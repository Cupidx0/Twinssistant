import os
import re
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from auth_utils import require_auth
from firebase_admin import firestore
from Routing import create_chat_completion, create_gemini_completion, extract_message_content
from dotenv import load_dotenv
from Pinecone_vec import get_embedding, find_pattern, save_pattern
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAT_DIR = os.path.join(BASE_DIR, "chat")
user_chat_history = os.path.join(CHAT_DIR, "chat_history.txt")
cred = credentials.Certificate("tw.json")
firebase_admin.initialize_app(cred)
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