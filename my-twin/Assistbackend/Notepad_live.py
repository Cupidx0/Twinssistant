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
sampling_rate = 24000  # 16 kHz
duration = 5  # seconds
def sample_recording(sampling_rate, duration):
    print("Recording...")
    recording = sd.rec(int(sampling_rate * duration), samplerate=sampling_rate, channels=1, dtype='float32')
    sd.wait()  # Wait until recording is finished
    print("Recording finished.")
    return recording.tobytes()
async def get_live_transcription(pcm_bytes):
    url = "wss://api.openai.com/v1/realtime?intent=transcription"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",}
    async with websockets.connect(url, extra_headers=headers) as ws:
        # Send the PCM audio data to the server
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": sampling_rate},
                        "transcription": {"model": "gpt-live-transcribe"},
                        "turn_detection": None
                    }
                }
            }
        }))
        chunk_size = 3200  # Number of bytes to send in each chunk
        for i in range(0, len(pcm_bytes),chunk_size):
            chunk = pcm_bytes[i:i + chunk_size]
            await ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(chunk).decode("utf-8")
            }))
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        transcript = ""
        async for message in ws:
            event = json.loads(message)
            if event["type"] == "conversation.item.input_audio_transcription.delta":
                print(event["delta"], end="", flush=True)
                transcript += event["delta"]
            elif event["type"] == "conversation.item.input_audio_transcription.completed":
                transcript += event["transcript"]
                break
            elif event["type"] == "error":
                print("\nError:", event)
                break
        return transcript
if __name__ == "__main__":
    pcm_bytes = sample_recording(sampling_rate, duration)
    transcription = asyncio.run(get_live_transcription(pcm_bytes))
    print("Transcription:", transcription)