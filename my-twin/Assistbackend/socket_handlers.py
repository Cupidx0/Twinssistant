import base64
import queue
import re
import threading
import traceback
import uuid

from firebase_admin import auth as fb_auth
from flask import request, session
from flask_socketio import emit, disconnect

from extensions import socketio
from Notepad_live import start_session, send_chunk, commit_and_get_transcript, close_session, run_coroutine
from chat_core import synthesize, process_chat_message
from ratelimit import allow

SENTENCE_END_RE = re.compile(r'(?<=[.!?])\s+')
CONFIRM_TIMEOUT_SECONDS = 60

# confirm_id -> {"sid", "event", "approved"}
_pending_confirms = {}
_confirm_lock = threading.Lock()


@socketio.on('connect')
def handle_connect(auth):
    token = (auth or {}).get("token", "")
    if not token:
        disconnect()
        return False
    try:
        decoded = fb_auth.verify_id_token(token)
    except Exception:
        disconnect()
        return False
    session['uid'] = decoded["uid"]


def _emitter(sid):
    """emit(event, payload) -> one 'ai_response' message with type=event."""
    def send(event, payload):
        socketio.emit('ai_response', {"type": event, **payload}, to=sid)
    return send


def _confirmer(sid):
    """Ask the UI to approve a destructive tool call; blocks until answered or timed out."""
    def confirm(action, args):
        confirm_id = uuid.uuid4().hex
        waiter = {"sid": sid, "event": threading.Event(), "approved": False}
        with _confirm_lock:
            _pending_confirms[confirm_id] = waiter
        socketio.emit('ai_response', {"type": "confirm", "id": confirm_id, "action": action, "args": args}, to=sid)
        waiter["event"].wait(CONFIRM_TIMEOUT_SECONDS)
        with _confirm_lock:
            _pending_confirms.pop(confirm_id, None)
        return waiter["approved"]
    return confirm


@socketio.on('tool_confirm_reply')
def handle_tool_confirm(data):
    confirm_id = (data or {}).get("id")
    with _confirm_lock:
        waiter = _pending_confirms.get(confirm_id)
    if waiter and waiter["sid"] == request.sid:
        waiter["approved"] = bool((data or {}).get("approved"))
        waiter["event"].set()


@socketio.on('stream_chat')
def ws_stream_chat(data):
    sid = request.sid
    try:
        user_id = session.get('uid')
        if not user_id:
            emit('ai_response', {"type": "error", "error": "Not authenticated."})
            return
        if not allow(user_id, "chat"):
            emit('ai_response', {"type": "error", "error": "Too many requests. Please slow down."})
            return
        message = (data or {}).get("question", "").strip()
        if not message:
            emit('ai_response', {"type": "error", "error": "Please provide a question."})
            return
        result = process_chat_message(message, user_id, data, emit=_emitter(sid), confirm=_confirmer(sid))
        socketio.emit('ai_response', {"type": "done", **result}, to=sid)
    except Exception as e:
        traceback.print_exc()
        socketio.emit('ai_response', {"type": "error", "error": str(e)}, to=sid)


@socketio.on('voice_message')
def handle_voice(data):
    """Voice mode: same pipeline as chat (memory, tools, Claude), spoken sentence by sentence."""
    sid = request.sid
    user_text = (data or {}).get('text', '').strip()
    user_id = session.get('uid')
    if not user_id:
        emit('ai_response', {"type": "done", "text": "You're not logged in."})
        return
    if not user_text:
        return
    if not allow(user_id, "chat"):
        emit('ai_response', {"type": "done", "text": "Too many requests. Please slow down."})
        return

    # TTS runs on a worker so token streaming never waits for audio; order is preserved.
    sentences = queue.Queue()

    def speak_worker():
        while True:
            sentence = sentences.get()
            if sentence is None:
                return
            audio = synthesize(sentence, user_id)
            socketio.emit('ai_response', {'type': 'audio', 'text': sentence,
                                          'audio': base64.b64encode(audio).decode() if audio else None}, to=sid)

    worker = threading.Thread(target=speak_worker, daemon=True)
    worker.start()
    buffer = {"text": ""}

    def voice_emit(event, payload):
        if event != "token":
            return
        chunk = payload["text"]
        socketio.emit('ai_response', {"type": "text", "text": chunk}, to=sid)
        buffer["text"] += chunk
        parts = SENTENCE_END_RE.split(buffer["text"])
        if len(parts) > 1:
            *complete, buffer["text"] = parts
            for sentence in complete:
                if sentence.strip():
                    sentences.put(sentence)

    try:
        result = process_chat_message(user_text, user_id, {**(data or {}), "voice": True}, emit=voice_emit)
        reply = result["reply"]
        if result.get("model") is None:  # shortcut replies are not streamed
            sentences.put(reply)
        elif buffer["text"].strip():
            sentences.put(buffer["text"])
    except Exception as e:
        traceback.print_exc()
        reply = f"Sorry, something went wrong: {e}"
        sentences.put(reply)
    sentences.put(None)
    worker.join()
    socketio.emit('ai_response', {'type': 'done', 'text': reply}, to=sid)


@socketio.on('start_live_transcription')
def ws_notepad(data):
    sid = request.sid
    try:
        user_id = session.get('uid')
        if not user_id:
            emit('transcript_response', {"type": "error", "error": "Not authenticated."}, room=sid)
            return
        run_coroutine(start_session(sid))
        emit('transcript_response', {"type": "started"}, room=sid)
    except Exception as e:
        traceback.print_exc()
        emit('transcript_response', {"type": "error", "error": str(e)}, room=sid)


@socketio.on('live_audio_chunk')
def handle_live_audio_chunk(data):
    pcm_b64 = (data or {}).get('audio')
    if session.get('uid') and pcm_b64:
        run_coroutine(send_chunk(request.sid, pcm_b64))


@socketio.on('stop_live_transcription')
def handle_stop_transcription(data):
    if not session.get('uid'):
        return
    # Waits for the final transcript (emitted by the listener), then closes the OpenAI socket.
    run_coroutine(commit_and_get_transcript(request.sid))


@socketio.on('disconnect')
def handle_disconnect(*args):
    sid = request.sid
    # Refuse any confirmation still waiting on this client.
    with _confirm_lock:
        for waiter in _pending_confirms.values():
            if waiter["sid"] == sid:
                waiter["event"].set()
    # Tab closed / navigated away mid-recording: don't leave the OpenAI socket open.
    try:
        run_coroutine(close_session(sid))
    except Exception:
        traceback.print_exc()
