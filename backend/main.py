import os
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import List, Optional

from .database import engine, Base, get_db, Company, User, ChatMessage, create_tables
from .search_agent import search_companies
from .email_generator import generate_email
from .email_sender import send_email, generate_mock_reply
from .pdf_generator import generate_catalog_pdf
from .auth import hash_password, verify_password, create_access_token, decode_token

app = FastAPI(title="Keitering Sales Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

create_tables()

# Раздаём фронтенд
_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(_FRONTEND_DIR, "index.html"))

# ─────────────────────────────────────────────
# Pydantic схемы
# ─────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    send_email: str          # почта для отправки писем
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class SearchRequest(BaseModel):
    category: str

class UpdateStatusRequest(BaseModel):
    status: str

class ChatMessageRequest(BaseModel):
    text: str
    direction: str = "outgoing"   # "outgoing" | "incoming"

# ─────────────────────────────────────────────
# Утилита: извлечь текущего пользователя из JWT
# ─────────────────────────────────────────────

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Не авторизован")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user

# ─────────────────────────────────────────────
# Авторизация
# ─────────────────────────────────────────────

@app.post("/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    user = User(
        name=req.name,
        email=req.email,
        send_email=req.send_email,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.email)
    return {"token": token, "user": {"id": user.id, "name": user.name, "email": user.email, "send_email": user.send_email}}


@app.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    token = create_access_token(user.id, user.email)
    return {"token": token, "user": {"id": user.id, "name": user.name, "email": user.email, "send_email": user.send_email}}


@app.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "name": current_user.name, "email": current_user.email, "send_email": current_user.send_email}

# ─────────────────────────────────────────────
# Компании
# ─────────────────────────────────────────────

def _company_dict(c: Company):
    return {
        "id": c.id,
        "owner_id": c.owner_id,
        "name": c.name,
        "category": c.category,
        "website": c.website,
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "description": c.description,
        "status": c.status,
        "email_subject": c.email_subject,
        "email_body": c.email_body,
        "reply_text": c.reply_text,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "email_sent_at": c.email_sent_at.isoformat() if c.email_sent_at else None,
        "messages_count": len(c.messages),
    }


@app.get("/companies")
def get_companies(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Company).filter(Company.owner_id == current_user.id)
    if status:
        q = q.filter(Company.status == status)
    return [_company_dict(c) for c in q.order_by(Company.id.desc()).all()]


@app.post("/search")
async def start_search(
    req: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = await search_companies(req.category, max_results=8)
    added = []
    for r in results:
        existing = None
        if r.get("email"):
            existing = db.query(Company).filter(
                Company.email == r["email"],
                Company.owner_id == current_user.id,
            ).first()
        if not existing:
            existing = db.query(Company).filter(
                Company.name == r["name"],
                Company.owner_id == current_user.id,
            ).first()
        if not existing:
            c = Company(
                owner_id=current_user.id,
                name=r.get("name"),
                category=req.category,
                website=r.get("website"),
                email=r.get("email") or f"info@{r.get('website','unknown.com').replace('https://','').split('/')[0]}",
                phone=r.get("phone"),
                address=r.get("address"),
                description=r.get("description"),
                status="new",
            )
            db.add(c)
            added.append(c)
    db.commit()
    return {"message": f"Найдено и добавлено {len(added)} новых компаний.", "total_found": len(results)}


@app.post("/generate-email/{company_id}")
async def preview_email(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comp = db.query(Company).filter(Company.id == company_id, Company.owner_id == current_user.id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    email_data = await generate_email(comp.name, comp.category)
    comp.email_subject = email_data["subject"]
    comp.email_body = email_data["body"]
    db.commit()
    return email_data


@app.post("/send-email/{company_id}")
async def send_to_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comp = db.query(Company).filter(Company.id == company_id, Company.owner_id == current_user.id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    if not comp.email_body:
        email_data = await generate_email(comp.name, comp.category)
        comp.email_subject = email_data["subject"]
        comp.email_body = email_data["body"]

    pdf_path = generate_catalog_pdf()
    # Используем send_email пользователя как отправителя
    success = await send_email(
        comp.email, comp.email_subject, comp.email_body, pdf_path,
        from_email=current_user.send_email
    )
    if success:
        comp.status = "email_sent"
        comp.email_sent_at = datetime.utcnow()
        # Сохраняем письмо в чат как исходящее сообщение
        msg = ChatMessage(
            company_id=comp.id,
            direction="outgoing",
            author=current_user.name,
            text=f"📧 **Тема:** {comp.email_subject}\n\n{comp.email_body}",
        )
        db.add(msg)
        db.commit()
        return {"message": "Письмо успешно отправлено"}
    else:
        raise HTTPException(status_code=500, detail="Ошибка при отправке письма")


@app.post("/send-all")
async def send_to_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    companies = db.query(Company).filter(
        Company.owner_id == current_user.id,
        Company.status == "new",
    ).all()
    if not companies:
        return {"message": "Нет новых компаний для рассылки"}

    pdf_path = generate_catalog_pdf()
    sent_count = 0
    skipped_no_email = 0
    failed_count = 0

    for comp in companies:
        # Пропускаем компании без реального email или с явно поддельным
        email_val = (comp.email or "").strip()
        has_real_email = (
            "@" in email_val
            and "unknown.com" not in email_val
            and "example.com" not in email_val
            and len(email_val) > 5
        )
        if not has_real_email:
            skipped_no_email += 1
            continue

        # Генерируем письмо если ещё не сгенерировано
        if not comp.email_body:
            email_data = await generate_email(comp.name, comp.category)
            comp.email_subject = email_data["subject"]
            comp.email_body = email_data["body"]

        success = await send_email(
            email_val, comp.email_subject, comp.email_body, pdf_path,
            from_email=current_user.send_email
        )
        if success:
            comp.status = "email_sent"
            comp.email_sent_at = datetime.utcnow()
            db.add(ChatMessage(
                company_id=comp.id,
                direction="outgoing",
                author=current_user.name,
                text=f"📧 **Тема:** {comp.email_subject}\n\n{comp.email_body}",
            ))
            sent_count += 1
        else:
            failed_count += 1

    db.commit()

    parts = [f"Отправлено: {sent_count}"]
    if skipped_no_email:
        parts.append(f"без email: {skipped_no_email}")
    if failed_count:
        parts.append(f"ошибка отправки: {failed_count}")
    return {"message": " | ".join(parts)}


@app.put("/company/{company_id}/status")
async def update_status(
    company_id: int,
    req: UpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    valid = ["new", "email_sent", "replied", "in_progress", "interested", "rejected", "closed"]
    if req.status not in valid:
        raise HTTPException(status_code=400, detail="Неверный статус")
    comp = db.query(Company).filter(Company.id == company_id, Company.owner_id == current_user.id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    comp.status = req.status
    db.commit()
    return {"message": f"Статус изменён на {req.status}"}

# ─────────────────────────────────────────────
# Чат-переписка
# ─────────────────────────────────────────────

@app.get("/company/{company_id}/messages")
def get_messages(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comp = db.query(Company).filter(Company.id == company_id, Company.owner_id == current_user.id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return [
        {
            "id": m.id,
            "direction": m.direction,
            "author": m.author,
            "text": m.text,
            "created_at": m.created_at.isoformat(),
        }
        for m in comp.messages
    ]


@app.post("/company/{company_id}/messages")
def send_message(
    company_id: int,
    req: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comp = db.query(Company).filter(Company.id == company_id, Company.owner_id == current_user.id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    msg = ChatMessage(
        company_id=company_id,
        direction=req.direction,
        author=current_user.name if req.direction == "outgoing" else comp.name,
        text=req.text,
    )
    db.add(msg)
    # Если добавляем входящее сообщение — обновляем статус
    if req.direction == "incoming" and comp.status == "email_sent":
        comp.status = "replied"
        comp.replied_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)
    return {
        "id": msg.id,
        "direction": msg.direction,
        "author": msg.author,
        "text": msg.text,
        "created_at": msg.created_at.isoformat(),
    }


@app.post("/simulate-reply/{company_id}")
async def simulate_reply(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comp = db.query(Company).filter(Company.id == company_id, Company.owner_id == current_user.id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    if comp.status != "email_sent":
        raise HTTPException(status_code=400, detail="Сначала нужно отправить письмо!")
    reply_text = generate_mock_reply()
    comp.status = "replied"
    comp.replied_at = datetime.utcnow()
    comp.reply_text = reply_text
    msg = ChatMessage(
        company_id=comp.id,
        direction="incoming",
        author=comp.name,
        text=reply_text,
    )
    db.add(msg)
    db.commit()
    return {"message": "Ответ получен!", "reply": reply_text}
