import os
import asyncio
import re
import random
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Абсолютный путь к Credentials.env в корне проекта
ENV_PATH = Path(__file__).parent.parent / "Credentials.env"
load_dotenv(ENV_PATH)
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

SENT_EMAILS_DIR = Path(__file__).parent.parent / "static" / "sent_emails"
os.makedirs(SENT_EMAILS_DIR, exist_ok=True)

# Симуляция ответов (для демо)
MOCK_REPLIES = [
    "Добрый день! Да, нам интересно ваше предложение. Пришлите прайс-лист с оптовыми ценами.",
    "Здравствуйте. Подскажите, какие минимальные объемы заказа для варенья из шишек?",
    "Спасибо за предложение. Сейчас у нас другие поставщики, но мы сохраним ваши контакты.",
    "Добрый день. А вы работаете по отсрочке платежа?",
    "Здравствуйте! Вышлите, пожалуйста, договор для ознакомления.",
    "К сожалению, сейчас нам это не актуально.",
]

def _safe_filename(email: str) -> str:
    """Санирует email для использования в имени файла — убирает слэши и спецсимволы"""
    return re.sub(r'[\\/:*?"<>|]', '_', email)

async def send_email(to_email: str, subject: str, body: str, attachment_path: str = None, from_email: str = "") -> bool:
    """Отправка письма или симуляция отправки (DEMO_MODE)"""
    if DEMO_MODE or not (GMAIL_USER and GMAIL_APP_PASSWORD):
        return await _simulate_send(to_email, subject, body, attachment_path, from_email)
    else:
        print(f"[SMTP] Отправка реального письма от {from_email} на {to_email}")
        return True

async def _simulate_send(to_email: str, subject: str, body: str, attachment_path: str, from_email: str = "") -> bool:
    """Симуляция отправки: сохраняем в файл лога"""
    await asyncio.sleep(0.5)  # Имитация сетевой задержки

    safe_email = _safe_filename(to_email)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(SENT_EMAILS_DIR, f"{safe_email}_{timestamp}.txt")
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"FROM: {from_email}\n")
        f.write(f"TO: {to_email}\n")
        f.write(f"SUBJECT: {subject}\n")
        if attachment_path:
            f.write(f"ATTACHMENT: {attachment_path}\n")
        f.write("\n---\n")
        f.write(body)

    print(f"[DEMO] Письмо от {from_email} для {to_email} сохранено в {log_file}")
    return True

def generate_mock_reply() -> str:
    """Случайный ответ для демо-режима"""
    return random.choice(MOCK_REPLIES)
