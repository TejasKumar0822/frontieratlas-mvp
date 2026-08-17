import os
import httpx
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GEMINI_API_KEY")

if not key:
    raise RuntimeError("GEMINI_API_KEY is missing from .env")

url = (
    "https://generativelanguage.googleapis.com/"
    "v1/models/gemini-2.5-flash:generateContent"
)

response = httpx.post(
    url,
    headers={
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    },
    json={
        "contents": [
            {
                "parts": [
                    {
                        "text": "Reply with exactly: Gemini works"
                    }
                ]
            }
        ]
    },
    timeout=60,
)

print("HTTP STATUS:", response.status_code)
print("RESPONSE:")
print(response.text)