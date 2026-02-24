import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "keitering.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    send_email = Column(String(255), nullable=False)   # email для отправки писем
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    companies = relationship("Company", back_populates="owner")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    category = Column(String(255), nullable=False)
    website = Column(String(500), default="")
    email = Column(String(255), default="")
    phone = Column(String(100), default="")
    address = Column(String(500), default="")
    description = Column(Text, default="")
    # Статусы: new → email_sent → replied → in_progress | interested | rejected | closed
    status = Column(String(50), default="new")
    email_subject = Column(String(500), default="")
    email_body = Column(Text, default="")
    reply_text = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    email_sent_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="companies")
    messages = relationship("ChatMessage", back_populates="company", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    direction = Column(String(20), nullable=False)  # "outgoing" | "incoming"
    author = Column(String(255), default="")        # имя отправителя
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="messages")


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
