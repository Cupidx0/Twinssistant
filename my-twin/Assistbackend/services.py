"""Lazily created shared clients (Firestore, Pinecone, OpenAI, Anthropic, Tavily).

Created on first use so pure helpers in other modules can be imported and
unit-tested without credentials.
"""
import os
import threading

from dotenv import load_dotenv

load_dotenv()

_lock = threading.Lock()
_clients = {}


def _get(name, factory):
    if name not in _clients:
        with _lock:
            if name not in _clients:
                _clients[name] = factory()
    return _clients[name]


def db():
    def make():
        from auth_utils import init_firebase
        _, client = init_firebase()
        return client
    return _get("db", make)


def pinecone_index():
    def make():
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        return pc.Index(os.getenv("PINECONE_INDEX", "twins"))
    return _get("pinecone", make)


def openai_client():
    def make():
        from openai import OpenAI
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _get("openai", make)


def anthropic_client():
    def make():
        import anthropic
        # The project historically used CLAUDE_API_KEY; ANTHROPIC_API_KEY is the SDK default.
        key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    return _get("anthropic", make)


def tavily_client():
    def make():
        from tavily import TavilyClient
        return TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return _get("tavily", make)


def env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


OWNER_UIDS = {u.strip() for u in os.getenv("OWNER_UIDS", "").split(",") if u.strip()}
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "claude-haiku-5-5")
MODEL_MAIN = os.getenv("MODEL_MAIN", "claude-sonnet-5-5")
MODEL_TOP = os.getenv("MODEL_TOP", "claude-opus-5-5")
