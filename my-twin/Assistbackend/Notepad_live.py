import os
import json
import asyncio
import threading
import websockets
from extensions import socketio
from dotenv import load_dotenv
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
#api call to get live audio transcription from the microphone
# Sessions are keyed by Socket.IO sid (not user id) so two tabs from the same
# user each get their own OpenAI connection and transcripts.
active_sessions = {}  # sid -> websocket connection
done_events = {}      # sid -> asyncio.Event set when the final transcript arrives
# Hard cap so a forgotten/abandoned recording can't keep an OpenAI socket open.
MAX_SESSION_SECONDS = 15 * 60
# One event loop, running forever in its own thread
_loop = asyncio.new_event_loop()
_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_thread.start()
def run_coroutine(coro):
    """Schedule a coroutine on the persistent loop and wait for its result."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()
async def start_session(sid):
    # Restarting from the same tab replaces the old connection instead of leaking it.
    await close_session(sid)
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
    active_sessions[sid] = ws
    done_events[sid] = asyncio.Event()
    # Start listening for transcripts in a separate task
    asyncio.create_task(listen_for_transcripts(sid, ws))
    asyncio.create_task(_expire_session(sid, ws))
    return ws

async def _expire_session(sid, ws):
    await asyncio.sleep(MAX_SESSION_SECONDS)
    if active_sessions.get(sid) is ws:
        socketio.emit('transcript_response', {
            "type": "error",
            "error": f"Recording stopped after {MAX_SESSION_SECONDS // 60} minutes."
        }, room=sid)
        await close_session(sid)

async def send_chunk(sid, pcm_b64):
    ws = active_sessions.get(sid)
    if ws:
        try:
            await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": pcm_b64}))
        except websockets.exceptions.ConnectionClosed:
            await close_session(sid)

async def listen_for_transcripts(sid, ws):
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
                print(f"Transcription completed for sid {sid} ({len(transcript)} chars)")
                ev = done_events.get(sid)
                if ev:
                    ev.set()

            elif etype == "error":
                socketio.emit('transcript_response', {"type": "error", "error": str(event)}, room=sid)
                print(f"Transcription error for sid {sid}: {event}")

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        # OpenAI side closed (or errored): drop the stale entry if it's still ours.
        if active_sessions.get(sid) is ws:
            active_sessions.pop(sid, None)
            done_events.pop(sid, None)

async def commit_and_get_transcript(sid, timeout=10):
    ws = active_sessions.get(sid)
    ev = done_events.get(sid)
    if not ws or not ev:
        return
    ev.clear()
    try:
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        await asyncio.wait_for(ev.wait(), timeout)
    except asyncio.TimeoutError:
        print("Timed out waiting for final transcript")
    except websockets.exceptions.ConnectionClosed:
        pass
    await close_session(sid)

async def close_session(sid):
    ws = active_sessions.pop(sid, None)
    done_events.pop(sid, None)
    if ws:
        await ws.close()
