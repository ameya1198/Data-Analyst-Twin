"""
Tests that specialist results survive JSON serialization.

These tests catch the exact production bug where numpy.bool_ / numpy.int64 etc.
inside specialist result dicts caused PydanticSerializationError when streamed
over WebSocket via StreamEvent.model_dump_json().
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from app.agent.executor import _sanitize_for_json
from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.eda import EDASpecialist
from app.agent.specialists.cleaning import CleaningSpecialist
from app.agent.specialists.stats import StatsSpecialist
from app.agent.specialists.viz import VizSpecialist
from app.models.schemas import StreamEvent, StreamEventType


# ─── _sanitize_for_json unit tests ───────────────────────────────────────────


class TestSanitizeForJson:
    def test_none(self):
        assert _sanitize_for_json(None) is None

    def test_native_types_passthrough(self):
        assert _sanitize_for_json("hello") == "hello"
        assert _sanitize_for_json(42) == 42
        assert _sanitize_for_json(3.14) == 3.14
        assert _sanitize_for_json(True) is True

    def test_numpy_bool(self):
        result = _sanitize_for_json(np.bool_(True))
        assert result is True
        assert type(result) is bool

    def test_numpy_false(self):
        result = _sanitize_for_json(np.bool_(False))
        assert result is False
        assert type(result) is bool

    def test_numpy_int64(self):
        result = _sanitize_for_json(np.int64(42))
        assert result == 42
        assert type(result) is int

    def test_numpy_int32(self):
        result = _sanitize_for_json(np.int32(99))
        assert result == 99
        assert type(result) is int

    def test_numpy_float64(self):
        result = _sanitize_for_json(np.float64(3.14))
        assert result == 3.14
        assert type(result) is float

    def test_numpy_nan_becomes_none(self):
        assert _sanitize_for_json(np.float64("nan")) is None

    def test_numpy_inf_becomes_none(self):
        assert _sanitize_for_json(np.float64("inf")) is None
        assert _sanitize_for_json(np.float64("-inf")) is None

    def test_numpy_array(self):
        arr = np.array([1, 2, 3])
        result = _sanitize_for_json(arr)
        assert result == [1, 2, 3]
        assert all(type(x) is int for x in result)

    def test_nested_dict_with_numpy(self):
        data = {
            "score": np.float64(0.95),
            "count": np.int64(100),
            "flag": np.bool_(True),
            "items": [np.int64(1), np.int64(2)],
        }
        result = _sanitize_for_json(data)
        assert result == {"score": 0.95, "count": 100, "flag": True, "items": [1, 2]}
        json_str = json.dumps(result)
        assert json_str

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": np.bool_(False)}}}
        result = _sanitize_for_json(data)
        assert result["a"]["b"]["c"] is False
        json.dumps(result)

    def test_list_of_dicts_with_numpy(self):
        data = [
            {"val": np.float64(1.5), "ok": np.bool_(True)},
            {"val": np.float64(float("nan")), "ok": np.bool_(False)},
        ]
        result = _sanitize_for_json(data)
        assert result[0]["val"] == 1.5
        assert result[1]["val"] is None
        json.dumps(result)

    def test_tuple_converted(self):
        result = _sanitize_for_json((np.int64(1), np.int64(2)))
        assert result == [1, 2]

    def test_unknown_type_becomes_string(self):
        result = _sanitize_for_json(object())
        assert isinstance(result, str)

    def test_dict_keys_become_strings(self):
        result = _sanitize_for_json({42: "val", np.int64(7): "x"})
        assert "42" in result
        assert "7" in result


# ─── StreamEvent serialization ────────────────────────────────────────────────


class TestStreamEventSerialization:
    def test_event_with_native_data(self):
        event = StreamEvent(
            event_type=StreamEventType.SPECIALIST_RESULT,
            data={"rows": 100, "flag": True},
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert parsed["data"]["rows"] == 100

    def test_event_with_sanitized_numpy(self):
        raw = {"count": np.int64(50), "is_valid": np.bool_(True)}
        event = StreamEvent(
            event_type=StreamEventType.SPECIALIST_RESULT,
            data=_sanitize_for_json(raw),
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert parsed["data"]["count"] == 50
        assert parsed["data"]["is_valid"] is True

    def test_final_response_string(self):
        event = StreamEvent(
            event_type=StreamEventType.FINAL_RESPONSE,
            data="Here are the results.",
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert parsed["data"] == "Here are the results."

    def test_error_event(self):
        event = StreamEvent(
            event_type=StreamEventType.ERROR,
            data={"error": "Dataset not found", "summary": "Please upload data."},
        )
        out = event.model_dump_json()
        parsed = json.loads(out)
        assert "error" in parsed["data"]


# ─── End-to-end: specialist result → sanitize → StreamEvent → JSON ───────────


@pytest.fixture
def _ctx() -> AnalysisContext:
    np.random.seed(42)
    df = pd.DataFrame({
        "age": np.random.randint(20, 65, 100),
        "salary": np.random.normal(75000, 15000, 100).round(2),
        "dept": np.random.choice(["Eng", "Sales"], 100),
        "is_mgr": np.random.choice([True, False], 100),
        "tenure": np.random.randint(0, 20, 100),
        "score": np.random.normal(4.0, 0.5, 100).round(2),
    })
    ctx = AnalysisContext()
    ctx.add_dataset("ds1", df, "data.csv")
    return ctx


class TestSpecialistResultSerialization:
    """Run real specialist tools and verify their output serializes to JSON."""

    @pytest.mark.asyncio
    async def test_eda_profile_serializes(self, _ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": "ds1"}, _ctx)
        assert result.success
        sanitized = _sanitize_for_json(result.data)
        out = json.dumps(sanitized)
        assert out

    @pytest.mark.asyncio
    async def test_eda_describe_serializes(self, _ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_describe", {"dataset_id": "ds1"}, _ctx)
        assert result.success
        sanitized = _sanitize_for_json(result.data)
        out = json.dumps(sanitized)
        assert out

    @pytest.mark.asyncio
    async def test_eda_correlations_serializes(self, _ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_correlations", {"dataset_id": "ds1"}, _ctx)
        assert result.success
        sanitized = _sanitize_for_json(result.data)
        out = json.dumps(sanitized)
        assert out

    @pytest.mark.asyncio
    async def test_eda_data_quality_serializes(self, _ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_data_quality", {"dataset_id": "ds1"}, _ctx)
        assert result.success
        sanitized = _sanitize_for_json(result.data)
        out = json.dumps(sanitized)
        assert out

    @pytest.mark.asyncio
    async def test_clean_structural_serializes(self, _ctx):
        cleaning = CleaningSpecialist()
        result = await cleaning.execute("clean_structural", {"dataset_id": "ds1"}, _ctx)
        assert result.success
        sanitized = _sanitize_for_json(result.data)
        out = json.dumps(sanitized)
        assert out

    @pytest.mark.asyncio
    async def test_clean_validate_serializes(self, _ctx):
        cleaning = CleaningSpecialist()
        result = await cleaning.execute("clean_validate", {"dataset_id": "ds1"}, _ctx)
        assert result.success
        sanitized = _sanitize_for_json(result.data)
        out = json.dumps(sanitized)
        assert out

    @pytest.mark.asyncio
    async def test_viz_bar_chart_serializes(self, _ctx):
        viz = VizSpecialist()
        result = await viz.execute("viz_bar_chart", {"dataset_id": "ds1", "x": "dept", "y": "salary"}, _ctx)
        assert result.success
        sanitized = _sanitize_for_json(result.data)
        out = json.dumps(sanitized)
        assert out

    @pytest.mark.asyncio
    async def test_viz_scatter_plot_serializes(self, _ctx):
        viz = VizSpecialist()
        result = await viz.execute("viz_scatter_plot", {"dataset_id": "ds1", "x": "age", "y": "salary"}, _ctx)
        assert result.success
        sanitized = _sanitize_for_json(result.data)
        out = json.dumps(sanitized)
        assert out

    @pytest.mark.asyncio
    async def test_stats_test_serializes(self, _ctx):
        stats = StatsSpecialist()
        result = await stats.execute(
            "stats_test",
            {"dataset_id": "ds1", "column": "salary", "group_column": "dept", "test_type": "auto"},
            _ctx,
        )
        assert result.success
        sanitized = _sanitize_for_json(result.data)
        out = json.dumps(sanitized)
        assert out

    @pytest.mark.asyncio
    async def test_full_stream_event_round_trip(self, _ctx):
        """The exact code path that crashed in production."""
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": "ds1"}, _ctx)
        sanitized = _sanitize_for_json(result.data)
        event = StreamEvent(
            event_type=StreamEventType.SPECIALIST_RESULT,
            data={"result_type": "table", "summary": result.summary, "data": sanitized},
            specialist_name="eda",
        )
        json_str = event.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "specialist_result"
        assert parsed["specialist_name"] == "eda"
