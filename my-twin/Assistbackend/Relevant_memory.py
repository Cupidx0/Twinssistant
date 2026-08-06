import os
import re
from Assist import chat
from Routing import create_chat_completion
from dotenv import load_dotenv
from Pinecone_vec import get_embedding, find_pattern, save_pattern
load_dotenv()
user_chat_history = os.path.join(os.path.dirname(__file__), "chat_history.txt")
def keywords():
    """Return a list of keywords to look for in user input."""
    return [
        "weather", "news", "calendar", "reminder", "joke", "quote",
        "translate", "define", "synonym", "antonym", "math", "time",
        "date", "alarm", "timer", "music", "video", "image",
        "search", "map", "location", "direction", "flight",
        "hotel", "restaurant", "recipe"
    ]
def memory_search(text):
    for keyword in keywords():
        if re.search(rf"\b{keyword}\b", text, re.IGNORECASE):
            with open(user_chat_history, "r") as f:
                for t in f:
                    if keyword in t:
                        return t
    return None
#def hit_match():
