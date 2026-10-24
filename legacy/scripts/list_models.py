import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

for model in client.models.list():
    name = model.name.lower()
    if "flash" in name or "pro" in name:
        print(model.name)
