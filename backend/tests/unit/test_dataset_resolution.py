"""
Tests for dataset ID resolution — the exact production bug where the LLM sent
'dataset_name' or a filename instead of the internal dataset_id, causing every
EDA/cleaning/stats/viz tool to fail with "dataset not found."
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.eda import EDASpecialist
from app.agent.specialists.cleaning import CleaningSpecialist
from app.agent.specialists.stats import StatsSpecialist
from app.agent.specialists.viz import VizSpecialist


@pytest.fixture
def df() -> pd.DataFrame:
    np.random.seed(42)
    return pd.DataFrame({
        "age": np.random.randint(20, 65, 50),
        "salary": np.random.normal(75000, 15000, 50).round(2),
        "dept": np.random.choice(["Eng", "Sales"], 50),
        "score": np.random.normal(4, 0.5, 50).round(2),
    })


@pytest.fixture
def ctx_single(df) -> AnalysisContext:
    """One dataset: ID='abc123', filename='sales_data.csv'."""
    ctx = AnalysisContext()
    ctx.add_dataset("abc123", df, "sales_data.csv")
    return ctx


@pytest.fixture
def ctx_multi(df) -> AnalysisContext:
    """Two datasets to test that empty-string fallback only works with one."""
    ctx = AnalysisContext()
    ctx.add_dataset("ds_a", df.copy(), "dataset_a.csv")
    ctx.add_dataset("ds_b", df.copy(), "dataset_b.csv")
    return ctx


# ─── resolve_dataset_id unit tests ───────────────────────────────────────────


class TestResolveDatasetId:
    def test_exact_id(self, ctx_single):
        assert ctx_single.resolve_dataset_id("abc123") == "abc123"

    def test_filename_exact(self, ctx_single):
        assert ctx_single.resolve_dataset_id("sales_data.csv") == "abc123"

    def test_filename_case_insensitive(self, ctx_single):
        assert ctx_single.resolve_dataset_id("Sales_Data.CSV") == "abc123"
        assert ctx_single.resolve_dataset_id("SALES_DATA.CSV") == "abc123"

    def test_empty_string_single_dataset(self, ctx_single):
        assert ctx_single.resolve_dataset_id("") == "abc123"

    def test_empty_string_multi_dataset_returns_none(self, ctx_multi):
        assert ctx_multi.resolve_dataset_id("") is None

    def test_nonexistent_returns_none(self, ctx_single):
        assert ctx_single.resolve_dataset_id("nonexistent") is None

    def test_partial_name_no_match(self, ctx_single):
        assert ctx_single.resolve_dataset_id("sales_data") is None

    def test_multi_exact_id(self, ctx_multi):
        assert ctx_multi.resolve_dataset_id("ds_a") == "ds_a"
        assert ctx_multi.resolve_dataset_id("ds_b") == "ds_b"

    def test_multi_filename(self, ctx_multi):
        assert ctx_multi.resolve_dataset_id("dataset_a.csv") == "ds_a"
        assert ctx_multi.resolve_dataset_id("dataset_b.csv") == "ds_b"

    def test_empty_context(self):
        ctx = AnalysisContext()
        assert ctx.resolve_dataset_id("anything") is None
        assert ctx.resolve_dataset_id("") is None


# ─── EDA specialist with mismatched params ────────────────────────────────────


class TestEDAResolution:
    @pytest.mark.asyncio
    async def test_eda_with_filename_as_dataset_id(self, ctx_single):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": "sales_data.csv"}, ctx_single)
        assert result.success
        assert result.data["rows"] == 50

    @pytest.mark.asyncio
    async def test_eda_with_dataset_name_param(self, ctx_single):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_name": "sales_data.csv"}, ctx_single)
        assert result.success

    @pytest.mark.asyncio
    async def test_eda_with_empty_id_single_dataset(self, ctx_single):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": ""}, ctx_single)
        assert result.success

    @pytest.mark.asyncio
    async def test_eda_with_empty_id_multi_dataset_fails(self, ctx_multi):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": ""}, ctx_multi)
        assert not result.success

    @pytest.mark.asyncio
    async def test_eda_with_wrong_id_fails(self, ctx_single):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": "nonexistent"}, ctx_single)
        assert not result.success


# ─── Cleaning specialist with mismatched params ──────────────────────────────


class TestCleaningResolution:
    @pytest.mark.asyncio
    async def test_clean_with_filename(self, ctx_single):
        cleaning = CleaningSpecialist()
        result = await cleaning.execute("clean_structural", {"dataset_id": "sales_data.csv"}, ctx_single)
        assert result.success

    @pytest.mark.asyncio
    async def test_clean_with_dataset_name_param(self, ctx_single):
        cleaning = CleaningSpecialist()
        result = await cleaning.execute("clean_structural", {"dataset_name": "sales_data.csv"}, ctx_single)
        assert result.success

    @pytest.mark.asyncio
    async def test_clean_with_wrong_id_fails(self, ctx_single):
        cleaning = CleaningSpecialist()
        result = await cleaning.execute("clean_structural", {"dataset_id": "nope"}, ctx_single)
        assert not result.success


# ─── Viz specialist with mismatched params ────────────────────────────────────


class TestVizResolution:
    @pytest.mark.asyncio
    async def test_viz_with_filename(self, ctx_single):
        viz = VizSpecialist()
        result = await viz.execute(
            "viz_bar_chart",
            {"dataset_id": "sales_data.csv", "x": "dept", "y": "salary"},
            ctx_single,
        )
        assert result.success

    @pytest.mark.asyncio
    async def test_viz_with_wrong_id_fails(self, ctx_single):
        viz = VizSpecialist()
        result = await viz.execute(
            "viz_bar_chart",
            {"dataset_id": "wrong", "x": "dept", "y": "salary"},
            ctx_single,
        )
        assert not result.success


# ─── Stats specialist with mismatched params ─────────────────────────────────


class TestStatsResolution:
    @pytest.mark.asyncio
    async def test_stats_with_filename(self, ctx_single):
        stats = StatsSpecialist()
        result = await stats.execute(
            "stats_assumptions",
            {"dataset_id": "sales_data.csv", "column": "salary"},
            ctx_single,
        )
        assert result.success

    @pytest.mark.asyncio
    async def test_stats_with_dataset_name_param(self, ctx_single):
        stats = StatsSpecialist()
        result = await stats.execute(
            "stats_assumptions",
            {"dataset_name": "sales_data.csv", "column": "salary"},
            ctx_single,
        )
        assert result.success


# ─── DataSchema.to_summary includes dataset_id ───────────────────────────────


class TestSchemaSummary:
    def test_summary_contains_dataset_id(self, ctx_single):
        schema = ctx_single.schemas["abc123"]
        summary = schema.to_summary()
        assert "dataset_id='abc123'" in summary
        assert "sales_data.csv" in summary
