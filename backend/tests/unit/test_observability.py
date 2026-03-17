"""
Tests for the observability layer: trace_id propagation, metrics collection,
structlog context binding, and the /metrics API endpoint.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.models.schemas import StreamEvent, StreamEventType
from app.observability.logger import (
    bind_session_context,
    clear_session_context,
    generate_trace_id,
    get_current_trace_id,
)
from app.observability.metrics import MetricsCollector, SessionMetrics, metrics_collector


# ─── Trace ID generation ─────────────────────────────────────────────────────


class TestTraceIdGeneration:
    def test_trace_id_is_8_chars(self):
        tid = generate_trace_id()
        assert len(tid) == 8

    def test_trace_ids_are_unique(self):
        ids = {generate_trace_id() for _ in range(100)}
        assert len(ids) == 100


# ─── Context binding ─────────────────────────────────────────────────────────


class TestContextBinding:
    def test_bind_sets_trace_id(self):
        bind_session_context("sess-1", "abc12345")
        assert get_current_trace_id() == "abc12345"
        clear_session_context()

    def test_bind_auto_generates_trace_id(self):
        bind_session_context("sess-2")
        tid = get_current_trace_id()
        assert len(tid) == 8
        clear_session_context()

    def test_clear_resets_trace_id(self):
        bind_session_context("sess-3", "xyz99999")
        clear_session_context()
        assert get_current_trace_id() == ""


# ─── StreamEvent trace_id ─────────────────────────────────────────────────────


class TestStreamEventTraceId:
    def test_trace_id_field_exists(self):
        event = StreamEvent(
            event_type=StreamEventType.INTENT,
            data={"test": True},
            trace_id="abc123",
        )
        assert event.trace_id == "abc123"

    def test_trace_id_defaults_to_none(self):
        event = StreamEvent(event_type=StreamEventType.ERROR, data="oops")
        assert event.trace_id is None

    def test_trace_id_serializes_to_json(self):
        event = StreamEvent(
            event_type=StreamEventType.FINAL_RESPONSE,
            data="hello",
            trace_id="t1234567",
        )
        parsed = json.loads(event.model_dump_json())
        assert parsed["trace_id"] == "t1234567"

    def test_null_trace_id_serializes(self):
        event = StreamEvent(event_type=StreamEventType.ERROR, data="fail")
        parsed = json.loads(event.model_dump_json())
        assert parsed["trace_id"] is None


# ─── MetricsCollector ─────────────────────────────────────────────────────────


class TestMetricsCollector:
    def test_get_or_create_new_session(self):
        mc = MetricsCollector()
        m = mc.get_or_create("s1")
        assert isinstance(m, SessionMetrics)
        assert m.session_id == "s1"

    def test_get_or_create_reuses_session(self):
        mc = MetricsCollector()
        m1 = mc.get_or_create("s1")
        m2 = mc.get_or_create("s1")
        assert m1 is m2

    def test_record_llm_call(self):
        mc = MetricsCollector()
        m = mc.get_or_create("s1")
        m.record_llm_call(100, 50, 250.0)
        assert m.llm_calls == 1
        assert m.token_usage.input_tokens == 100
        assert m.token_usage.output_tokens == 50
        assert m.token_usage.total_tokens == 150

    def test_record_multiple_llm_calls(self):
        mc = MetricsCollector()
        m = mc.get_or_create("s1")
        m.record_llm_call(100, 50, 200.0)
        m.record_llm_call(200, 100, 300.0)
        assert m.llm_calls == 2
        assert m.token_usage.total_tokens == 450

    def test_record_specialist_call(self):
        mc = MetricsCollector()
        m = mc.get_or_create("s1")
        m.record_specialist_call("eda", 15.0, True)
        assert m.specialist_calls == 1
        assert m.errors == 0
        assert "eda" in m.latency_by_specialist

    def test_record_specialist_failure(self):
        mc = MetricsCollector()
        m = mc.get_or_create("s1")
        m.record_specialist_call("viz", 10.0, False)
        assert m.specialist_calls == 1
        assert m.errors == 1

    def test_record_reflection(self):
        mc = MetricsCollector()
        m = mc.get_or_create("s1")
        m.record_reflection()
        m.record_reflection()
        assert m.reflect_cycles == 2

    def test_get_summary(self):
        mc = MetricsCollector()
        m = mc.get_or_create("s1")
        m.record_llm_call(500, 200, 300.0)
        m.record_specialist_call("eda", 50.0, True)
        m.record_specialist_call("eda", 70.0, True)
        summary = m.get_summary()
        assert summary["session_id"] == "s1"
        assert summary["llm_calls"] == 1
        assert summary["specialist_calls"] == 2
        assert summary["total_tokens"] == 700
        assert summary["avg_latency_by_specialist_ms"]["eda"] == 60.0

    def test_estimated_cost(self):
        mc = MetricsCollector()
        m = mc.get_or_create("s1")
        m.record_llm_call(1_000_000, 100_000, 1000.0)
        assert m.token_usage.estimated_cost_usd == pytest.approx(4.5, rel=0.01)

    def test_get_session_summary_missing(self):
        mc = MetricsCollector()
        assert mc.get_session_summary("nonexistent") is None

    def test_get_all_summaries(self):
        mc = MetricsCollector()
        mc.get_or_create("a")
        mc.get_or_create("b")
        summaries = mc.get_all_summaries()
        assert len(summaries) == 2

    def test_clear_session(self):
        mc = MetricsCollector()
        mc.get_or_create("s1")
        mc.clear_session("s1")
        assert mc.get_session_summary("s1") is None


# ─── Supervisor trace_id propagation ──────────────────────────────────────────


class TestSupervisorTraceId:
    @pytest.fixture
    def eval_ctx(self):
        from app.agent.specialists.context import AnalysisContext
        np.random.seed(42)
        df = pd.DataFrame({
            "a": np.random.randint(1, 100, 50),
            "b": np.random.normal(10, 2, 50),
        })
        ctx = AnalysisContext()
        ctx.add_dataset("ds1", df, "test.csv")
        return ctx

    @pytest.fixture
    def registry(self):
        from app.agent.specialists.base import SpecialistRegistry
        from app.agent.specialists.eda import EDASpecialist
        from app.agent.specialists.viz import VizSpecialist
        from app.agent.specialists.sql import SQLSpecialist
        from app.agent.specialists.stats import StatsSpecialist
        from app.agent.specialists.cleaning import CleaningSpecialist
        reg = SpecialistRegistry()
        reg.register(EDASpecialist())
        reg.register(VizSpecialist())
        reg.register(SQLSpecialist())
        reg.register(StatsSpecialist())
        reg.register(CleaningSpecialist())
        return reg

    @pytest.mark.asyncio
    async def test_all_events_carry_trace_id(self, eval_ctx, registry):
        from app.agent.supervisor import Supervisor

        with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
            block = MagicMock()
            block.text = "Profile complete."
            block.type = "text"
            usage = MagicMock()
            usage.input_tokens = 80
            usage.output_tokens = 40
            resp = MagicMock()
            resp.content = [block]
            resp.usage = usage
            resp.stop_reason = "end_turn"
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=resp)
            MockCls.return_value = mock_client

            sup = Supervisor(registry=registry, context=eval_ctx)
            sup._client = mock_client

            events = []
            async for event in sup.run("profile my data", trace_id="test1234"):
                events.append(event)

        assert len(events) >= 2
        for event in events:
            assert event.trace_id == "test1234", (
                f"Event {event.event_type} missing trace_id"
            )

    @pytest.mark.asyncio
    async def test_no_data_events_carry_trace_id(self, registry):
        from app.agent.specialists.context import AnalysisContext
        from app.agent.supervisor import Supervisor

        empty = AnalysisContext()
        with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
            mock_client = AsyncMock()
            MockCls.return_value = mock_client
            sup = Supervisor(registry=registry, context=empty)
            sup._client = mock_client

            events = []
            async for event in sup.run("profile data", trace_id="nodata99"):
                events.append(event)

        assert len(events) == 1
        assert events[0].trace_id == "nodata99"

    @pytest.mark.asyncio
    async def test_trace_id_none_when_not_provided(self, eval_ctx, registry):
        from app.agent.supervisor import Supervisor

        with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
            block = MagicMock()
            block.text = "Done."
            block.type = "text"
            usage = MagicMock()
            usage.input_tokens = 50
            usage.output_tokens = 20
            resp = MagicMock()
            resp.content = [block]
            resp.usage = usage
            resp.stop_reason = "end_turn"
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=resp)
            MockCls.return_value = mock_client

            sup = Supervisor(registry=registry, context=eval_ctx)
            sup._client = mock_client

            events = []
            async for event in sup.run("profile my data"):
                events.append(event)

        for event in events:
            assert event.trace_id is None


# ─── Metrics API endpoint ────────────────────────────────────────────────────


class TestMetricsAPI:
    @pytest.mark.asyncio
    async def test_get_all_metrics_empty(self, test_app):
        resp = await test_app.get("/api/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_sessions" in data
        assert "sessions" in data

    @pytest.mark.asyncio
    async def test_get_session_metrics_not_found(self, test_app):
        resp = await test_app.get("/api/v1/metrics/nonexistent-session")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_session_metrics_found(self, test_app):
        metrics_collector.get_or_create("test-metrics-session")
        resp = await test_app.get("/api/v1/metrics/test-metrics-session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "test-metrics-session"
        metrics_collector.clear_session("test-metrics-session")
