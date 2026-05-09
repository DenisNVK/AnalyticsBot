import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не найден в .env")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY не найден в .env")

MODEL = "llama-3.3-70b-versatile"