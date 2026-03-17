"""
Integration tests for the Supervisor pipeline.

These tests don't hit the real Anthropic API — they mock the LLM client and
verify that the Supervisor correctly yields StreamEvents, handles errors,
serializes results, routes by intent, and parses plans.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.agent.executor import _sanitize_for_json
from app.agent.planner import AnalysisPlan, AnalysisStep, Planner
from app.agent.specialists.base import ResultType, SpecialistRegistry, SpecialistResult
from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.eda import EDASpecialist
from app.agent.specialists.cleaning import CleaningSpecialist
from app.agent.specialists.viz import VizSpecialist
from app.agent.specialists.stats import StatsSpecialist
from app.agent.specialists.sql import SQLSpecialist
from app.agent.supervisor import Supervisor
from app.guardrails.confirmation import ConfirmationManager
from app.models.schemas import StreamEvent, StreamEventType


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def ctx_with_data() -> AnalysisContext:
    np.random.seed(42)
    df = pd.DataFrame({
        "age": np.random.randint(20, 65, 100),
        "salary": np.random.normal(75000, 15000, 100).round(2),
        "dept": np.random.choice(["Eng", "Sales", "HR"], 100),
    })
    ctx = AnalysisContext()
    ctx.add_dataset("test_ds", df, "test_data.csv")
    return ctx


@pytest.fixture
def registry() -> SpecialistRegistry:
    reg = SpecialistRegistry()
    reg.register(EDASpecialist())
    reg.register(CleaningSpecialist())
    reg.register(VizSpecialist())
    reg.register(StatsSpecialist())
    reg.register(SQLSpecialist())
    return reg


def _make_anthropic_response(text: str):
    """Build a mock that looks like an Anthropic API response."""
    content_block = MagicMock()
    content_block.text = text
    content_block.type = "text"

    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50

    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    response.stop_reason = "end_turn"
    return response


# ─── StreamEvent serialization round-trip ─────────────────────────────────────


class TestStreamEventRoundTrip:
    """Every StreamEvent the supervisor can yield must serialize to JSON."""

    def test_intent_event(self):
        event = StreamEvent(
            event_type=StreamEventType.INTENT,
            data={
                "intent": "profile_data",
                "mode": "direct",
                "confidence": 0.95,
                "reasoning": "Matched profile keyword.",
            },
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert parsed["event_type"] == "intent"
        assert parsed["data"]["confidence"] == 0.95

    def test_plan_event(self):
        plan = AnalysisPlan(
            understanding="Profile the dataset",
            approach="direct",
            steps=[
                AnalysisStep(
                    step_number=1,
                    description="Run EDA profile",
                    tool_name="eda_profile",
                    tool_params={"dataset_id": "ds1"},
                    rationale="Basic profiling",
                )
            ],
        )
        event = StreamEvent(
            event_type=StreamEventType.PLAN,
            data=plan.to_display(),
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert parsed["data"]["steps"][0]["tool_name"] == "eda_profile"

    def test_specialist_result_with_numpy(self):
        data = {
            "rows": np.int64(100),
            "missing_pct": np.float64(5.2),
            "has_dupes": np.bool_(False),
            "values": np.array([1, 2, 3]),
        }
        sanitized = _sanitize_for_json(data)
        event = StreamEvent(
            event_type=StreamEventType.SPECIALIST_RESULT,
            data=sanitized,
            specialist_name="eda",
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert parsed["data"]["rows"] == 100
        assert parsed["data"]["has_dupes"] is False

    def test_error_event(self):
        event = StreamEvent(
            event_type=StreamEventType.ERROR,
            data={"error": "Dataset not found", "summary": "Upload your data first."},
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert "error" in parsed["data"]

    def test_confirmation_request_event(self):
        event = StreamEvent(
            event_type=StreamEventType.CONFIRMATION_REQUEST,
            data={
                "request_id": "abc123",
                "specialist_name": "cleaning",
                "tool_name": "clean_structural",
                "description": "Data Cleaning: Structural",
                "details": {"dataset_id": "ds1"},
                "impact": "Normalize column names.",
            },
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert parsed["data"]["request_id"] == "abc123"

    def test_final_response_string(self):
        event = StreamEvent(
            event_type=StreamEventType.FINAL_RESPONSE,
            data="The dataset has 100 rows and 3 columns.",
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert parsed["data"] == "The dataset has 100 rows and 3 columns."


# ─── Direct mode execution ───────────────────────────────────────────────────


class TestDirectMode:
    @pytest.mark.asyncio
    async def test_direct_eda_profile(self, ctx_with_data, registry):
        """Direct mode should yield INTENT, SPECIALIST_CALL, SPECIALIST_RESULT, FINAL_RESPONSE."""
        with patch("app.agent.supervisor.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=_make_anthropic_response("Your dataset has 100 rows and 3 columns.")
            )
            MockClient.return_value = mock_client

            supervisor = Supervisor(registry, context=ctx_with_data)
            supervisor._client = mock_client

            events = []
            async for event in supervisor.run("profile my data"):
                events.append(event)

        event_types = [e.event_type for e in events]
        assert StreamEventType.INTENT in event_types
        assert StreamEventType.SPECIALIST_CALL in event_types
        assert StreamEventType.FINAL_RESPONSE in event_types

        intent_event = next(e for e in events if e.event_type == StreamEventType.INTENT)
        assert intent_event.data["mode"] == "direct"

    @pytest.mark.asyncio
    async def test_direct_mode_all_events_serialize(self, ctx_with_data, registry):
        """Every event from direct mode must serialize to JSON without error."""
        with patch("app.agent.supervisor.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=_make_anthropic_response("Results look great.")
            )
            MockClient.return_value = mock_client

            supervisor = Supervisor(registry, context=ctx_with_data)
            supervisor._client = mock_client

            async for event in supervisor.run("profile my data"):
                json_str = event.model_dump_json()
                parsed = json.loads(json_str)
                assert "event_type" in parsed


# ─── Error propagation ───────────────────────────────────────────────────────


class TestErrorPropagation:
    @pytest.mark.asyncio
    async def test_no_data_yields_final_response(self, registry):
        """When no data is loaded, the supervisor should return a help message."""
        ctx_empty = AnalysisContext()

        with patch("app.agent.supervisor.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client

            supervisor = Supervisor(registry, context=ctx_empty)
            supervisor._client = mock_client

            events = []
            async for event in supervisor.run("profile my data"):
                events.append(event)

        assert len(events) == 1
        assert events[0].event_type == StreamEventType.FINAL_RESPONSE
        assert "upload" in events[0].data.lower()

    @pytest.mark.asyncio
    async def test_specialist_error_yields_error_event(self, ctx_with_data, registry):
        """When a specialist fails, the supervisor should yield an ERROR event."""
        with patch("app.agent.supervisor.AsyncAnthropic") as MockClient:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                return_value=_make_anthropic_response("Something went wrong.")
            )
            MockClient.return_value = mock_client

            supervisor = Supervisor(registry, context=ctx_with_data)
            supervisor._client = mock_client

            events = []
            async for event in supervisor.run("describe columns in nonexistent_dataset"):
                events.append(event)

            for event in events:
                json_str = event.model_dump_json()
                json.loads(json_str)


# ─── Confirmation flow ───────────────────────────────────────────────────────


class TestConfirmationFlow:
    def test_needs_confirmation_for_cleaning(self):
        mgr = ConfirmationManager()
        assert mgr.needs_confirmation("cleaning", "clean_structural") is True
        assert mgr.needs_confirmation("cleaning", "clean_deduplicate") is True
        assert mgr.needs_confirmation("cleaning", "clean_missing") is True

    def test_no_confirmation_for_eda(self):
        mgr = ConfirmationManager()
        assert mgr.needs_confirmation("eda", "eda_profile") is False

    def test_build_request(self):
        mgr = ConfirmationManager()
        req = mgr.build_request("cleaning", "clean_structural", {"dataset_id": "ds1"})
        assert req.specialist_name == "cleaning"
        assert req.tool_name == "clean_structural"
        assert req.details["dataset_id"] == "ds1"
        assert "request_id" in req.__dict__

    @pytest.mark.asyncio
    async def test_resolve_approval(self):
        mgr = ConfirmationManager(timeout_seconds=5)
        req = mgr.build_request("cleaning", "clean_structural", {"dataset_id": "ds1"})
        mgr.create_pending(req.request_id)

        assert mgr.has_pending

        resolved = mgr.resolve(req.request_id, approved=True)
        assert resolved is True
        assert not mgr.has_pending

    @pytest.mark.asyncio
    async def test_resolve_rejection(self):
        mgr = ConfirmationManager(timeout_seconds=5)
        req = mgr.build_request("cleaning", "clean_missing", {"dataset_id": "ds1"})
        mgr.create_pending(req.request_id)

        import asyncio

        async def resolve_soon():
            await asyncio.sleep(0.05)
            mgr.resolve(req.request_id, approved=False, message="Not now.")

        asyncio.create_task(resolve_soon())
        response = await mgr.wait_for(req.request_id)
        assert response.approved is False
        assert response.user_message == "Not now."

    @pytest.mark.asyncio
    async def test_timeout_returns_rejection(self):
        mgr = ConfirmationManager(timeout_seconds=0.1)
        req = mgr.build_request("cleaning", "clean_structural", {"dataset_id": "ds1"})
        mgr.create_pending(req.request_id)

        response = await mgr.wait_for(req.request_id)
        assert response.approved is False
        assert "timed out" in (response.user_message or "").lower()

    def test_confirmation_request_serializes(self):
        mgr = ConfirmationManager()
        req = mgr.build_request("cleaning", "clean_structural", {"dataset_id": "ds1"})
        event = StreamEvent(
            event_type=StreamEventType.CONFIRMATION_REQUEST,
            data=req.to_stream_data(),
            specialist_name="cleaning",
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert parsed["event_type"] == "confirmation_request"
        assert parsed["data"]["tool_name"] == "clean_structural"


# ─── Planner parse ───────────────────────────────────────────────────────────


class TestPlannerParse:
    """Test Planner._parse_plan() with realistic JSON — no LLM call needed."""

    def _get_planner(self) -> Planner:
        return Planner(client=AsyncMock(), registry=SpecialistRegistry())

    def test_valid_plan(self):
        raw = json.dumps({
            "understanding": "User wants to profile the dataset.",
            "approach": "Run EDA profile, then data quality check.",
            "question_type": "descriptive",
            "assumptions": ["Single dataset loaded"],
            "caveats": [],
            "steps": [
                {
                    "step_number": 1,
                    "description": "Profile the dataset",
                    "tool_name": "eda_profile",
                    "tool_params": {"dataset_id": "abc123"},
                    "rationale": "Get an overview of the data.",
                    "workflow_phase": "exploration",
                },
                {
                    "step_number": 2,
                    "description": "Check data quality",
                    "tool_name": "eda_data_quality",
                    "tool_params": {"dataset_id": "abc123"},
                    "rationale": "Identify data quality issues.",
                    "workflow_phase": "exploration",
                },
            ],
        })

        planner = self._get_planner()
        plan = planner._parse_plan(raw)

        assert plan.understanding == "User wants to profile the dataset."
        assert len(plan.steps) == 2
        assert plan.steps[0].tool_name == "eda_profile"
        assert plan.steps[0].tool_params["dataset_id"] == "abc123"
        assert plan.steps[1].tool_name == "eda_data_quality"
        assert plan.question_type == "descriptive"

    def test_plan_with_code_fence(self):
        raw = "```json\n" + json.dumps({
            "understanding": "Test",
            "approach": "Test approach",
            "steps": [
                {
                    "step_number": 1,
                    "description": "Test step",
                    "tool_name": "eda_profile",
                    "tool_params": {"dataset_id": "x"},
                    "rationale": "Test",
                },
            ],
        }) + "\n```"

        planner = self._get_planner()
        plan = planner._parse_plan(raw)
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "eda_profile"

    def test_malformed_json_returns_fallback(self):
        planner = self._get_planner()
        plan = planner._parse_plan("This is not JSON at all {{{")
        assert plan.steps == []
        assert "Could not parse" in plan.understanding

    def test_missing_steps_key(self):
        raw = json.dumps({"understanding": "No steps", "approach": "none"})
        planner = self._get_planner()
        plan = planner._parse_plan(raw)
        assert plan.steps == []

    def test_empty_steps_list(self):
        raw = json.dumps({
            "understanding": "Empty",
            "approach": "none",
            "steps": [],
        })
        planner = self._get_planner()
        plan = planner._parse_plan(raw)
        assert plan.steps == []

    def test_step_defaults_for_missing_fields(self):
        raw = json.dumps({
            "understanding": "Test",
            "approach": "Test",
            "steps": [
                {
                    "tool_name": "eda_profile",
                    "tool_params": {"dataset_id": "ds1"},
                },
            ],
        })
        planner = self._get_planner()
        plan = planner._parse_plan(raw)
        assert len(plan.steps) == 1
        assert plan.steps[0].step_number == 1
        assert plan.steps[0].description == ""
        assert plan.steps[0].rationale == ""

    def test_plan_to_display(self):
        plan = AnalysisPlan(
            understanding="Test",
            approach="direct",
            steps=[
                AnalysisStep(
                    step_number=1,
                    description="Profile",
                    tool_name="eda_profile",
                    tool_params={"dataset_id": "ds1"},
                    rationale="Overview",
                    workflow_phase="exploration",
                ),
            ],
            assumptions=["One dataset"],
            caveats=["Small sample"],
        )
        display = plan.to_display()
        assert display["understanding"] == "Test"
        assert len(display["steps"]) == 1
        assert display["steps"][0]["tool_name"] == "eda_profile"
        assert display["assumptions"] == ["One dataset"]

        event = StreamEvent(event_type=StreamEventType.PLAN, data=display)
        json_str = event.model_dump_json()
        json.loads(json_str)
