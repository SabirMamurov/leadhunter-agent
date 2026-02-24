import os
import json
import re
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Абсолютный путь к Credentials.env в корне проекта
ENV_PATH = Path(__file__).parent.parent / "Credentials.env"
load_dotenv(ENV_PATH)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Мок-продукты Сибирского кедра
PRODUCTS = [
    {"name": "Кедровые орехи очищенные (500г)", "price": "1200 руб."},
    {"name": "Кедровое масло холодного отжима (250мл)", "price": "950 руб."},
    {"name": "Варенье из сосновых шишек (300г)", "price": "450 руб."},
    {"name": "Мармелад с кедровым орехом Ассорти", "price": "350 руб."},
    {"name": "Кедровый грильяж в шоколаде", "price": "550 руб."},
]

async def generate_email(company_name: str, category: str) -> dict:
    """Генерация персонализированного письма через OpenAI"""
    if not OPENAI_API_KEY:
        return _generate_mock_email(company_name)

    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # Берем 3 случайных продукта
    import random
    sample_products = random.sample(PRODUCTS, 3)
    products_text = "\n".join([f"- {p['name']} ({p['price']})" for p in sample_products])

    prompt = f"""Ты — менеджер по продажам компании "Сибирский кедр" (сайт: siberia.eco).
Твоя задача — написать коммерческое предложение для компании "{company_name}", которая занимается деятельностью в категории "{category}".
Цель: предложить нашу продукцию для их мероприятий (кейтеринг, фуршеты, подарки клиентам).

Требования к письму:
1. Письмо должно начинаться со слов: "Добрый день, компания {company_name}, к вам обращается компания «Сибирский кедр»."
2. Тон письма вежливый, профессиональный, побуждающий к сотрудничеству.
3. Вставь в тело письма следующие примеры нашей продукции:
{products_text}
4. Упомяни, что более подробная информация и полный ассортимент находятся в приложенном PDF-файле.
5. Заверши письмо призывом к действию (например, предложением созвониться или ответить на письмо).

Верни результат строго в формате JSON:
{{
  "subject": "Тема письма",
  "body": "Текст письма"
}}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000,
        )
        text = resp.choices[0].message.content.strip()
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        result = json.loads(text)
        return {
            "subject": result.get("subject", f"Сотрудничество с Сибирским кедром — {company_name}"),
            "body": result.get("body", _generate_mock_email(company_name)["body"])
        }
    except Exception as e:
        print(f"[ERROR] Ошибка генерации письма: {e}")
        return _generate_mock_email(company_name)

def _generate_mock_email(company_name: str) -> dict:
    body = f"""Добрый день, компания {company_name}, к вам обращается компания «Сибирский кедр».

Мы производим натуральную эко-продукцию из Сибири и хотим предложить вам сотрудничество при организации ваших мероприятий и фуршетов. 

Наши популярные позиции:
- Кедровые орехи очищенные (500г) (1200 руб.)
- Варенье из сосновых шишек (300г) (450 руб.)
- Мармелад с кедровым орехом Ассорти (350 руб.)

Полный ассортимент вы можете найти на нашем сайте siberia.eco, а также в приложенном PDF-каталоге.

Будем рады обсудить специальные оптовые условия для вашей компании. Ответьте на это письмо, если предложение вам интересно.

С уважением, 
Команда Сибирского кедра"""
    
    return {
        "subject": f"Эко-продукция для ваших мероприятий — Сибирский кедр x {company_name}",
        "body": body
    }
