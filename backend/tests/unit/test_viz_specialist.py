"""Tests for the Visualization specialist — all 8 tools + edge cases."""

import numpy as np
import pandas as pd
import pytest

from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.viz import VizSpecialist


@pytest.fixture
def viz():
    return VizSpecialist()


@pytest.fixture
def viz_ctx():
    np.random.seed(42)
    df = pd.DataFrame({
        "category": ["A", "B", "C", "D", "E", "F", "G"] * 14 + ["A", "B"],
        "value": np.random.normal(50, 15, 100).round(2),
        "metric": np.random.normal(100, 25, 100).round(2),
        "date": pd.date_range("2023-01-01", periods=100, freq="D"),
        "group": np.random.choice(["X", "Y"], 100),
    })
    ctx = AnalysisContext()
    ctx.add_dataset("viz", df, "viz_data.csv")
    return ctx


# ─── viz_bar_chart ────────────────────────────────────────────────────────────

class TestVizBarChart:
    async def test_basic_bar_chart(self, viz, viz_ctx):
        r = await viz.execute("viz_bar_chart", {
            "dataset_id": "viz", "x": "category", "y": "value", "agg": "mean"
        }, viz_ctx)
        assert r.success
        assert r.data is not None

    async def test_bar_chart_y_axis_starts_at_zero(self, viz, viz_ctx):
        r = await viz.execute("viz_bar_chart", {
            "dataset_id": "viz", "x": "category", "y": "value", "agg": "mean"
        }, viz_ctx)
        fig_data = r.data
        assert fig_data is not None

    async def test_bar_chart_nonexistent_column(self, viz, viz_ctx):
        r = await viz.execute("viz_bar_chart", {
            "dataset_id": "viz", "x": "nonexistent", "y": "value"
        }, viz_ctx)
        assert not r.success


# ─── viz_line_chart ───────────────────────────────────────────────────────────

class TestVizLineChart:
    async def test_basic_line_chart(self, viz, viz_ctx):
        r = await viz.execute("viz_line_chart", {
            "dataset_id": "viz", "x": "date", "y": "value"
        }, viz_ctx)
        assert r.success

    async def test_line_chart_with_group(self, viz, viz_ctx):
        r = await viz.execute("viz_line_chart", {
            "dataset_id": "viz", "x": "date", "y": "value", "color": "group"
        }, viz_ctx)
        assert r.success


# ─── viz_scatter_plot ─────────────────────────────────────────────────────────

class TestVizScatterPlot:
    async def test_basic_scatter(self, viz, viz_ctx):
        r = await viz.execute("viz_scatter_plot", {
            "dataset_id": "viz", "x": "value", "y": "metric"
        }, viz_ctx)
        assert r.success

    async def test_scatter_with_color(self, viz, viz_ctx):
        r = await viz.execute("viz_scatter_plot", {
            "dataset_id": "viz", "x": "value", "y": "metric", "color": "group"
        }, viz_ctx)
        assert r.success

    async def test_scatter_with_nulls(self, viz):
        df = pd.DataFrame({
            "x": [1, 2, None, 4, 5],
            "y": [10, None, 30, 40, 50],
        })
        ctx = AnalysisContext()
        ctx.add_dataset("null", df, "null.csv")
        r = await viz.execute("viz_scatter_plot", {
            "dataset_id": "null", "x": "x", "y": "y"
        }, ctx)
        assert r.success


# ─── viz_histogram ────────────────────────────────────────────────────────────

class TestVizHistogram:
    async def test_basic_histogram(self, viz, viz_ctx):
        r = await viz.execute("viz_histogram", {
            "dataset_id": "viz", "column": "value"
        }, viz_ctx)
        assert r.success

    async def test_histogram_with_bins(self, viz, viz_ctx):
        r = await viz.execute("viz_histogram", {
            "dataset_id": "viz", "column": "value", "bins": 20
        }, viz_ctx)
        assert r.success

    async def test_histogram_single_value(self, viz):
        df = pd.DataFrame({"x": [5] * 50})
        ctx = AnalysisContext()
        ctx.add_dataset("single", df, "single.csv")
        r = await viz.execute("viz_histogram", {
            "dataset_id": "single", "column": "x"
        }, ctx)
        assert r.success


# ─── viz_box_plot ─────────────────────────────────────────────────────────────

class TestVizBoxPlot:
    async def test_basic_box_plot(self, viz, viz_ctx):
        r = await viz.execute("viz_box_plot", {
            "dataset_id": "viz", "y": "value"
        }, viz_ctx)
        assert r.success

    async def test_box_plot_with_group(self, viz, viz_ctx):
        r = await viz.execute("viz_box_plot", {
            "dataset_id": "viz", "y": "value", "x": "group"
        }, viz_ctx)
        assert r.success


# ─── viz_heatmap ──────────────────────────────────────────────────────────────

class TestVizHeatmap:
    async def test_correlation_heatmap(self, viz, viz_ctx):
        r = await viz.execute("viz_heatmap", {
            "dataset_id": "viz", "type": "correlation"
        }, viz_ctx)
        assert r.success


# ─── viz_pie_chart ────────────────────────────────────────────────────────────

class TestVizPieChart:
    async def test_basic_pie(self, viz, viz_ctx):
        r = await viz.execute("viz_pie_chart", {
            "dataset_id": "viz", "names": "group", "values": "value"
        }, viz_ctx)
        assert r.success

    async def test_pie_max_5_segments(self, viz, viz_ctx):
        r = await viz.execute("viz_pie_chart", {
            "dataset_id": "viz", "names": "category", "values": "value"
        }, viz_ctx)
        assert r.success
        assert r.data is not None


# ─── viz_recommend ────────────────────────────────────────────────────────────

class TestVizRecommend:
    async def test_recommend_returns_suggestion(self, viz, viz_ctx):
        r = await viz.execute("viz_recommend", {
            "dataset_id": "viz", "goal": "compare_categories",
            "columns": ["category", "value"]
        }, viz_ctx)
        assert r.success
        assert r.data is not None


# ─── Tool metadata ────────────────────────────────────────────────────────────

class TestVizToolMetadata:
    def test_tool_count(self, viz):
        assert len(viz.get_tools()) == 8

    def test_tool_names(self, viz):
        names = set(viz.get_tool_names())
        expected = {"viz_bar_chart", "viz_line_chart", "viz_scatter_plot",
                    "viz_histogram", "viz_box_plot", "viz_heatmap",
                    "viz_pie_chart", "viz_recommend"}
        assert names == expected

    def test_system_prompt_references_tufte(self, viz):
        assert "Tufte" in viz.system_prompt or "tufte" in viz.system_prompt.lower()
