import hashlib
import os

import openai
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()
if hasattr(openai, "OpenAI"):
    openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("twins")

# Only cache intents the classifier was actually confident about,
# otherwise low-confidence guesses get replayed as high-similarity matches.
SAVE_CONFIDENCE_THRESHOLD = 0.8


def get_embedding(user_text):
    response = openai_client.embeddings.create(
        input=user_text,
        model="text-embedding-3-small",
        dimensions=512,
    )
    return response.data[0].embedding


def save_pattern(user_text, intent, confidence):
    if confidence < SAVE_CONFIDENCE_THRESHOLD:
        return
    embedding = get_embedding(user_text)
    index.upsert(vectors=[{
        "id": hashlib.sha256(user_text.encode("utf-8")).hexdigest(),
        "values": embedding,
        "metadata": {
            "intent": intent,
            "confidence": confidence,
            "text": user_text,
        }
    }])


def find_pattern(user_text, threshold=0.85):
    embedding = get_embedding(user_text)
    results = index.query(vector=embedding, top_k=1, include_metadata=True)

    if results["matches"] and results["matches"][0]["score"] >= threshold:
        match = results["matches"][0]
        return match["metadata"]["intent"], match["metadata"]["confidence"]

    return None, None


if __name__ == "__main__":
    save_pattern("heyyy,how are you?", "greeting", 0.95)
    intent, confidence = find_pattern("hiiii,how are you?")
    print(f"Intent: {intent}, Confidence: {confidence}")
    print(index.describe_index_stats())
