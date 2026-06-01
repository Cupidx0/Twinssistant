from pickle import GET
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import openai
import anthropic
import os
import os.path
from dotenv import load_dotenv
from firebase_admin import credentials, firestore, initialize_app   
import requests
import cv2
from dateutil import parser
import dateparser
import pdfplumber
from docx import Document
from yaml import emit
from eleven import text_to_speech_ws_streaming
import asyncio
import base64
from tavily import TavilyClient
from datetime import datetime, time, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from gtts import gTTS
import io
from werkzeug.utils import secure_filename
from google import genai
from google.genai import types
import json
from flask_socketio import SocketIO, emit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CV_DIR = os.path.join(BASE_DIR, "Cv_docs")
CHAT_DIR = os.path.join(BASE_DIR, "chat")
CHAT_HISTORY_FILE = os.path.join(CHAT_DIR, "chat_history.txt")

load_dotenv()
api_key = os.getenv("OPENWEATHER_API_KEY")
city = "horley"
tavilyclient = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
openai.api_key = os.getenv("OPENAI_API_KEY")
anthropic.api_key = os.getenv("CLAUDE_API_KEY")
genai.api_key = os.getenv("GEMINI_API_KEY")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:5173"])

def get_tavily_results(query, num_results=5):
    """Helper to fetch Tavily search results."""
    try:
        results = tavilyclient.search(query=query, max_results=num_results)
        return results.get("results", [])
    except Exception as e:
        return [{"title": "Error", "url": "", "content": str(e)}]
def create_chat_completion(model, messages, functions=None, function_call=None, **kwargs):
    if hasattr(openai, "ChatCompletion"):
        payload = {"model": model, "messages": messages, **kwargs}
        if functions is not None:
            payload["functions"] = functions
        if function_call is not None:
            payload["function_call"] = function_call
        return openai.ChatCompletion.create(**payload)
    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        if functions is not None:
            tools = [{"type": "function", "function": fn} for fn in functions]
            tool_choice = "auto" if function_call in (None, "auto") else {"type": "function", "function": {"name": function_call}}
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                **kwargs
            )
        return client.chat.completions.create(model=model, messages=messages, **kwargs)
    raise RuntimeError("OpenAI client is not available.")
def create_anthropic_completion(model, messages, functions=None, function_call=None, **kwargs):
    client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
    
    payload = {
        "model": model,
        "max_tokens": kwargs.pop("max_tokens", 1024),
        "messages": messages,
        **kwargs
    }

    if functions is not None:
        payload["tools"] = [{"type": "function", "function": fn} for fn in functions]
        if function_call not in (None, "auto"):
            payload["tool_choice"] = {"type": "tool", "name": function_call}

    return client.messages.create(**payload)
def create_gemini_completion(model, messages, functions=None, function_call=None, **kwargs):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Convert OpenAI-style messages → Gemini contents
    contents = []
    system_instruction = None

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            system_instruction = content  # Gemini handles system prompts separately
            continue

        gemini_role = "model" if role == "assistant" else "user"
        contents.append(types.Content(
            role=gemini_role,
            parts=[types.Part(text=content)]
        ))

    # Build config
    config_kwargs = {**kwargs}
    # Remap OpenAI-style keys to Gemini equivalents
    if "max_tokens" in config_kwargs:
        config_kwargs["max_output_tokens"] = config_kwargs.pop("max_tokens")
    if "temperature" in config_kwargs:
        config_kwargs["temperature"] = config_kwargs.pop("temperature")
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    if functions is not None:
        fn_declarations = [
            types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=fn.get("parameters", {})
            )
            for fn in functions
        ]
        config_kwargs["tools"] = [types.Tool(function_declarations=fn_declarations)]

        if function_call not in (None, "auto"):
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=[function_call]
                )
            )

    config = types.GenerateContentConfig(**config_kwargs)

    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config
    )
def extract_message_content(response):
    try:
        if hasattr(response, "candidates"):
            candidate = response.candidates[0]
            part = candidate.content.parts[0]

            # Function call
            if hasattr(part, "function_call") and part.function_call:
                fn = part.function_call
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "name": fn.name,
                        "arguments": dict(fn.args)
                    }]
                }

            # Normal text
            return part.text

        # OpenAI-style dict (other providers)
        if isinstance(response, dict):
            return response["choices"][0]["message"]["content"]

    except TypeError:
        raise ValueError(f"Unrecognised response type: {type(response)}")
    return response.choices[0].message.content
def extract_function_call(message):
    if isinstance(message, dict):
        return message.get("function_call")
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        tool = tool_calls[0]
        return {"name": tool.function.name, "arguments": tool.function.arguments}
    return None
def main():
    app.run(debug=True)
if __name__ == "__main__":    
    main()