import asyncio
import base64
import io
import json
import os
import re
import traceback
from datetime import datetime

from dotenv import load_dotenv
from firebase_admin import firestore
from flask import Blueprint, request, jsonify
from gtts import gTTS

import memory
from agent import agent_turn
from artifacts import save_artifacts
from auth_utils import require_auth, init_firebase
from context import build_request, conversation_id_for, format_turns, load_recent_turns, summarise_in_background
from costs import budget_status, log_service
from eleven import text_to_speech_ws_streaming
from model_router import choose_model, detect_difficulty_intent
from Pinecone_vec import save_pattern, find_pattern
from Relevant_memory import keyword_classify, is_laptop_command
from Routing import extract_message_content, create_gemini_completion
from services import MODEL_CHEAP, OWNER_UIDS
from tools import ToolContext, tools_for
from uploads import load_upload_blocks
from ratelimit import rate_limited
from utils import get_request_json
from weather_route import fetch_weather

chat_bp = Blueprint('chat', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CV_INFO_FILE = os.path.join(BASE_DIR, "refined")
CHAT_DIR = os.path.join(BASE_DIR, "chat")
CHAT_HISTORY_FILE = os.path.join(CHAT_DIR, "chat_history.txt")
load_dotenv()
# Firebase UIDs allowed to control the host Mac and calendar (comma-separated OWNER_UIDS in .env).
# Registration is open, so nobody gets those tools unless listed here.
MAC_TOOL_UIDS = OWNER_UIDS
firebase_app, db = init_firebase()

INTENT_NAMES = ["calendar", "cv", "mac_tool", "code", "greeting", "web_search", "identity", "casual",
                "jobs", "writing", "assessment"]
# Intents where recalling long-term memory is not worth the extra latency.
NO_MEMORY_INTENTS = {"greeting", "identity", "mac_tool"}
MODEL_LABELS = {"claude-haiku-5-5": "Haiku 5.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-opus-5-5": "Opus 5.5"}


def intent_classifier(user_text):
    """Existing three-tier router: Pinecone cache -> keyword rules -> cheap LLM."""
    try:
        cached_intent, cached_confidence = find_pattern(user_text)
        # Don't trust cached mac_tool hits: older cache entries came from a looser
        # keyword rule that sent ordinary questions to laptop control.
        if cached_intent == "mac_tool" and not is_laptop_command(user_text):
            cached_intent = None
        if cached_intent:
            return cached_intent, cached_confidence
    except Exception as e:
        print(f"Intent cache lookup failed: {e}")

    intent = keyword_classify(user_text)
    confidence = 0.9 if intent != "casual" else 0.5
    if confidence < 0.7:
        try:
            response = create_gemini_completion(
                model="gemini-3.1-flash-lite",
                messages=[
                    {"role": "system", "content": (
                        "You classify user intents. Respond with JSON only: "
                        f'{{"intent": one of {INTENT_NAMES}, "confidence": 0-1}}'
                    )},
                    {"role": "user", "content": f"Classify the intent of this message: '{user_text}'"}
                ],
                max_tokens=50,
                temperature=0.5
            )
            response_text = extract_message_content(response).strip()
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not match:
                raise ValueError(f"No JSON found in: {response_text}")
            response_json = json.loads(match.group())
            intent = response_json.get("intent", intent)
            confidence = float(response_json.get("confidence", confidence))
        except Exception as e:
            print(f"Error during intent classification: {e}")

    try:
        save_pattern(user_text, intent=intent, confidence=confidence)
    except Exception as e:
        print(f"Intent cache save failed: {e}")
    return intent, confidence


@chat_bp.route('/api/voice_repeat', methods=['POST'])
@require_auth
def voice_repeat():
    audio_text = (request.json.get('text') or '').strip()
    audio_request = request.json.get('want_audio', True)
    audio_bytes = None
    if audio_request:
        if not audio_text:
            return jsonify({"error": "No text provided"}), 400
        audio_bytes = synthesize(audio_text, request.user["uid"])
        if audio_bytes is None:
            return jsonify({"error": "Text-to-speech failed"}), 500
    audio_b64 = base64.b64encode(audio_bytes).decode() if audio_bytes else None
    return jsonify({'type': 'audio', 'text': audio_text, 'audio': audio_b64})


def text_to_speech_sync(text: str) -> bytes:
    tts = gTTS(text=text, lang='en')
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    return buf.getvalue()


def synthesize(text, user_id=None):
    """ElevenLabs first, then gTTS. Returns bytes or None (the browser falls back to speechSynthesis)."""
    try:
        audio = asyncio.run(text_to_speech_ws_streaming(
            voice_id="JBFqnCBsd6RMkjVDRZzb", model_id="eleven_flash_v2_5", text=text))
        log_service(user_id, "elevenlabs_chars", len(text), feature="voice")
        return audio
    except Exception:
        try:
            return text_to_speech_sync(text)
        except Exception as e:
            print(f"gTTS also failed: {e}")
            return None


def push_to_db(user_id, user_text, ai_response, conversation_id, extra=None):
    """Store one exchange in Firestore (conversations/{id}/messages/{id})."""
    doc_ref = db.collection('conversations').document(conversation_id)
    message_ref = doc_ref.collection('messages').document()
    message_ref.set({
        "userId": user_id,
        "user": user_text,
        "assistant": ai_response,
        "category": "chat",
        "source": None,
        "clienttimestamp": datetime.now().isoformat(),
        "conversationId": conversation_id,
        "Servertimestamp": firestore.SERVER_TIMESTAMP,
        **(extra or {}),
    })
    doc_ref.set({"userId": user_id, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)


def _save_locally(message, reply, sources):
    os.makedirs(CHAT_DIR, exist_ok=True)
    with open(CHAT_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"User: {message}\nAssistant: {reply}\n Source: {sources}\n Timestamp: {datetime.now().isoformat()}\n\n")


def _simple_result(reply, conv_id, info=None):
    return {"reply": reply, "sources": [], "info": info, "model": None, "usage": None,
            "artifacts": [], "conversation_id": conv_id}


def process_chat_message(message, user_id, data, emit=None, confirm=None):
    """Full chat pipeline. `emit(event, payload)` streams "token", "thinking", "tool",
    "tool_done" and "info" events; None for plain HTTP. `confirm(action, args)` asks the
    UI to approve destructive tool calls (None means they are refused).

    Returns a dict: reply, sources, info, model, usage, artifacts, budget, conversation_id.
    """
    data = data or {}
    conv_id = conversation_id_for(user_id, data)
    is_owner = user_id in MAC_TOOL_UIDS

    def status(text):
        if emit:
            emit("info", {"info": text})

    lowered = message.lower()
    if "weather" in lowered and len(message) < 60 and not data.get("upload_ids"):
        weather = fetch_weather("horley")
        reply = (f"The current weather in {weather['city']} is {weather['temperature']}°C "
                 f"with {weather['description']}.") if weather else "Sorry, I could not fetch the weather right now."
        return _simple_result(reply, conv_id)

    forget_what = memory.forget_request(message)
    if forget_what:
        status("Forgetting")
        removed = memory.forget_matching(user_id, forget_what)
        reply = ("Done. I've forgotten:\n" + "\n".join(f"- {r}" for r in removed)) if removed \
            else "I couldn't find anything saved about that."
        return _simple_result(reply, conv_id, "memory updated")

    intent, _ = intent_classifier(message)
    intent = detect_difficulty_intent(message, intent)
    think = bool(data.get("think"))
    budget = budget_status(user_id)
    model, why = choose_model(intent, message, data.get("model"), think, budget["over_budget"])
    status(f"{MODEL_LABELS.get(model, model)} · {why}")

    recent_turns = load_recent_turns(conv_id)
    memories = []
    if intent not in NO_MEMORY_INTENTS:
        status("Checking past chats")
        try:
            memories = memory.retrieve(user_id, message, recent=format_turns(recent_turns[-3:]),
                                       current_conv_id=conv_id)
        except Exception as e:
            print(f"Memory retrieval failed: {e}")

    upload_blocks, upload_names = load_upload_blocks(user_id, data.get("upload_ids"))

    extra_context = {}
    cv_info_json = os.path.join(CV_INFO_FILE, "review_Software_Engineer.json")
    if intent == "cv" and os.path.exists(cv_info_json):
        with open(cv_info_json, "r") as f:
            extra_context["latest_cv_review"] = f.read()[:20000]

    system, messages = build_request(user_id, conv_id, message, memories=memories,
                                     upload_blocks=upload_blocks, extra_context=extra_context,
                                     voice=bool(data.get("voice")), turns=recent_turns)
    ctx = ToolContext(user_id=user_id, is_owner=is_owner, conv_id=conv_id, confirm=confirm)
    effort = "low" if model == MODEL_CHEAP else "medium"
    result = agent_turn(emit, model, system, messages, tools_for(is_owner), ctx, think=think, effort=effort)
    reply = result["reply"]

    artifacts = save_artifacts(user_id, conv_id, reply)
    try:
        push_to_db(user_id, message, reply, conv_id, extra={
            "model": result["model"], "intent": intent, "tokens": result["usage"],
            "upload_ids": data.get("upload_ids") or [], "upload_names": upload_names,
            "sources": ctx.sources})
    except Exception as e:
        print(f"Error occurred while pushing to DB: {e}. Saved locally instead.")
        _save_locally(message, reply, ctx.sources)

    if intent not in {"greeting", "identity"}:
        memory.write_memory_in_background(user_id, conv_id, message, reply)
    summarise_in_background(user_id, conv_id)

    info = [MODEL_LABELS.get(result["model"], result["model"])]
    if "web_search" in ctx.used:
        info.append("searched the web")
    if memories or "search_memory" in ctx.used:
        info.append("recalled from memory")
    if not ctx.used and not memories:
        info.append("internal knowledge")

    return {"reply": reply, "sources": ctx.sources, "info": " · ".join(info), "model": result["model"],
            "usage": result["usage"], "artifacts": artifacts, "budget": budget, "conversation_id": conv_id,
            "memories_used": len(memories), "tools_used": ctx.used}


@chat_bp.route('/api/chat', methods=['POST'])
@require_auth
@rate_limited("chat")
def chat():
    try:
        data = get_request_json()
        message = data.get("question", "").strip()
        user_id = request.user["uid"]
        if not message:
            return jsonify({"error": "Please provide a question."}), 400
        return jsonify(process_chat_message(message, user_id, data)), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/api/history", methods=["GET"])
@require_auth
def conversation_history():
    """Recent exchanges of a conversation so the UI can restore the thread."""
    user_id = request.user["uid"]
    conv_id = conversation_id_for(user_id, {"conversation_id": request.args.get("conversation_id")})
    if conv_id != f"user_{user_id}":
        snap = db.collection("conversations").document(conv_id).get()
        if not snap.exists or (snap.to_dict() or {}).get("userId") != user_id:
            return jsonify({"error": "Not found"}), 404
    turns = load_recent_turns(conv_id, n=min(int(request.args.get("limit", 20)), 100))
    return jsonify({"conversation_id": conv_id, "turns": [
        {"user": t.get("user"), "assistant": t.get("assistant"), "model": t.get("model"),
         "sources": t.get("sources") or [], "ts": t.get("clienttimestamp")} for t in turns]})


def read_chat_history(n=10):
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-(n * 2):])
    return ""


@chat_bp.route("/load_history", methods=["GET"])
@require_auth
def load_chat_history():
    return jsonify({"history": read_chat_history()})


@chat_bp.route("/clear", methods=["POST"])
@require_auth
def clear_chat():
    try:
        data = request.get_json()
        confirmation = data.get("confirmation", "").strip().lower()
        if confirmation == "yes":
            os.makedirs(CHAT_DIR, exist_ok=True)
            with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write("")
            return jsonify({"reply": "Chat history cleared."})
        return jsonify({"reply": "Chat history not cleared."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
