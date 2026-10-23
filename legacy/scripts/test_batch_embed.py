import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

# Test embed_content with list
try:
    print("Trying embed_content with list of strings...")
    resp = client.models.embed_content(
        model="gemini-embedding-2",
        contents=["hello", "world"]
    )
    print("embed_content returned:", len(resp.embeddings))
except Exception as e:
    print("Error:", e)

# Test if there is an embed_content_batch or something
try:
    print("Checking methods...")
    methods = [m for m in dir(client.models) if "embed" in m.lower()]
    print("Methods:", methods)
except Exception as e:
    print("Error:", e)
