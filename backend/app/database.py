"""
SQLite persistence layer — sessions, datasets, and messages survive server restarts.

Uses SQLAlchemy async with aiosqlite. The database file lives at data/sessions.db
(configurable via DATABASE_URL in .env).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    pass


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DatasetModel(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    rows = Column(Integer, default=0)
    columns = Column(Integer, default=0)
    column_names = Column(Text, default="[]")
    dtypes = Column(Text, default="{}")
    size_bytes = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ─── Engine & Session Factory ────────────────────────────────────────────────

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_db_file = _BACKEND_ROOT / "data" / "sessions.db"
_db_file.parent.mkdir(parents=True, exist_ok=True)
_db_url = f"sqlite+aiosqlite:///{_db_file}"

_engine = create_async_engine(_db_url, echo=False)
async_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_initialized", path=str(_db_file))


async def get_db() -> AsyncSession:
    """Get a new async session (caller must close/commit)."""
    return async_session_factory()


# ─── Dataset Helpers ─────────────────────────────────────────────────────────

async def save_dataset_metadata(
    dataset_id: str,
    filename: str,
    file_path: str,
    rows: int,
    columns: int,
    column_names: list[str],
    dtypes: dict[str, str],
    size_bytes: int,
    session_id: str | None = None,
) -> None:
    async with async_session_factory() as db:
        dataset = DatasetModel(
            id=dataset_id,
            session_id=session_id,
            filename=filename,
            file_path=file_path,
            rows=rows,
            columns=columns,
            column_names=json.dumps(column_names),
            dtypes=json.dumps(dtypes),
            size_bytes=size_bytes,
        )
        db.add(dataset)
        await db.commit()


async def delete_dataset_metadata(dataset_id: str) -> None:
    async with async_session_factory() as db:
        await db.execute(delete(DatasetModel).where(DatasetModel.id == dataset_id))
        await db.commit()


async def load_all_datasets() -> list[DatasetModel]:
    async with async_session_factory() as db:
        result = await db.execute(select(DatasetModel))
        return list(result.scalars().all())


# ─── Session Helpers ─────────────────────────────────────────────────────────

async def create_session(session_id: str, title: str | None = None) -> SessionModel:
    async with async_session_factory() as db:
        session = SessionModel(id=session_id, title=title)
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session


async def get_session(session_id: str) -> SessionModel | None:
    async with async_session_factory() as db:
        result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
        return result.scalar_one_or_none()


async def list_sessions() -> list[SessionModel]:
    async with async_session_factory() as db:
        result = await db.execute(select(SessionModel).order_by(SessionModel.updated_at.desc()))
        return list(result.scalars().all())


async def delete_session(session_id: str) -> bool:
    async with async_session_factory() as db:
        result = await db.execute(delete(SessionModel).where(SessionModel.id == session_id))
        await db.commit()
        return result.rowcount > 0


async def touch_session(session_id: str) -> None:
    """Update the updated_at timestamp for a session."""
    async with async_session_factory() as db:
        result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            session.updated_at = datetime.now(timezone.utc)
            await db.commit()


# ─── Message Helpers ─────────────────────────────────────────────────────────

async def save_message(
    message_id: str,
    session_id: str,
    role: str,
    content: str | None,
) -> None:
    async with async_session_factory() as db:
        msg = MessageModel(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
        )
        db.add(msg)
        await db.commit()


async def load_messages(session_id: str) -> list[MessageModel]:
    async with async_session_factory() as db:
        result = await db.execute(
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at)
        )
        return list(result.scalars().all())


async def count_messages(session_id: str) -> int:
    async with async_session_factory() as db:
        from sqlalchemy import func
        result = await db.execute(
            select(func.count()).select_from(MessageModel).where(MessageModel.session_id == session_id)
        )
        return result.scalar() or 0


async def get_session_dataset_ids(session_id: str) -> list[str]:
    async with async_session_factory() as db:
        result = await db.execute(
            select(DatasetModel.id).where(DatasetModel.session_id == session_id)
        )
        return [r[0] for r in result.all()]
