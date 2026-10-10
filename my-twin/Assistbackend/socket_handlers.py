import asyncio
import base64
import re
import traceback

from firebase_admin import auth as fb_auth
from flask import request, session
from flask_socketio import emit, disconnect

from extensions import socketio
from eleven import text_to_speech_ws_streaming
from Notepad_live import start_session, send_chunk, commit_and_get_transcript, close_session, run_coroutine
from chat_core import get_ai_response, text_to_speech_sync, process_chat_message

SENTENCE_END_RE = re.compile(r'(?<=[.!?])\s+')

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
@socketio.on('voice_message')
def handle_voice(data):
    user_text = data.get('text', '').strip()
    user_id = session.get('uid')
    if not user_id:
        emit('ai_response', {"type": "error", "error": "Not authenticated."})
        return
    if not user_text:
        return

    buffer = ""
    full_text = ""

    for text_chunk in get_ai_response(user_text):
        full_text += text_chunk
        buffer += text_chunk
        emit('ai_response', {"type": "text", 'text': text_chunk})  # live text, immediately

        parts = SENTENCE_END_RE.split(buffer)
        if len(parts) > 1:
            *complete, buffer = parts  # last part is an incomplete trailing sentence
            for sentence in complete:
                _synthesize_and_emit(sentence)

    if buffer.strip():
        _synthesize_and_emit(buffer)

    emit('ai_response', {'type': 'done', 'text': full_text})

def _synthesize_and_emit(sentence):
    audio_bytes = None
    try:
        audio_bytes = asyncio.run(text_to_speech_ws_streaming(
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_flash_v2_5",
            text=sentence,
        ))
    except Exception:
        try:
            audio_bytes = text_to_speech_sync(sentence)
        except Exception as e2:
            print(f"gTTS also failed: {e2}")
    audio_b64 = base64.b64encode(audio_bytes).decode() if audio_bytes else None
    emit('ai_response',{'type': 'audio', 'text': sentence, 'audio': audio_b64})

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
    # Tab closed / navigated away mid-recording: don't leave the OpenAI socket open.
    try:
        run_coroutine(close_session(request.sid))
    except Exception:
        traceback.print_exc()
@socketio.on('stream_chat')
def ws_stream_chat(data):
    try:
        user_id = session.get('uid')
        if not user_id:
            emit('ai_response', {"type": "error", "error": "Not authenticated."})
            return

        message = (data or {}).get("question", "").strip()
        if not message:
            emit('ai_response', {"type": "error", "error": "Please provide a question."})
            return
        reply, source, info = process_chat_message(message, user_id, data)
        if source is None and info is None:
            emit('ai_response', {"type":"done", "reply": reply})
            return
        if info:
            emit('ai_response', {"type":"info", "info": info})
        emit('ai_response', {"type":"done", "reply": reply, "sources": source, "info": info})
    except Exception as e:
        traceback.print_exc()
        emit('ai_response', {"type":"error", "error": str(e)})
