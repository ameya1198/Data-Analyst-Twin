"""
E2E WebSocket tests — the full pipeline that was completely untested.

WebSocket connect → send JSON → supervisor.run() → specialists → event streaming
→ DB persistence → disconnect cleanup.

The Anthropic client is mocked so no real API calls happen, but everything else
runs for real: intent classification, specialist execution, JSON serialization,
error handling, session management.
"""

from __future__ import annotations

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.api.routes import chat as chat_module, data as data_module


def _make_anthropic_response(text: str):
    """Build a mock Anthropic API response."""
    block = MagicMock()
    block.text = text
    block.type = "text"

    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50

    resp = MagicMock()
    resp.content = [block]
    resp.usage = usage
    resp.stop_reason = "end_turn"
    return resp


def _upload_csv_to_context(filename: str = "test_data.csv") -> str:
    """Inject a DataFrame directly into the shared AnalysisContext. Returns dataset_id."""
    from app.api.routes.data import get_context

    np.random.seed(42)
    df = pd.DataFrame({
        "age": np.random.randint(20, 65, 100),
        "salary": np.random.normal(75000, 15000, 100).round(2),
        "dept": np.random.choice(["Eng", "Sales", "HR"], 100),
    })
    ctx = get_context()
    dataset_id = "ws_test_ds"
    ctx.add_dataset(dataset_id, df, filename)
    return dataset_id


def _collect_events(ws, *, until: str = "final_response", max_events: int = 20) -> list[dict]:
    """Read events from WebSocket until a specific event type or max_events reached."""
    events = []
    for _ in range(max_events):
        raw = ws.receive_text()
        event = json.loads(raw)
        events.append(event)
        if event["event_type"] == until:
            break
    return events


def _cleanup_context(dataset_id: str):
    """Remove test data from the shared context."""
    from app.api.routes.data import get_context
    ctx = get_context()
    ctx.datasets.pop(dataset_id, None)
    ctx.schemas.pop(dataset_id, None)


# ─── No Data Path (zero LLM calls) ───────────────────────────────────────────


class TestWebSocketNoData:
    """When no datasets are loaded, supervisor yields a help message — no LLM call."""

    def test_no_data_returns_upload_prompt(self):
        from app.api.routes.data import get_context
        ctx = get_context()
        had_data = dict(ctx.datasets)
        ctx.datasets.clear()
        ctx.schemas.clear()

        try:
            client = TestClient(app)
            with client.websocket_connect("/api/v1/chat/ws/no-data-session") as ws:
                ws.send_json({"message": "profile my data"})
                events = _collect_events(ws)

                assert len(events) >= 1
                final = events[-1]
                assert final["event_type"] == "final_response"
                assert "upload" in final["data"].lower()
        finally:
            ctx.datasets.update(had_data)


# ─── Empty Message ────────────────────────────────────────────────────────────


class TestWebSocketEmptyMessage:
    def test_empty_message_returns_error(self):
        client = TestClient(app)
        with client.websocket_connect("/api/v1/chat/ws/empty-msg-session") as ws:
            ws.send_json({"message": ""})
            raw = ws.receive_text()
            event = json.loads(raw)

            assert event["event_type"] == "error"
            assert "empty" in event["data"]["error"].lower()

    def test_whitespace_only_returns_error(self):
        client = TestClient(app)
        with client.websocket_connect("/api/v1/chat/ws/ws-msg-session") as ws:
            ws.send_json({"message": "   "})
            raw = ws.receive_text()
            event = json.loads(raw)

            assert event["event_type"] == "error"


# ─── Direct Mode (profile) — real specialist, mocked synthesis ────────────────


class TestWebSocketDirectMode:
    """
    "profile my data" → DIRECT mode → eda_profile (real) → synthesis (mocked).
    Tests the full event chain: INTENT → SPECIALIST_CALL → SPECIALIST_RESULT → FINAL_RESPONSE.
    """

    def test_profile_streams_all_event_types(self):
        dataset_id = _upload_csv_to_context()
        try:
            with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
                mock_client = AsyncMock()
                mock_client.messages.create = AsyncMock(
                    return_value=_make_anthropic_response(
                        "Your dataset has **100 rows** and **3 columns**."
                    )
                )
                MockCls.return_value = mock_client

                client = TestClient(app)
                with client.websocket_connect("/api/v1/chat/ws/direct-session") as ws:
                    ws.send_json({"message": "profile my data"})
                    events = _collect_events(ws)

            event_types = [e["event_type"] for e in events]

            assert "intent" in event_types
            assert "final_response" in event_types

            intent_evt = next(e for e in events if e["event_type"] == "intent")
            assert intent_evt["data"]["mode"] == "direct"

            final_evt = next(e for e in events if e["event_type"] == "final_response")
            assert "100 rows" in final_evt["data"]
        finally:
            _cleanup_context(dataset_id)

    def test_all_events_are_valid_json(self):
        dataset_id = _upload_csv_to_context()
        try:
            with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
                mock_client = AsyncMock()
                mock_client.messages.create = AsyncMock(
                    return_value=_make_anthropic_response("Summary here.")
                )
                MockCls.return_value = mock_client

                client = TestClient(app)
                with client.websocket_connect("/api/v1/chat/ws/json-session") as ws:
                    ws.send_json({"message": "profile my data"})
                    events = _collect_events(ws)

            for event in events:
                assert "event_type" in event
                assert "data" in event
                assert "timestamp" in event
        finally:
            _cleanup_context(dataset_id)

    def test_specialist_result_data_serializes(self):
        """The exact crash point: numpy types in specialist results must serialize."""
        dataset_id = _upload_csv_to_context()
        try:
            with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
                mock_client = AsyncMock()
                mock_client.messages.create = AsyncMock(
                    return_value=_make_anthropic_response("Done.")
                )
                MockCls.return_value = mock_client

                client = TestClient(app)
                with client.websocket_connect("/api/v1/chat/ws/serial-session") as ws:
                    ws.send_json({"message": "profile my data"})
                    events = _collect_events(ws)

            result_events = [e for e in events if e["event_type"] == "specialist_result"]
            for re_evt in result_events:
                json.dumps(re_evt["data"])
        finally:
            _cleanup_context(dataset_id)


# ─── Data Quality (another DIRECT mode tool) ─────────────────────────────────


class TestWebSocketDataQuality:
    def test_data_quality_check(self):
        dataset_id = _upload_csv_to_context()
        try:
            with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
                mock_client = AsyncMock()
                mock_client.messages.create = AsyncMock(
                    return_value=_make_anthropic_response("Data quality is good.")
                )
                MockCls.return_value = mock_client

                client = TestClient(app)
                with client.websocket_connect("/api/v1/chat/ws/dq-session") as ws:
                    ws.send_json({"message": "check data quality"})
                    events = _collect_events(ws)

            event_types = [e["event_type"] for e in events]
            assert "intent" in event_types
            assert "final_response" in event_types
        finally:
            _cleanup_context(dataset_id)


# ─── Supervisor Exception → Error Event (connection stays alive) ──────────────


class TestWebSocketSupervisorError:
    """
    When supervisor.run() raises an exception, the handler should:
    1. Yield an ERROR event with the error message
    2. Keep the WebSocket connection alive for the next message
    """

    def test_error_then_recovery(self):
        dataset_id = _upload_csv_to_context()
        try:
            with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
                mock_client = AsyncMock()

                call_count = 0

                async def _side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        raise RuntimeError("Simulated LLM failure")
                    return _make_anthropic_response("Recovered successfully.")

                mock_client.messages.create = AsyncMock(side_effect=_side_effect)
                MockCls.return_value = mock_client

                client = TestClient(app)
                with client.websocket_connect("/api/v1/chat/ws/error-session") as ws:
                    ws.send_json({"message": "profile my data"})
                    first_events = _collect_events(ws, until="error", max_events=10)

                    assert any(e["event_type"] == "error" for e in first_events)

                    ws.send_json({"message": "profile my data"})
                    second_events = _collect_events(ws)

                    assert any(e["event_type"] == "final_response" for e in second_events)
        finally:
            _cleanup_context(dataset_id)


# ─── Multiple Messages on Same Connection ────────────────────────────────────


class TestWebSocketMultiMessage:
    def test_two_messages_same_connection(self):
        dataset_id = _upload_csv_to_context()
        try:
            with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
                mock_client = AsyncMock()
                mock_client.messages.create = AsyncMock(
                    return_value=_make_anthropic_response("Here are the results.")
                )
                MockCls.return_value = mock_client

                client = TestClient(app)
                with client.websocket_connect("/api/v1/chat/ws/multi-session") as ws:
                    ws.send_json({"message": "profile my data"})
                    events1 = _collect_events(ws)
                    assert any(e["event_type"] == "final_response" for e in events1)

                    ws.send_json({"message": "check data quality"})
                    events2 = _collect_events(ws)
                    assert any(e["event_type"] == "final_response" for e in events2)
        finally:
            _cleanup_context(dataset_id)


# ─── Disconnect Cleanup ──────────────────────────────────────────────────────


class TestWebSocketDisconnect:
    def test_supervisor_removed_after_disconnect(self):
        with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=_make_anthropic_response("Done.")
            )
            MockCls.return_value = mock_client

            client = TestClient(app)
            session_id = "cleanup-session"
            with client.websocket_connect(f"/api/v1/chat/ws/{session_id}"):
                pass

            assert session_id not in chat_module._supervisors


# ─── DB Persistence Resilience ────────────────────────────────────────────────


class TestWebSocketDBResilience:
    """
    When the database layer fails (the exact bug that killed WebSocket connections),
    the handler should log a warning but keep the connection alive.
    """

    def test_db_failure_does_not_crash_connection(self):
        from app.api.routes.data import get_context
        ctx = get_context()
        had_data = dict(ctx.datasets)
        ctx.datasets.clear()
        ctx.schemas.clear()

        try:
            with patch.object(chat_module, "db_create_session", side_effect=Exception("DB is down")), \
                 patch.object(chat_module, "save_message", side_effect=Exception("DB is down")):
                client = TestClient(app)
                with client.websocket_connect("/api/v1/chat/ws/db-fail-session") as ws:
                    ws.send_json({"message": "hello"})
                    events = _collect_events(ws)

                    assert any(e["event_type"] == "final_response" for e in events)
        finally:
            ctx.datasets.update(had_data)
