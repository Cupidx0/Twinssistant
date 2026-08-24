import re
import os
import firebase_admin
from firebase_admin import credentials, firestore
from auth_utils import require_auth
cred = credentials.Certificate("tw.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHAT_DIR = os.path.join(BASE_DIR, "chat")
def parse_chat_txt(filepath):
    messages = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # split into turns only on "User:" at line start — that's the real boundary
    turns = re.split(r'\n(?=User:)', content.strip())

    for turn in turns:
        user_match = re.search(r'^User:\s*(.*?)(?=\nAssistant:|\Z)', turn, re.DOTALL)
        assistant_match = re.search(r'Assistant:\s*(.*?)(?=\n\s*Source:|\n\s*Timestamp:|\Z)', turn, re.DOTALL)
        source_match = re.search(r'Source:\s*(.*)', turn)
        timestamp_match = re.search(r'Timestamp:\s*(.*)', turn)
        if user_match and assistant_match:
            user_text = user_match.group(1).strip()
            assistant_text = assistant_match.group(1).strip()
            source = source_match.group(1).strip() if source_match else None
            timestamp = timestamp_match.group(1).strip() if timestamp_match else None
            messages.append({
                "user": user_text,
                "assistant": assistant_text,
                "category": "imported",
                "source": source,
                "clienttimestamp": timestamp
            })
    return messages
def upload_to_firestore(conversation_id, messages):
    batch = db.batch()
    conv_ref = db.collection('conversations').document(conversation_id)
    messages_ref = conv_ref.collection('messages')

    for msg in messages:
        doc_ref = messages_ref.document()
        batch.set(doc_ref, {
            "userId": None,
            **msg,
            "conversationId": conversation_id,
            'serverTimestamp': firestore.SERVER_TIMESTAMP
        })
    batch.commit()

messages = parse_chat_txt(os.path.join(CHAT_DIR, 'chat_history.txt'))
upload_to_firestore('imported_conv_1', messages)