import random
import datetime
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gtts import gTTS
from deep_translator import GoogleTranslator

app = FastAPI(title="RU↔EN Translate & TTS")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Модели ---
class SpeakIn(BaseModel):
    text: str
    target_lang: Optional[str] = None  # "en"|"ru"

class TranslateIn(BaseModel):
    text: str
    target_lang: Optional[str] = None  # "en"|"ru"

# --- Вспомогательные функции ---
def pick_target_lang(text: str, target: Optional[str]) -> str:
    """
    Определяет целевой язык для перевода.
    Если target указан (en/ru), возвращаем его.
    Иначе: если текст на русском — en, иначе — ru
    """
    tgt = (target or "").lower()
    if tgt in ("en", "ru"):
        return tgt

    # Автоопределение через deep-translator
    try:
        detected = GoogleTranslator(source='auto', target='en').detect(text)
        # detected может вернуть 'ru' или 'en'
        return "en" if detected.startswith("ru") else "ru"
    except Exception:
        return "en"

def translate_text(text: str, target: str) -> str:
    """
    Перевод текста на target язык с помощью deep-translator
    """
    try:
        return GoogleTranslator(source='auto', target=target).translate(text)
    except Exception as e:
        raise RuntimeError(f"Translation failed: {e}")

# --- Эндпоинт /translate ---
@app.post("/translate")
def translate_endpoint(payload: TranslateIn):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    target = pick_target_lang(text, payload.target_lang)

    try:
        translated = translate_text(text, target)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Translate failed: {e}")

    return {
        "source_lang": "auto",
        "target_lang": target,
        "translated_text": translated,
    }

# --- Эндпоинт /speak ---
@app.post("/speak")
def speak_endpoint(payload: SpeakIn):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    target = pick_target_lang(text, payload.target_lang)

    try:
        translated = translate_text(text, target)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Translate failed: {e}")

    # Генерация MP3 через gTTS
    tts = gTTS(translated, lang=target)
    audio_bytes = BytesIO()
    tts.write_to_fp(audio_bytes)
    audio_bytes.seek(0)

    # Генерируем уникальное имя файла
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand_suffix = random.randint(1000, 9999)
    filename = f"speech_{target}_{timestamp}_{rand_suffix}.mp3"

    headers = {
        "Content-Type": "audio/mpeg",
        "Content-Disposition": f'attachment; filename="{filename}"'
    }

    return Response(content=audio_bytes.read(), media_type="audio/mpeg", headers=headers)
