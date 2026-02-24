import os
import json
import re
import asyncio
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Абсолютный путь к Credentials.env — работает независимо от CWD запуска
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_BASE_DIR, "Credentials.env"))

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

print(f"[search_agent] TAVILY_API_KEY present: {bool(TAVILY_API_KEY)}, OPENAI_API_KEY present: {bool(OPENAI_API_KEY)}")

# Настройки парсинга
_SCRAPE_TIMEOUT = 8          # Таймаут на загрузку страницы (сек)
_MAX_SCRAPE_PAGES = 8        # Максимум сайтов для параллельного парсинга
_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# Мусорные email-домены, которые нужно исключить
_JUNK_EMAIL_DOMAINS = {
    "example.com", "domain.com", "test.com", "email.com", "mail.com",
    "sentry.io", "wixpress.com", "cloudflare.com", "google.com",
    "yandex-team.ru", "2x.png", "png", "jpg", "jpeg", "gif",
}

# Мок-данные на случай отсутствия ключей
MOCK_COMPANIES = [
    {
        "name": "ООО «Вкус Праздника»",
        "website": "vkusprazdnika.ru",
        "email": "info@vkusprazdnika.ru",
        "phone": "+7 (495) 123-45-67",
        "address": "Москва, ул. Садовая, 15",
        "description": "Кейтеринговая компания, организация фуршетов и корпоративных мероприятий",
    },
    {
        "name": "ООО «Банкет Экспресс»",
        "website": "banket-express.ru",
        "email": "zakaz@banket-express.ru",
        "phone": "+7 (495) 234-56-78",
        "address": "Москва, Ленинский пр-т, 42",
        "description": "Выездное обслуживание мероприятий, кофе-паузы, банкеты",
    },
    {
        "name": "ИП Смирнов А.В. (CaterPro)",
        "website": "caterpro.ru",
        "email": "contact@caterpro.ru",
        "phone": "+7 (499) 345-67-89",
        "address": "Москва, ул. Тверская, 8",
        "description": "Профессиональный кейтеринг для конференций и корпоративов",
    },
    {
        "name": "ООО «Гастроном Events»",
        "website": "gastronom-events.ru",
        "email": "info@gastronom-events.ru",
        "phone": "+7 (495) 456-78-90",
        "address": "Москва, Арбат, 20",
        "description": "Кейтеринг премиум-класса, фуршеты, шведский стол",
    },
    {
        "name": "ООО «Сытый Офис»",
        "website": "sitiy-ofis.ru",
        "email": "order@sitiy-ofis.ru",
        "phone": "+7 (495) 567-89-01",
        "address": "Москва, ул. Профсоюзная, 55",
        "description": "Корпоративное питание и кейтеринг для офисов",
    },
]


def _clean_url(url: str) -> str:
    """Возвращает базовый URL (схема + хост) без trailing slash."""
    match = re.match(r"(https?://[^/]+)", url)
    return match.group(1).rstrip("/") if match else url


def _filter_emails(raw_emails: List[str]) -> List[str]:
    """Фильтрует технические / мусорные email-адреса."""
    result = []
    seen = set()
    for email in raw_emails:
        email = email.lower().strip(".,;:\"'")
        domain = email.split("@")[-1]
        ext = domain.rsplit(".", 1)[-1] if "." in domain else ""
        if (
            email not in seen
            and domain not in _JUNK_EMAIL_DOMAINS
            and ext not in {"png", "jpg", "jpeg", "gif", "svg", "webp", "js", "css"}
            and len(email) <= 80
            and "noreply" not in email
            and "no-reply" not in email
            and "example" not in email
        ):
            seen.add(email)
            result.append(email)
    return result


async def _scrape_emails_from_url(url: str) -> List[str]:
    """
    Загружает страницу и ищет email-адреса в HTML.
    Пробует главную страницу, потом /contacts или /contact.
    """
    try:
        import httpx
    except ImportError:
        return []

    base = _clean_url(url)
    pages_to_try = [url, f"{base}/contacts", f"{base}/contact", f"{base}/о-компании"]
    found: List[str] = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=_SCRAPE_TIMEOUT,
        follow_redirects=True,
        verify=False,          # Некоторые сайты используют самоподписанные сертификаты
    ) as client:
        for page_url in pages_to_try:
            try:
                resp = await client.get(page_url, headers=headers)
                if resp.status_code == 200:
                    text = resp.text
                    emails = _EMAIL_REGEX.findall(text)
                    filtered = _filter_emails(emails)
                    found.extend(filtered)
                    # Если нашли что-то на главной — контакты дополнительно проверим
                    if filtered and page_url == url:
                        continue
                    elif filtered:
                        break
            except Exception:
                pass  # Страница недоступна = пропускаем молча

    return _filter_emails(found)  # финальная дедупликация


async def _enrich_results_with_emails(results: list) -> list:
    """
    Параллельно парсит сайты из результатов Tavily и добавляет найденные email
    в каждый результат под ключом '_scraped_emails'.
    """
    urls = [r.get("url", "") for r in results[:_MAX_SCRAPE_PAGES]]
    print(f"[Scraper] Параллельный парсинг {len(urls)} сайтов...")

    tasks = [_scrape_emails_from_url(u) for u in urls]
    email_lists = await asyncio.gather(*tasks, return_exceptions=True)

    enriched = []
    for i, result in enumerate(results):
        r = dict(result)
        if i < len(email_lists) and isinstance(email_lists[i], list):
            emails = email_lists[i]
            r["_scraped_emails"] = emails
            if emails:
                print(f"[Scraper] [OK] {r.get('url', '')[:60]}: {emails[:3]}")
            else:
                print(f"[Scraper] [--] {r.get('url', '')[:60]}: email ne nayden")
        else:
            r["_scraped_emails"] = []
        enriched.append(r)

    return enriched


async def search_companies(category: str, max_results: int = 10) -> List[Dict]:
    """Поиск компаний по категории через Tavily API или мок-данные.

    Ожидаемый формат category: 'Название компании Город'
    Например: 'Кейтеринг Томск' или 'Доставка еды Новосибирск'
    """
    if TAVILY_API_KEY:
        try:
            return await _search_via_tavily(category, max_results)
        except Exception as e:
            print(f"[ERROR] Tavily недоступен, переключаемся на мок-данные: {e}")
            return MOCK_COMPANIES[:max_results]
    else:
        print("[WARN] TAVILY_API_KEY не задан, используются мок-данные")
        return MOCK_COMPANIES[:max_results]


async def _search_via_tavily(category: str, max_results: int) -> List[Dict]:
    """Реальный поиск через Tavily REST API (httpx, без SDK) + парсинг email."""
    import httpx

    query = f"{category} компания контакты сайт официальный"
    print(f"[Tavily] Поиск: {query}")

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    print(f"[Tavily] Получено результатов: {len(results)}")

    if not results:
        print("[WARN] Tavily вернул 0 результатов, используем мок-данные")
        return MOCK_COMPANIES[:max_results]

    # ── Шаг 2: параллельный парсинг email со всех найденных сайтов ──
    enriched_results = await _enrich_results_with_emails(results)

    # ── Шаг 3: структурируем данные через OpenAI (или без него) ──
    companies: List[Dict] = []
    if OPENAI_API_KEY and enriched_results:
        companies = await _extract_companies_with_ai(enriched_results, category)
    else:
        for r in enriched_results[:max_results]:
            scraped = r.get("_scraped_emails", [])
            companies.append({
                "name": r.get("title", "Неизвестная компания"),
                "website": r.get("url", ""),
                "email": scraped[0] if scraped else "",
                "phone": "",
                "address": "",
                "description": r.get("content", "")[:300],
            })

    return companies if companies else MOCK_COMPANIES[:max_results]


async def _extract_companies_with_ai(results: list, category: str) -> List[Dict]:
    """Извлечение структурированных данных о компаниях через OpenAI.
    В отличие от предыдущей версии, здесь результаты содержат '_scraped_emails'
    — реальные email-адреса, найденные непосредственно на сайтах компаний.
    """
    from openai import OpenAI

    oai = OpenAI(api_key=OPENAI_API_KEY)

    # Формируем сниппеты с учётом найденных email
    snippet_parts = []
    for i, r in enumerate(results[:_MAX_SCRAPE_PAGES]):
        scraped_emails = r.get("_scraped_emails", [])
        email_line = (
            f"Email-адреса найденные на сайте: {', '.join(scraped_emails[:5])}"
            if scraped_emails
            else "Email-адреса на сайте: не найдены"
        )
        snippet_parts.append(
            f"Источник {i+1}: {r.get('title', '')}\n"
            f"URL: {r.get('url', '')}\n"
            f"{email_line}\n"
            f"Описание: {r.get('content', '')[:600]}"
        )

    snippets = "\n\n".join(snippet_parts)

    prompt = f"""Ты — помощник по извлечению данных о компаниях.
На основе следующих результатов поиска по запросу "{category}" извлеки список РЕАЛЬНЫХ компаний.

ВАЖНЫЕ ПРАВИЛА:
1. Для каждого «Источника» — только ОДНА компания в результирующем массиве.
2. Поле "email" ОБЯЗАТЕЛЬНО бери ТОЛЬКО из «Email-адреса найденные на сайте». Не придумывай email.
3. Если email не найден — оставь пустую строку "".
4. Название компании должно быть официальным (с юридической формой ООО/ИП/АО если видно).
5. Исключай агрегаторы (2GIS, Yandex Maps, Avito и т.п.) — они не являются компаниями.

Для каждой компании верни JSON-объект с полями:
- name: полное название компании
- website: URL сайта
- email: email-адрес (только из данных выше, иначе "")
- phone: телефон (если есть в описании, иначе "")
- address: адрес (если есть в описании, иначе "")
- description: краткое описание деятельности (1-2 предложения)

Верни ТОЛЬКО валидный JSON-массив. Не добавляй пояснений.

Результаты поиска:
{snippets}
"""

    try:
        resp = oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=3000,
        )
        text = resp.choices[0].message.content.strip()
        # Убираем возможные ```json блоки
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        companies = json.loads(text)
        if not isinstance(companies, list):
            return []

        # ── Постобработка: если AI не вставил scraped email — вставляем сами ──
        url_to_emails: Dict[str, List[str]] = {
            r.get("url", ""): r.get("_scraped_emails", []) for r in results
        }
        for comp in companies:
            if not comp.get("email"):
                site = comp.get("website", "")
                # Ищем по совпадению хоста
                for url, emails in url_to_emails.items():
                    if emails and (_clean_url(site) == _clean_url(url) or site in url):
                        comp["email"] = emails[0]
                        break

        return companies
    except Exception as e:
        print(f"[ERROR] Ошибка OpenAI извлечения: {e}")
        return []
