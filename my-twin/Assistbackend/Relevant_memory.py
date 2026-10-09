import os
import re
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from auth_utils import require_auth,init_firebase
from firebase_admin import firestore
from Routing import create_chat_completion, create_gemini_completion, extract_message_content
from dotenv import load_dotenv
from pc_connect import close_app, open_app, list_files, read_file, get_system_info ,open_url
from Pinecone_vec import get_embedding, find_pattern, save_pattern
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAT_DIR = os.path.join(BASE_DIR, "chat")
user_chat_history = os.path.join(CHAT_DIR, "chat_history.txt")
firebase_app = init_firebase()
db = firestore.client()

def has_word(text, words):
    """Match whole words/phrases, not substrings ('hi' should not match 'this')."""
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


WEB_SEARCH_KEYWORDS = [
    "latest", "news", "search", "youtube", "today", "current", "year", "lyrics", "video", "videos", "google", "bing", "duckduckgo", "search engine",
    "music", "song", "songs", "weather", "sports", "football", "cricket", "president",
    "prime minister", "capital of", "country", "countries", "who is", "what is",
    "when is", "where is", "how to", "define"
]
LAPTOP_TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open/launch an application on the user's Mac. Note: the camera app is 'Photo Booth'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the app, e.g. 'Spotify', 'Safari'"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Close/quit an application on the user's Mac.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the app to close"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory on the user's Mac.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Path, e.g. '~/Downloads'"}
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the text content of a file on the user's Mac.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full or ~-relative path to the file"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in the default web browser on the user's Mac.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to open, e.g. 'https://www.example.com'"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Get basic system/platform info about the user's Mac.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]
def resolve_and_run_laptop_tool(user_text: str):
    response = create_chat_completion(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "You are a helpful assistant that can perform tasks on the user's Mac. "
                "Based on the user's request, determine which tool to use and provide the necessary arguments. "
                "If you cannot determine a tool, respond with an error message."
            )},
            {"role": "user", "content": user_text}
        ],
        tools=LAPTOP_TOOL_SCHEMA,
        tool_choice="auto",
        temperature=0.2,
    )

    message = response.choices[0].message
    if not message.tool_calls:
        return {"success": False, "error": "Could not resolve laptop tool intent"}

    call = message.tool_calls[0]
    tool_name = call.function.name
    try:
        args = json.loads(call.function.arguments)
    except json.JSONDecodeError:
        args = {}

    return handle_laptop_tool_intent(tool_name, **args)
MAC_APP_NAMES = [
    "spotify", "safari", "chrome", "google chrome", "firefox", "finder", "notes", "music",
    "photo booth", "camera", "terminal", "slack", "discord", "whatsapp", "mail", "messages",
    "facetime", "preview", "vs code", "visual studio code", "xcode", "word", "excel",
    "powerpoint", "zoom", "teams", "photos", "app store", "system settings", "calculator",
]
_LAPTOP_VERB = r"(?:open|launch|start|close|quit|kill)"
LAPTOP_PATTERNS = [
    # "open spotify", "can you close the safari app"
    rf"\b{_LAPTOP_VERB}\s+(?:up\s+)?(?:the\s+|my\s+)?(?:{'|'.join(re.escape(a) for a in MAC_APP_NAMES)})\b",
    # "open the X app", "quit X application"
    rf"\b{_LAPTOP_VERB}\s+(?:up\s+)?(?:the\s+|my\s+)?[\w .]{{1,30}}?\s+(?:app|application)\b",
    # "open https://...", "open www.example.com"
    r"\bopen\s+(?:https?://|www\.)",
    # "list files in ~/Downloads", "show me my files", "what's in my downloads"
    r"\b(?:list|show)\b(?:\s+\w+){0,3}?\s+(?:files|folders)\b",
    r"\bwhat(?:'s| is)\s+in\s+(?:my\s+)?(?:~/\S*|downloads|documents|desktop|home folder)",
    # "read the file notes.txt", "read ~/todo.md"
    r"\b(?:read|open)\s+(?:the\s+|my\s+)?file\b",
    r"\bread\s+~/",
    r"\bsystem info(?:rmation)?\b",
]
_LAPTOP_RE = re.compile("|".join(LAPTOP_PATTERNS))

def is_laptop_command(text):
    """True only for explicit Mac-control commands."""
    return bool(_LAPTOP_RE.search(text.lower()))

TOOL_MAP = {
        "open_app": open_app,
        "list_files": list_files,
        "read_file": read_file,
        "open_url": open_url,
        "system_info": get_system_info,
        "close_app": close_app
    }
def keyword_classify(user_text):
    text = user_text.lower()

    # Checked first: the patterns only match explicit commands, so they can't
    # swallow ordinary questions like "what file format should I use?".
    if is_laptop_command(text):
        return "mac_tool"

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
        "code", "debug", "error", "function", "python", "react", "flask", "bug", "fix"
    ]):
        return "code"

    if has_word(text, WEB_SEARCH_KEYWORDS):
        return "web_search"

    return "casual"

# Matches one full turn block, tolerant of the leading space before Source/Timestamp
ENTRY_PATTERN = re.compile(
    r"User:\s*(?P<user>.*?)\n"
    r"Assistant:\s*(?P<assistant>.*?)(?:\n\s*Source:\s*(?P<source>.*?))?"
    r"(?:\n\s*Timestamp:\s*(?P<timestamp>.*?))?"
    r"(?=\nUser:|\Z)",
    re.DOTALL
)
def extract_keywords(text):
    text = text.lower()
    words = re.findall(r"[a-zA-Z0-9']+", text)
    # remove stopwords and short words
    stopwords = {"the", "a", "an", "is", "it", "to", "of", "in", "on", "for", "what", "who", "how", "do", "you", "your", "me", "my", "his", "her"}
    return [w for w in words if len(w) > 2 and w not in stopwords] 

def get_conversation(conversation_id):
    messages_ref = db.collection('conversations').document(conversation_id) \
                      .collection('messages') \
                      .order_by('clienttimestamp')  # or 'clientTimestamp' if you trust that more

    messages = []
    for doc in messages_ref.stream():
        data = doc.to_dict()
        data['id'] = doc.id
        messages.append(data)

    return messages

def _load_entries():
    try:
        history = get_conversation('imported_conv_1')
        for msg in history:
            print(f"{msg['user']}: {msg['assistant']} (Source: {msg.get('source', 'N/A')}, Timestamp: {msg.get('clienttimestamp', 'N/A')})")
        entries = []
        for m in ENTRY_PATTERN.finditer('\n'.join([f"User: {msg['user']}\nAssistant: {msg['assistant']}\nSource: {msg.get('source', '')}\nTimestamp: {msg.get('clienttimestamp', '')}" for msg in history])):
            entries.append({
                "user": m.group("user"),
                "assistant": m.group("assistant"),
                "source": m.group("source"),
                "timestamp": m.group("timestamp"),
            })
    except Exception as e:
        print(f"Error loading conversation from Firestore: {e}")
        if not os.path.exists(user_chat_history):
            return []
        with open(user_chat_history, "r", encoding="utf-8") as f:
            content = f.read()
        entries = []
        for m in ENTRY_PATTERN.finditer(content ):
            entries.append({
                "user": m.group("user"),
                "assistant": m.group("assistant"),
                "source": m.group("source"),
                "timestamp": m.group("timestamp"),
            })
    return entries

def memory_search(text, max_results=5):
    """Keyword-based episodic memory filter.
    Returns recent matching turns (dicts), most recent first.
    None if nothing matches (caller should escalate to Pinecone)."""
    """keywords = lambda: keyword_classify(text)  # Lazy evaluation to avoid unnecessary calls
    matched_keywords = [
        kw for kw in keywords()
        if re.search(rf"\b{kw}\b", text, re.IGNORECASE)
    ]
    if not matched_keywords:
        return None"""
    terms = extract_keywords(text)
    if not terms:
        return None

    pattern = re.compile(
        r"\b(" + "|".join(re.escape(kw) for kw in terms) + r")\b",
        re.IGNORECASE
    )

    entries = _load_entries()
    hits = []
    for entry in reversed(entries):  # most recent block last in file
         haystack = f"{entry['user']} {entry['assistant']} {entry['timestamp']}"
         if pattern.search(haystack):
            hits.append(entry)
            if len(hits) >= max_results:
                break

    return hits or None

MAX_LISTED_FILES = 50

def describe_laptop_tool_result(tool_name, result):
    """Turn a tool's raw result dict into a reply the user can read."""
    if result.get("message"):
        return result["message"]
    if tool_name == "list_files":
        files = sorted(result.get("files", []), key=str.lower)
        if not files:
            return "That folder is empty."
        shown = ", ".join(files[:MAX_LISTED_FILES])
        extra = len(files) - MAX_LISTED_FILES
        more = f", and {extra} more" if extra > 0 else ""
        return f"{len(files)} item{'s' if len(files) != 1 else ''}: {shown}{more}."
    if tool_name == "read_file":
        content = result.get("content", "")
        if not content.strip():
            return "The file is empty."
        return f"Here's the file:\n\n```\n{content}\n```"
    if tool_name == "system_info":
        return (f"System: {result.get('platform', 'unknown')} {result.get('release', '')}"
                f" ({result.get('machine', 'unknown')}).")
    return "Done."

def handle_laptop_tool_intent(tool_name: str, **kwargs):
    fn = TOOL_MAP.get(tool_name)
    if not fn:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
    try:
        result = fn(**kwargs)
    except TypeError as e:  # model sent arguments the tool doesn't accept
        return {"success": False, "error": f"Bad arguments for {tool_name}: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    if result.get("success"):
        result["message"] = describe_laptop_tool_result(tool_name, result)
    return result
def memo_gpt(text):
    """Search for relevant past conversations in chat history and return a concise summary."""
    memoir = memory_search(text)
    response = create_gemini_completion(
            model="gemini-3.1-flash-lite",
            messages=[
                {"role": "system", "content": (
                        "You are a helpful assistant that searches for relevant past conversations. "
                        "focus more on the users info and not assistant info,if its based on users needs and wants, and if the user has asked for something similar in the past, you should return that info to the user. "
                        "strip out the answer instead of a sentence use e.g 21 years old for age or 5.11 for height and 70kg for weight, and if the user has asked for something similar in the past, you should return that info to the user. "
                        "Return a concise summary of any relevant past exchanges."
                        f"Use information from the following past conversations: {memoir if memoir else 'None'}"
                )},
                {"role": "user", "content": f"Search for relevant past conversations from{memoir} related to: '{text}'"}
            ],
            max_tokens=2048,
            temperature=0.7
        )
    memory_searcher = extract_message_content(response).strip()
    return memory_searcher