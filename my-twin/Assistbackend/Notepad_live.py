import os
import json
import asyncio
import threading
from datetime import datetime
import websockets
from extensions import socketio
from dotenv import load_dotenv
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAT_DIR = os.path.join(BASE_DIR, "chat")
user_chat_history = os.path.join(CHAT_DIR, "chat_history.txt")
user_note_history = os.path.join(CHAT_DIR, "note_history.txt")
openai_api_key = os.getenv("OPENAI_API_KEY")
#api call to get live audio transcription from the microphone
active_sessions = {}  # user_id -> websocket connection
done_events = {}
# One event loop, running forever in its own thread
_loop = asyncio.new_event_loop()
_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_thread.start()
def run_coroutine(coro):
    """Schedule a coroutine on the persistent loop and wait for its result."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()
async def start_session(user_id, sid):
    url = "wss://api.openai.com/v1/realtime?intent=transcription"
    headers = {"Authorization": f"Bearer {openai_api_key}"}
    ws = await websockets.connect(url, additional_headers=headers)
    await ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "type": "transcription",
            "audio": {"input": {
                "format": {"type": "audio/pcm", "rate": 24000},
                "transcription": {"model": "gpt-live-transcribe"},
                "turn_detection": None
            }}
        }
    }))
    active_sessions[user_id] = ws
    done_events[user_id] = asyncio.Event()
    # Start listening for transcripts in a separate task
    asyncio.create_task(listen_for_transcripts(user_id, sid))
    return ws

async def send_chunk(user_id, pcm_b64):
    ws = active_sessions.get(user_id)
    if ws:
        await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": pcm_b64}))

def log_note(user_id, label, text):
    os.makedirs(CHAT_DIR, exist_ok=True)
    with open(user_note_history, "a", encoding="utf-8") as f:
        f.write(f"\n--- {label} at {datetime.now()} ---\n")
        f.write(f"User ID: {user_id}\n")
        f.write(f"Transcript: {text}\n")

async def listen_for_transcripts(user_id, sid):
    ws = active_sessions.get(user_id)
    if not ws:
        return
    try:
        async for message in ws:
            event = json.loads(message)
            etype = event.get("type")

            if etype == "conversation.item.input_audio_transcription.delta":
                socketio.emit('transcript_response', {
                    "type": "delta",
                    "delta": event["delta"]
                }, room=sid)

            elif etype == "conversation.item.input_audio_transcription.completed":
                transcript = event.get("transcript", "")
                socketio.emit('transcript_response', {
                    "type": "done",
                    "transcript": transcript,
                }, room=sid)
                print(f"Transcription completed for user {user_id}: {transcript}")
                log_note(user_id, "Transcription received", f"Transcript: {transcript}")
                ev = done_events.get(user_id)
                if ev:
                    ev.set()

            elif etype == "error":
                socketio.emit('transcript_response', {"type": "error", "error": str(event)}, room=sid)
                log_note(user_id, "Transcription error", f"Error: {event}")

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception:
        import traceback
        traceback.print_exc()

async def commit_and_get_transcript(user_id,timeout=10):
    ws = active_sessions.get(user_id)
    ev = done_events.get(user_id)
    if not ws or not ev:
        return
    ev.clear()
    await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
    try:
        await asyncio.wait_for(ev.wait(), timeout)
    except asyncio.TimeoutError:
        print("Timed out waiting for final transcript")
    await close_session(user_id)
    done_events.pop(user_id, None)
        
async def close_session(user_id):
    ws = active_sessions.pop(user_id, None)
    if ws:
        await ws.close()