import os
import re
from datetime import datetime
from Routing import create_chat_completion
from dotenv import load_dotenv
from Pinecone_vec import get_embedding, find_pattern, save_pattern
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAT_DIR = os.path.join(BASE_DIR, "chat")
user_chat_history = os.path.join(CHAT_DIR, "chat_history.txt")


def has_word(text, words):
    """Match whole words/phrases, not substrings ('hi' should not match 'this')."""
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


WEB_SEARCH_KEYWORDS = [
    "latest", "news", "search", "youtube", "today", "current", "year", "lyrics", "video", "videos", "google", "bing", "duckduckgo", "search engine",
    "music", "song", "songs", "weather", "sports", "football", "cricket", "president",
    "prime minister", "capital of", "country", "countries", "who is", "what is",
    "when is", "where is", "how to", "define"
]


def keyword_classify(user_text):
    text = user_text.lower()

    if has_word(text, [
        "good morning", "good afternoon", "good evening", "hello", "hi", "hey", "how are you"
    ]):
        return "greeting"

    if has_word(text, [
        "what are you", "who made you", "your name"
    ]):
        return "identity"

    if has_word(text, [
        "calendar", "schedule", "remind", "meeting", "event", "appointment", "book"
    ]):
        return "calendar"

    if has_word(text, [
        "cv", "resume", "cover letter", "job application", "rewrite my cv"
    ]):
        return "cv"

    if has_word(text, [
        "open", "launch", "play", "spotify", "file", "folder", "close", "quit"
    ]):
        return "mac_control"

    if has_word(text, [
        "code", "debug", "error", "function", "python", "react", "flask", "bug", "fix"
    ]):
        return "code"

    if has_word(text, WEB_SEARCH_KEYWORDS):
        return "web_search"

    return "casual"

# Matches one full turn block, tolerant of the leading space before Source/Timestamp
ENTRY_PATTERN = re.compile(
    r"User:\s*(?P<user>.*?)\n"
    r"Assistant:\s*(?P<assistant>.*?)\n"
    r"\s*Source:\s*(?P<source>.*?)\n"
    r"\s*Timestamp:\s*(?P<timestamp>.*?)(?=\nUser:|\Z)",
    re.DOTALL
)

def _load_entries():
    if not os.path.exists(user_chat_history):
        return []
    with open(user_chat_history, "r", encoding="utf-8") as f:
        content = f.read()
    entries = []
    for m in ENTRY_PATTERN.finditer(content):
        entries.append({
            "user": m.group("user").strip(),
            "assistant": m.group("assistant").strip(),
            "source": m.group("source").strip(),
            "timestamp": m.group("timestamp").strip(),
        })
    return entries

def memory_search(text, max_results=3):
    """Keyword-based episodic memory filter.
    Returns recent matching turns (dicts), most recent first.
    None if nothing matches (caller should escalate to Pinecone)."""
    keywords = lambda: keyword_classify(text)  # Lazy evaluation to avoid unnecessary calls
    matched_keywords = [
        kw for kw in keywords()
        if re.search(rf"\b{kw}\b", text, re.IGNORECASE)
    ]
    if not matched_keywords:
        return None

    pattern = re.compile(
        r"\b(" + "|".join(re.escape(kw) for kw in matched_keywords) + r")\b",
        re.IGNORECASE
    )

    entries = _load_entries()
    hits = []
    for entry in reversed(entries):  # most recent block last in file
        haystack = entry["user"] + " " + entry["assistant"]
        if pattern.search(haystack):
            hits.append(entry)
            if len(hits) >= max_results:
                break

    return hits or None