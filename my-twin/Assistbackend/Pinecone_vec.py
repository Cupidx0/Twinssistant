from pinecone import Pinecone
import os
import openai
from dotenv import load_dotenv
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("twins")
def get_embedding(text):
    response = openai.Embedding.create(
         input=text,
         model="text-embedding-3-small"  # cheap, fast, good enough
         dimensions = 512
    )
    return response['data'][0]['embedding']
 #def save_pattern(user_text, intent, confidence):
   #  embedding = get_embedding(user_text)
    # index.upsert([(user_text, embedding, {"intent": intent, "confidence": confidence})])
 #def find_pattern(user_text, threshold=0.85):
  #   embedding = get_embedding(user_text)
   #  results = index.query(vector=embedding, top_k=1, include_metadata=True)

   #  if results["matches"] and results["matches"][0]["score"] >= threshold:
    #     match = results["matches"][0]
    #     return match["metadata"]["intent"], match["metadata"]["confidence"]
 #
    # return None, None
print(index.describe_index_stats())