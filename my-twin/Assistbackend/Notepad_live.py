import os
import re
import json
import base64
import asyncio
import subprocess
import platform
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from auth_utils import require_auth
import sounddevice as sd
import numpy as np
import websockets
import threading
from firebase_admin import firestore
from Routing import create_chat_completion, create_gemini_completion, extract_message_content
from dotenv import load_dotenv
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAT_DIR = os.path.join(BASE_DIR, "chat")
user_chat_history = os.path.join(CHAT_DIR, "chat_history.txt")
cred = credentials.Certificate("tw.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
openai_api_key = os.getenv("OPENAI_API_KEY")
#api call to get live audio transcription from the microphone
active_sessions = {}  # user_id -> websocket connection

# One event loop, running forever in its own thread
_loop = asyncio.new_event_loop()
_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_thread.start()

def run_coroutine(coro):
    """Schedule a coroutine on the persistent loop and wait for its result."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()
async def start_session(user_id):
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
    return ws

async def send_chunk(user_id, pcm_b64):
    ws = active_sessions.get(user_id)
    if ws:
        await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": pcm_b64}))

async def commit_and_get_transcript(user_id):
    ws = active_sessions.get(user_id)
    if not ws:
        return None
    await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
    async for message in ws:
        event = json.loads(message)
        if event["type"] == "conversation.item.input_audio_transcription.completed":
            return event["transcript"]
        if event["type"] == "error":
            return f"Error: {event}"

async def close_session(user_id):
    ws = active_sessions.pop(user_id, None)
    if ws:
        await ws.close()