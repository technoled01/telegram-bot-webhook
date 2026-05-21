import os
import logging
import requests
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LOCAL_AUTH_KEY = os.getenv("LOCAL_AUTH_KEY")

if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, LOCAL_AUTH_KEY]):
    raise RuntimeError("Missing required environment variables")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Bot Sender", version="1.0.0")

# --- Логирование запросов (опционально) ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.method == "POST":
        body = await request.body()
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Raw body bytes: {body}")
    response = await call_next(request)
    return response

# --- Функция отправки в Telegram ---
def send_telegram_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get("ok"):
            logger.info(f"Message sent: {text[:50]}...")
            return True
        else:
            logger.error(f"Telegram API error: {result}")
            return False
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return False

# --- Модель для JSON-эндпоинта ---
class MessageRequest(BaseModel):
    auth_key: str
    message: str

# --- Эндпоинт для JSON (рекомендованный) ---
@app.post("/send", status_code=status.HTTP_200_OK)
async def send_message_json(request: MessageRequest):
    if request.auth_key != LOCAL_AUTH_KEY:
        raise HTTPException(status_code=401, detail="Invalid authorization key")
    success = send_telegram_message(request.message)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send message to Telegram")
    return {"status": "ok"}

# --- Эндпоинт для form-urlencoded (если нужен) ---
@app.post("/send_form", status_code=status.HTTP_200_OK)
async def send_message_form(request: Request):
    form = await request.form()
    auth_key = form.get("auth_key")
    message = form.get("message")
    if not auth_key or not message:
        raise HTTPException(status_code=400, detail="auth_key and message required")
    if auth_key != LOCAL_AUTH_KEY:
        raise HTTPException(status_code=401, detail="Invalid auth key")
    success = send_telegram_message(message)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send to Telegram")
    return {"status": "ok"}

# --- Проверка здоровья ---
@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {
        "service": "Telegram Bot Sender",
        "endpoints": {
            "/send": "POST JSON (auth_key, message)",
            "/send_form": "POST form-urlencoded",
            "/health": "GET"
        }
    }