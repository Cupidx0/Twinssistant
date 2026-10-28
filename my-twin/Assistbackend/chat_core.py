import asyncio
import base64
import io
import json
import os
import re
import traceback
from datetime import datetime, timedelta

from dotenv import load_dotenv
from firebase_admin import firestore
from flask import Blueprint, request, jsonify
from gtts import gTTS
from tavily import TavilyClient
from eleven import text_to_speech_ws_streaming
from Routing import create_chat_completion, extract_function_call, create_anthropic_completion, extract_message_content, create_gemini_completion
from Pinecone_vec import save_pattern, find_pattern
from auth_utils import require_owner, require_auth, init_firebase
from Relevant_memory import memory_search, memo_gpt, resolve_and_run_laptop_tool, keyword_classify, is_laptop_command
from calendar_route import safe_get_calendar_events, add_event_to_calendar, calendar_functions
from weather_route import fetch_weather
from jobs import search_jobs
from utils import get_request_json, parse_natural_datetime, has_word

chat_bp = Blueprint('chat', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CV_DIR = os.path.join(BASE_DIR, "Cv_docs")
CV_INFO_FILE = os.path.join(BASE_DIR, "refined")
CHAT_DIR = os.path.join(BASE_DIR, "chat")
CHAT_HISTORY_FILE = os.path.join(CHAT_DIR, "chat_history.txt")
load_dotenv()
tavilyclient = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
# Firebase UIDs allowed to control the host Mac (comma-separated in .env).
# Registration is open, so nobody gets laptop control unless listed here.
MAC_TOOL_UIDS = {u.strip() for u in os.getenv("OWNER_UIDS", "").split(",") if u.strip()}
firebase_app, db = init_firebase()
WEB_SEARCH_KEYWORDS = [
    "latest", "news", "search", "youtube", "today", "current", "year","lyrics", "video", "videos", "google", "bing", "duckduckgo", "search engine",
    "music", "song", "songs", "weather", "sports", "football", "cricket", "president",
    "prime minister", "capital of", "country", "countries", "who is", "what is",
    "when is", "where is", "how to", "define"
]

"""def pull_frm_db():
    try:
        doc_ref = db.collection("conversations").stream()
"""
INTENT_NAMES = ["calendar", "cv", "mac_tool", "code", "greeting", "web_search", "identity", "casual"]

def intent_classifier(user_text):
    try:
        cached_intent, cached_confidence = find_pattern(user_text)
        # Don't trust cached mac_tool hits: older cache entries came from a looser
        # keyword rule that sent ordinary questions to laptop control.
        if cached_intent == "mac_tool" and not is_laptop_command(user_text):
            cached_intent = None
        if cached_intent:
            print(f"Found cached intent: {cached_intent} with confidence {cached_confidence}")
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
            # Fall back to the keyword result on any classification failure
            print(f"Error during intent classification: {e}")

    try:
        save_pattern(user_text, intent=intent, confidence=confidence)
    except Exception as e:
        print(f"Intent cache save failed: {e}")
    return intent, confidence
def get_ai_response(user_text):
    try:
        namer = "Ashen"
        today = datetime.now().strftime("%Y-%m-%d")
        time = datetime.now().strftime("%H:%M:%S")
    #"""Generator — yields text chunks as Gemini produces them."""
    #model = genai.GenerativeModel(
     #   "gemini-3.1-flash-lite",
     #   system_instruction=f"You are a helpful assistant named Ashen. Current date {today}, time {time_now}."
    #)
        response = create_gemini_completion(
                    model="gemini-3.1-flash-lite",
                    messages=[
                        {"role": "system", "content": f"You are a helpful assistant,and your name is {namer},Current date is {today}, Current time is {time}."},
                        {"role": "user", "content": user_text}
                    ],
                    max_tokens=2048,
                    stream=True,
                    temperature=0.7
                )
        for chunk in response:
                if chunk.text:
                    yield chunk.text

        #response_text = extract_message_content(response).strip()
        #return response_text
    except Exception as e:
        yield f"Error generating response: {str(e)}"

@chat_bp.route('/api/voice_repeat', methods=['POST'])
@require_auth
def voice_repeat():
    audio_text = request.json.get('text').strip()
    audio_request = request.json.get('want_audio', True)
    audio_bytes = None
    if audio_request:
        if not audio_text:
            return jsonify({"error": "No text provided"}), 400
        try:
            audio_bytes = asyncio.run(text_to_speech_ws_streaming(
                        voice_id="JBFqnCBsd6RMkjVDRZzb",
                        model_id="eleven_flash_v2_5",
                        text=audio_text,
                    ))
        except Exception:
            try:
                audio_bytes = text_to_speech_sync(audio_text)
            except Exception as e2:
                return jsonify({"error": f"Text-to-speech failed: {e2}"}), 500
    audio_b64 = base64.b64encode(audio_bytes).decode() if audio_bytes else None
    return jsonify({'type': 'audio', 'text': audio_text, 'audio': audio_b64})
def text_to_speech_sync(text: str) -> bytes:
    tts = gTTS(text=text, lang='en')
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    return buf.getvalue()
def smart_chat_history(history_text, recent=6):
    """Keep the last `recent` exchanges verbatim and squash older ones into one line.

    History is stored as text blocks separated by blank lines (one per exchange).
    """
    turns = [t for t in history_text.split("\n\n") if t.strip()]
    if len(turns) <= recent:
        return history_text

    old = turns[:-recent]
    recent_turns = turns[-recent:]
    summary = f"Earlier in conversation: {' | '.join(t[:50] for t in old)}"
    return summary + "\n" + "\n\n".join(recent_turns)
def episodic_memory_search(user_text):
    """Search for relevant past conversations in chat history."""
    try:
        return {"memoran":memory_search(user_text),
                "grant":memo_gpt(user_text)
        }

    except Exception as e:
        print(f"Episodic memory search failed: {e}")
        return None
def push_to_db(user_id, user_text, ai_response,conversation_id):
    """Store the conversation in Firestore."""
    try:
        doc_ref = db.collection('conversations').document(conversation_id)
        message_ref = doc_ref.collection('messages').document()
        message_ref.set({
            "userId": user_id,
            "user": user_text,
            "assistant": ai_response,
            "category": "transmigration",
            "source": None,
            "clienttimestamp": datetime.now().isoformat(),
            "conversationId": conversation_id,
            "Servertimestamp": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print(f"Failed to push to DB: {e}")
def tavily_search(query, max_results=5):
    """Perform a web search using Tavily and return results."""
    try:
        results = tavilyclient.search(
            query=query,
            include_answer="advanced",
            search_depth="advanced",
            include_raw_content="text",
            max_results=max_results
        )
        items = results.get("results", []) if isinstance(results, dict) else results
        return [{"title": r.get("title", "Untitled"), "url": r.get("url", "")} for r in items[:max_results]]
    except Exception as e:
        print(f"Tavily search failed: {e}")
        return []
def chat_prompt(message, user_id, data):
    intent, confidence = intent_classifier(message)
    calevent = None
    if intent == "calendar":
        calevent = safe_get_calendar_events(data, user_id)  # also: was request.user["uid"] — wrong for a helper meant to work for both transports, see #5

    if "weather" in message.lower():
        city = get_user_city(user_id,"horley")  # default to "horley" if not found
        weather = fetch_weather(city)
        reply = (f"The current weather in {weather['city']} is {weather['temperature']}°C "
                  f"with {weather['description']}.") if weather else "Sorry, I could not fetch the weather right now."
        return {"early_reply": reply}

    creatorname = "Godwin Alamu"
    history = smart_chat_history(read_chat_history())
    epi = episodic_memory_search(message)
    ep = epi.get("memoran")
    episodic = epi.get("grant")
    memory_was_used = bool(ep) or bool(episodic)

    if history.count("User:") > 40:
        return {"early_reply": "Your chat history is too long. Do you want to clear it (Y/N)?"}

    fit_check = f"if the user asks for outfit suggestion or fashion advice, check {episodic} if the user's sex, age, height, weight, skin tone is in the history — if not, ask the user for the details."

    cv_info = None
    cv_info_json = os.path.join(CV_INFO_FILE, "review_Software_Engineer.json")
    if intent == "cv" and os.path.exists(cv_info_json):
        with open(cv_info_json, "r") as f:
            cv_info = json.load(f)

    web_context, sources = "", []
    if intent == "web_search" or has_word(message.lower(), WEB_SEARCH_KEYWORDS):
        try:
            results = tavily_search(message, max_results=5)
            sources = [{"title": r.get("title", "Untitled"), "url": r.get("url", "")} for r in results]
            web_context = "\n".join(f"[{i}] {s['title']}: {s['url']}" for i, s in enumerate(sources, start=1))
        except Exception as e:
            web_context = f"(Tavily search failed: {e})"
    web_search_was_used = bool(intent == "web_search") or bool(has_word(message.lower(), WEB_SEARCH_KEYWORDS))

    today = datetime.now().strftime("%Y-%m-%d")
    time = datetime.now().strftime("%H:%M:%S")

    prompt = (
                f"""
                You are Godwin's personal AI assistant. You are sharp, intelligent, and adaptive — not just a coding assistant. Most conversations will be personal, practical, or conversational.
    
                Today is {today}, current time is {time}.
    
                Context available to you:
                - Web search results: {web_context if web_context else 'None'}
                - Calendar events: {calevent if calevent else 'None'}
                - Conversation history: {history if history else {episodic} if episodic else 'None'}
                - Current message: {message}
                Respond to this directly and specifically. Do not get distracted by context unless it
                How to behave:
                - Prioritise web context over your training knowledge for anything current
                - Primary rule: Always respond directly to the current message first.
                    Use context only if it strengthens the response.
                - If it's casual, respond like a smart friend — no unnecessary structure
                - If it's technical, be precise and concise
                - If it's emotional or personal, be empathetic and grounded
                - For code, format it cleanly with a brief explanation
                - Always review Conversation history and episodic memory for relevant info, but don't repeat it unless it strengthens your response
                - For CV questions, use the uploaded CV and give concrete specific feedback. Latest CV review: {cv_info if cv_info else 'none available — ask him to upload a CV first'}
                - For calendar, use the events provided and confirm when adding or deleting
                - In voice mode, respond in natural spoken sentences — no bullet points, no markdown
                - Be direct. Don't over-explain. Don't pad responses
                - Always respond in plain conversational language unless code or structure is specifically needed
    
                What you can handle:
                - Weather: suggest outfits based on conditions, from closet if available
                - Outfit: using {fit_check} suggest outfits based on conditions, from closet if available
                - Career: CV feedback, cover letters, interview prep
                - Learning: explain Python, React, DSA step by step, build study plans
                - Productivity: plan tasks, manage time, suggest routines
                - Personal_info: use {episodic} and Conversational history to remember user's age, height, weight, skin tone, sex, body
                - Personal: be empathetic and motivational when needed
                - Fun: jokes, trivia, light content when the mood calls for it
                - Web: search and provide relevant links when useful
                - Music: suggest songs or provide lyrics if asked
                - Calendar: fetch, add, delete Google Calendar events
                - Mac: you have access to Godwin's calendar, files, and Mac
    
                About Godwin:
                - Developer learning Python, React, and DSA
                - Targeting apprenticeships and junior roles
                - Built you — so he knows how you work
    
                You are built by {creatorname} and still evolving.
                """
            )

    assistantname = data.get("assistantname", "").strip()
    namer = assistantname or "Ashen"
    system_msg = f"You are a helpful assistant named {namer}. Current date is {today}, current time is {time}."

    return {
        "early_reply": None,
        "prompt": prompt,
        "system_msg": system_msg,
        "intent": intent,
        "sources": sources,
        "memory_was_used": memory_was_used,
        "web_search_was_used": web_search_was_used,
        "calevent": calevent,
    }
def process_chat_message(message, user_id, data):
    """
    Runs the full chat pipeline: intent routing, model call, DB/local persistence.
    Returns (reply, source, info). Raises on unrecoverable errors , caller decides
    how to surface them (jsonify vs emit).
    """
    prompter = chat_prompt(message, user_id, data)
    if prompter.get("early_reply"):
        return prompter["early_reply"], None, None  # caller checks for this case

    prompt = prompter.get("prompt")
    system_msg = prompter.get("system_msg")
    intent = prompter.get("intent")
    source = prompter.get("sources")
    memory_was_used = prompter.get("memory_was_used")
    web_search_was_used = prompter.get("web_search_was_used")

    reply = None
    if intent == "calendar":
        response = create_anthropic_completion(
            model="claude-sonnet-4-6",
            system=system_msg,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.7,
            functions=calendar_functions,
            function_call="auto"
        )
        fn = extract_function_call(response)
        if fn:
            fn_name = fn["name"]
            raw_args = fn.get("arguments") or {}
            args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args or "{}")

            if fn_name == "add_calendar_event":
                end_time = parse_natural_datetime(args.get("end"))
                if not end_time:
                    reply = "Sorry, I couldn't work out the date/time for that event — could you be more specific?"
                else:
                    end_time_obj = datetime.fromisoformat(end_time)
                    start_time = end_time_obj - timedelta(hours=1)
                    add_event_to_calendar(args.get("summary"), start_time.isoformat(), end_time_obj.isoformat())
                    reply = f"Done — added \"{args.get('summary')}\" to your calendar for {end_time_obj.strftime('%A %d %b, %H:%M')}."

            elif fn_name == "get_calendar_events":
                calevent = safe_get_calendar_events(args, user_id)
                reply = f"Here's what's on your calendar: {calevent}"

    elif intent in ("weather", "web_search") or any(k in message.lower() for k in ["weather", "outfit", "logic", "jokes"]):
        response = create_gemini_completion(
            model="gemini-3.1-flash-lite",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2048,
            temperature=0.7
        )
        if reply is None:
            reply = extract_message_content(response).strip()
    elif intent == "mac_tool":
        if user_id not in MAC_TOOL_UIDS:
            reply = "Sorry, laptop control isn't enabled for your account."
        else:
            result = resolve_and_run_laptop_tool(message)
            if result.get("success"):
                reply = result.get("message") or "Done."
            else:
                reply = f"Couldn't do that — {result.get('error', 'unknown error')}"
    elif intent == "jobs": 
        result = search_jobs(message)
        if result.get("success"):
            jobs = result.get("jobs", [])
            if not jobs:
                reply = "No job listings found."
            else:
                lines = [
                    f"{i}. {j.get('title')} at {j.get('company')} ({j.get('location')}) {j.get('url')}"
                    for i, j in enumerate(jobs[:10], 1)
                ]
                reply = f"Found {len(jobs)} jobs:\n\n" + "\n".join(lines)
        else:
            reply = f"Job search failed: {result.get('error', 'unknown error')}"
    else:
        response = create_chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2048,
            temperature=0.7
        )
        if reply is None:
            reply = extract_message_content(response).strip()

    try:
        push_to_db(user_id, message, reply, conversation_id= """eligible for changes"""f"user_{user_id}")
    except Exception as e:
        print(f"Error occurred while pushing to DB: {e}")
        print("Continuing without saving to DB, saved locally.")
        os.makedirs(CHAT_DIR, exist_ok=True)
        with open(CHAT_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"User: {message}\nAssistant: {reply}\n Source: {source}\n Timestamp: {datetime.now().isoformat()}\n\n")

    info = "relying on internal knowledge"
    if memo_gpt and memory_was_used:
        info = "recalled from episodic memory"
    if intent_classifier and web_search_was_used:
        info = "surfing the web"

    return reply, source, info


@chat_bp.route('/api/chat', methods=['POST'])
@require_auth
def chat():
    try:
        data = get_request_json()
        message = data.get("question", "").strip()
        user_id = request.user["uid"]
        if not message:
            return jsonify({"error": "Please provide a question."}), 400

        reply, source, info = process_chat_message(message, user_id, data)
        if source is None and info is None:
            # early_reply case
            return jsonify({"reply": reply}), 200

        return jsonify({"reply": reply, "sources": source, "info": info}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
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
