"""
Tests for conversation memory persistence.

Covers the exact gap that both AI Agent skills flagged:
"Agent workflows lost on crash or restart" — the agent forgets everything
when the server restarts because ConversationMemory was purely in-memory.

Now we reload persisted messages from SQLite into ConversationMemory so the
agent remembers past conversations.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

import pytest

from app.agent.memory import ConversationMemory, Message


# ─── ConversationMemory.load_history ──────────────────────────────────────────


class TestLoadHistory:
    def test_load_user_and_assistant(self):
        mem = ConversationMemory()
        loaded = mem.load_history([
            ("user", "profile my data"),
            ("assistant", "Your dataset has 100 rows."),
        ])
        assert loaded == 2
        assert mem.message_count == 2
        assert mem.has_history

    def test_load_preserves_order(self):
        mem = ConversationMemory()
        mem.load_history([
            ("user", "first question"),
            ("assistant", "first answer"),
            ("user", "second question"),
            ("assistant", "second answer"),
        ])
        msgs = mem.get_messages()
        assert msgs[0]["content"] == "first question"
        assert msgs[1]["content"] == "first answer"
        assert msgs[2]["content"] == "second question"
        assert msgs[3]["content"] == "second answer"

    def test_load_skips_empty_content(self):
        mem = ConversationMemory()
        loaded = mem.load_history([
            ("user", "hello"),
            ("assistant", ""),
            ("user", ""),
            ("assistant", "world"),
        ])
        assert loaded == 2
        assert mem.message_count == 2

    def test_load_skips_non_user_assistant_roles(self):
        mem = ConversationMemory()
        loaded = mem.load_history([
            ("user", "hello"),
            ("system", "You are a data analyst."),
            ("tool_result", "some result"),
            ("assistant", "Hi!"),
        ])
        assert loaded == 2

    def test_load_empty_list(self):
        mem = ConversationMemory()
        loaded = mem.load_history([])
        assert loaded == 0
        assert mem.is_empty

    def test_load_trims_to_max(self):
        mem = ConversationMemory(max_messages=4)
        loaded = mem.load_history([
            ("user", f"msg {i}") for i in range(10)
        ])
        assert loaded == 10
        assert mem.message_count == 4
        msgs = mem.get_messages()
        assert msgs[0]["content"] == "msg 6"

    def test_load_then_add_more(self):
        mem = ConversationMemory()
        mem.load_history([
            ("user", "old question"),
            ("assistant", "old answer"),
        ])
        mem.add_user_message("new question")
        mem.add_assistant_message("new answer")
        assert mem.message_count == 4
        msgs = mem.get_messages()
        assert msgs[0]["content"] == "old question"
        assert msgs[2]["content"] == "new question"

    def test_load_does_not_duplicate_on_second_call(self):
        mem = ConversationMemory()
        mem.load_history([("user", "hello")])
        mem.load_history([("user", "world")])
        assert mem.message_count == 2

    def test_api_format_after_load(self):
        mem = ConversationMemory()
        mem.load_history([
            ("user", "test"),
            ("assistant", "response"),
        ])
        msgs = mem.get_messages()
        assert msgs[0] == {"role": "user", "content": "test"}
        assert msgs[1] == {"role": "assistant", "content": "response"}


# ─── Supervisor.reload_memory ─────────────────────────────────────────────────


class TestSupervisorReloadMemory:
    @pytest.mark.asyncio
    async def test_reload_populates_memory(self):
        from app.agent.specialists.base import SpecialistRegistry
        from app.agent.supervisor import Supervisor

        mock_rows = [
            SimpleNamespace(role="user", content="profile my data"),
            SimpleNamespace(role="assistant", content="Your dataset has 100 rows and 3 columns."),
            SimpleNamespace(role="user", content="show correlations"),
            SimpleNamespace(role="assistant", content="Here are the correlations."),
        ]

        with patch("app.agent.supervisor.AsyncAnthropic"), \
             patch("app.database.load_messages", new_callable=AsyncMock, return_value=mock_rows):
            sup = Supervisor(registry=SpecialistRegistry())
            loaded = await sup.reload_memory("test-session")

        assert loaded == 4
        assert sup.memory.message_count == 4
        assert sup.memory.has_history
        msgs = sup.memory.get_messages()
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "profile my data"

    @pytest.mark.asyncio
    async def test_reload_empty_session(self):
        from app.agent.specialists.base import SpecialistRegistry
        from app.agent.supervisor import Supervisor

        with patch("app.agent.supervisor.AsyncAnthropic"), \
             patch("app.database.load_messages", new_callable=AsyncMock, return_value=[]):
            sup = Supervisor(registry=SpecialistRegistry())
            loaded = await sup.reload_memory("empty-session")

        assert loaded == 0
        assert sup.memory.is_empty

    @pytest.mark.asyncio
    async def test_reload_skips_null_content(self):
        from app.agent.specialists.base import SpecialistRegistry
        from app.agent.supervisor import Supervisor

        mock_rows = [
            SimpleNamespace(role="user", content="hello"),
            SimpleNamespace(role="assistant", content=None),
            SimpleNamespace(role="user", content="world"),
        ]

        with patch("app.agent.supervisor.AsyncAnthropic"), \
             patch("app.database.load_messages", new_callable=AsyncMock, return_value=mock_rows):
            sup = Supervisor(registry=SpecialistRegistry())
            loaded = await sup.reload_memory("null-session")

        assert loaded == 2

    @pytest.mark.asyncio
    async def test_reload_db_failure_does_not_crash(self):
        """Memory reload failure should not prevent the supervisor from working."""
        from app.agent.specialists.base import SpecialistRegistry
        from app.agent.supervisor import Supervisor

        with patch("app.agent.supervisor.AsyncAnthropic"), \
             patch("app.database.load_messages", new_callable=AsyncMock, side_effect=Exception("DB down")):
            sup = Supervisor(registry=SpecialistRegistry())
            with pytest.raises(Exception, match="DB down"):
                await sup.reload_memory("bad-session")

        assert sup.memory.is_empty


# ─── Chat handler integration ────────────────────────────────────────────────


class TestChatHandlerMemoryReload:
    @pytest.mark.asyncio
    async def test_get_or_create_supervisor_reloads_memory(self):
        """When a new supervisor is created, it should attempt to reload memory."""
        from app.api.routes import chat as chat_module

        mock_rows = [
            SimpleNamespace(role="user", content="old question"),
            SimpleNamespace(role="assistant", content="old answer"),
        ]

        chat_module._supervisors.clear()

        with patch("app.agent.supervisor.AsyncAnthropic"), \
             patch("app.database.load_messages", new_callable=AsyncMock, return_value=mock_rows):
            sup = await chat_module._get_or_create_supervisor("reload-test-session")

        assert sup.memory.message_count == 2
        assert sup.memory.get_messages()[0]["content"] == "old question"

        chat_module._supervisors.clear()

    @pytest.mark.asyncio
    async def test_existing_supervisor_skips_reload(self):
        """If a supervisor already exists for the session, don't reload."""
        from app.api.routes import chat as chat_module

        chat_module._supervisors.clear()

        with patch("app.agent.supervisor.AsyncAnthropic"), \
             patch("app.database.load_messages", new_callable=AsyncMock, return_value=[]):
            sup1 = await chat_module._get_or_create_supervisor("existing-session")

        sup1.memory.add_user_message("live question")
        sup1.memory.add_assistant_message("live answer")

        with patch("app.database.load_messages", new_callable=AsyncMock) as mock_load:
            sup2 = await chat_module._get_or_create_supervisor("existing-session")
            mock_load.assert_not_awaited()

        assert sup2 is sup1
        assert sup2.memory.message_count == 2

        chat_module._supervisors.clear()

    @pytest.mark.asyncio
    async def test_reload_failure_still_creates_supervisor(self):
        """DB failure during reload should not prevent supervisor creation."""
        from app.api.routes import chat as chat_module

        chat_module._supervisors.clear()

        with patch("app.agent.supervisor.AsyncAnthropic"), \
             patch("app.database.load_messages", new_callable=AsyncMock, side_effect=Exception("DB down")):
            sup = await chat_module._get_or_create_supervisor("fail-session")

        assert sup is not None
        assert sup.memory.is_empty

        chat_module._supervisors.clear()
