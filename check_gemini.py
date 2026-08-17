import os
import httpx
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GEMINI_API_KEY")

if not key:
    raise RuntimeError("GEMINI_API_KEY is not set in .env")

url = "https://generativelanguage.googleapis.com/v1beta/models"

response = httpx.get(
    url,
    headers={
        "x-goog-api-key": key
    },
    timeout=30,
)

response.raise_for_status()

data = response.json()

print("\nAvailable Gemini models:\n")

for model in data.get("models", []):
    name = model.get("name", "")
    methods = model.get("supportedGenerationMethods", [])

    if "generateContent" in methods:
        print(name)