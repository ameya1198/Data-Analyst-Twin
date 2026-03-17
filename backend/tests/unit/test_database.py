"""
Tests for the SQLite persistence layer.

Uses an in-memory SQLite database for isolation. Covers the exact bugs that
hit production: wrong path resolution and CRUD operations that failed silently.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import (
    Base,
    SessionModel,
    DatasetModel,
    MessageModel,
    _db_file,
    _BACKEND_ROOT,
)


# ─── Test-local in-memory DB helpers ─────────────────────────────────────────


@pytest.fixture
async def db():
    """Create a fresh in-memory database for each test."""
    from sqlalchemy import event as sa_event

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys = ON")

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ─── Path resolution ─────────────────────────────────────────────────────────


class TestPathResolution:
    def test_db_file_is_absolute(self):
        assert _db_file.is_absolute()

    def test_db_file_under_backend_data(self):
        assert _db_file.name == "sessions.db"
        assert _db_file.parent.name == "data"

    def test_backend_root_is_absolute(self):
        assert _BACKEND_ROOT.is_absolute()

    def test_backend_root_contains_app(self):
        assert (_BACKEND_ROOT / "app").exists()


# ─── Table creation ──────────────────────────────────────────────────────────


class TestTableCreation:
    @pytest.mark.asyncio
    async def test_all_tables_created(self, db):
        async with db() as session:
            from sqlalchemy import inspect

            def get_tables(conn):
                inspector = inspect(conn)
                return inspector.get_table_names()

            async with session.bind.connect() as conn:
                tables = await conn.run_sync(get_tables)
                assert "sessions" in tables
                assert "datasets" in tables
                assert "messages" in tables


# ─── Session CRUD ─────────────────────────────────────────────────────────────


class TestSessionCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get_session(self, db):
        from sqlalchemy import select

        async with db() as session:
            s = SessionModel(id="sess-1", title="Test Session")
            session.add(s)
            await session.commit()

        async with db() as session:
            result = await session.execute(select(SessionModel).where(SessionModel.id == "sess-1"))
            found = result.scalar_one_or_none()
            assert found is not None
            assert found.title == "Test Session"

    @pytest.mark.asyncio
    async def test_create_session_without_title(self, db):
        from sqlalchemy import select

        async with db() as session:
            s = SessionModel(id="sess-2")
            session.add(s)
            await session.commit()

        async with db() as session:
            result = await session.execute(select(SessionModel).where(SessionModel.id == "sess-2"))
            found = result.scalar_one_or_none()
            assert found is not None
            assert found.title is None

    @pytest.mark.asyncio
    async def test_delete_session(self, db):
        from sqlalchemy import select, delete

        async with db() as session:
            session.add(SessionModel(id="del-me"))
            await session.commit()

        async with db() as session:
            await session.execute(delete(SessionModel).where(SessionModel.id == "del-me"))
            await session.commit()

        async with db() as session:
            result = await session.execute(select(SessionModel).where(SessionModel.id == "del-me"))
            assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_list_sessions_ordered(self, db):
        from sqlalchemy import select

        async with db() as session:
            s1 = SessionModel(id="s1", updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
            s2 = SessionModel(id="s2", updated_at=datetime(2024, 6, 1, tzinfo=timezone.utc))
            session.add_all([s1, s2])
            await session.commit()

        async with db() as session:
            result = await session.execute(select(SessionModel).order_by(SessionModel.updated_at.desc()))
            sessions = list(result.scalars().all())
            assert sessions[0].id == "s2"
            assert sessions[1].id == "s1"


# ─── Dataset CRUD ────────────────────────────────────────────────────────────


class TestDatasetCRUD:
    @pytest.mark.asyncio
    async def test_save_and_load_dataset(self, db):
        from sqlalchemy import select

        async with db() as session:
            ds = DatasetModel(
                id="ds-1",
                filename="test.csv",
                file_path="uploads/ds-1_test.csv",
                rows=100,
                columns=5,
                column_names='["a","b","c","d","e"]',
                dtypes='{"a":"int64","b":"float64"}',
                size_bytes=5000,
            )
            session.add(ds)
            await session.commit()

        async with db() as session:
            result = await session.execute(select(DatasetModel).where(DatasetModel.id == "ds-1"))
            found = result.scalar_one_or_none()
            assert found is not None
            assert found.filename == "test.csv"
            assert found.rows == 100
            assert found.columns == 5

    @pytest.mark.asyncio
    async def test_delete_dataset(self, db):
        from sqlalchemy import select, delete

        async with db() as session:
            session.add(DatasetModel(id="ds-del", filename="x.csv", file_path="uploads/x.csv"))
            await session.commit()

        async with db() as session:
            await session.execute(delete(DatasetModel).where(DatasetModel.id == "ds-del"))
            await session.commit()

        async with db() as session:
            result = await session.execute(select(DatasetModel).where(DatasetModel.id == "ds-del"))
            assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_dataset_with_session_fk(self, db):
        from sqlalchemy import select

        async with db() as session:
            session.add(SessionModel(id="parent-sess"))
            await session.commit()

        async with db() as session:
            ds = DatasetModel(id="ds-fk", session_id="parent-sess", filename="f.csv", file_path="uploads/f.csv")
            session.add(ds)
            await session.commit()

        async with db() as session:
            result = await session.execute(select(DatasetModel).where(DatasetModel.session_id == "parent-sess"))
            datasets = list(result.scalars().all())
            assert len(datasets) == 1
            assert datasets[0].id == "ds-fk"


# ─── Message CRUD ────────────────────────────────────────────────────────────


class TestMessageCRUD:
    @pytest.mark.asyncio
    async def test_save_and_load_messages(self, db):
        from sqlalchemy import select

        async with db() as session:
            session.add(SessionModel(id="msg-sess"))
            await session.commit()

        async with db() as session:
            m1 = MessageModel(id="m1", session_id="msg-sess", role="user", content="Hello")
            m2 = MessageModel(id="m2", session_id="msg-sess", role="assistant", content="Hi there")
            session.add_all([m1, m2])
            await session.commit()

        async with db() as session:
            result = await session.execute(
                select(MessageModel)
                .where(MessageModel.session_id == "msg-sess")
                .order_by(MessageModel.created_at)
            )
            msgs = list(result.scalars().all())
            assert len(msgs) == 2
            assert msgs[0].role == "user"
            assert msgs[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_count_messages(self, db):
        from sqlalchemy import select, func

        async with db() as session:
            session.add(SessionModel(id="count-sess"))
            await session.commit()

        async with db() as session:
            for i in range(5):
                session.add(MessageModel(id=f"cm-{i}", session_id="count-sess", role="user", content=f"msg {i}"))
            await session.commit()

        async with db() as session:
            result = await session.execute(
                select(func.count()).select_from(MessageModel).where(MessageModel.session_id == "count-sess")
            )
            assert result.scalar() == 5

    @pytest.mark.asyncio
    async def test_message_cascade_on_session_delete(self, db):
        """Deleting a session should cascade-delete its messages."""
        from sqlalchemy import select, delete

        async with db() as session:
            session.add(SessionModel(id="cascade-sess"))
            await session.commit()

        async with db() as session:
            session.add(MessageModel(id="cas-m1", session_id="cascade-sess", role="user", content="test"))
            await session.commit()

        async with db() as session:
            await session.execute(delete(SessionModel).where(SessionModel.id == "cascade-sess"))
            await session.commit()

        async with db() as session:
            result = await session.execute(select(MessageModel).where(MessageModel.session_id == "cascade-sess"))
            assert list(result.scalars().all()) == []

    @pytest.mark.asyncio
    async def test_message_with_null_content(self, db):
        from sqlalchemy import select

        async with db() as session:
            session.add(SessionModel(id="null-sess"))
            await session.commit()

        async with db() as session:
            session.add(MessageModel(id="null-m", session_id="null-sess", role="assistant", content=None))
            await session.commit()

        async with db() as session:
            result = await session.execute(select(MessageModel).where(MessageModel.id == "null-m"))
            found = result.scalar_one()
            assert found.content is None
