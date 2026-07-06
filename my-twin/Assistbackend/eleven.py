import asyncio
import json
import base64
import os
import websockets
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

async def text_to_speech_ws_streaming(voice_id: str, model_id: str, text:str):
    uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input?model_id={model_id}"

    async with websockets.connect(uri) as websocket:
        # Initialize connection
        await websocket.send(json.dumps({
            "text": " ",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.8
            },
            "generation_config": {
                "chunk_length_schedule": [120, 160, 250, 290]
            },
            "xi_api_key": ELEVENLABS_API_KEY
        }))

        # Send text chunks
        await websocket.send(json.dumps({"text": text}))
        # Close stream (empty text signals completion)
        await websocket.send(json.dumps({"text": ""}))

        # Receive and process audio chunks
        audio_chunks = []
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            if data.get("audio"):
                audio_chunks.append(base64.b64decode(data["audio"]))
            elif data.get("isFinal"):
                break

        return b"".join(audio_chunks)

async def main():
    audio = await text_to_speech_ws_streaming(
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_flash_v2_5",
        text="Hello, this is a test of the text to speech pipeline,my name tha goat."
    )
    with open("output.mp3", "wb") as f:
        f.write(audio)

if __name__ == "__main__":
    asyncio.run(main())