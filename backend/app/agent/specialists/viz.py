"""
Visualization Specialist — chart generation in ToolMode.

Built on a comprehensive knowledge framework:
- Edward Tufte's principles (data-ink ratio, graphical integrity, no chartjunk)
- Chart Selection Rules (goal-to-chart mapping)
- Color Principles (sequential/diverging/categorical, colorblind-safe)
- Audience-First Design (Executive / Manager / Analyst / Public)
- Labeling & Annotation Standards (insight-driven titles, units on axes)
- Scale & Proportion Rules (bar charts start at zero)
- Analytics Visualization Ladder (Descriptive → Diagnostic → Predictive → Prescriptive)

All charts enforce Tufte defaults: plotly_white template, minimal gridlines,
direct labels over legends, no 3D effects, colorblind-safe palettes.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import structlog

from app.agent.specialists.base import BaseSpecialist, SpecialistMode, SpecialistResult, ResultType
from app.agent.specialists.context import AnalysisContext
from app.agent.knowledge.viz_knowledge import (
    CHART_ANTI_PATTERNS,
    CHART_SELECTION_RULES,
    COLORBLIND_SAFE_PALETTES,
    PLOTLY_DEFAULTS,
    SCALE_RULES,
    AudienceLevel,
    ChartGoal,
    apply_tufte_axes,
    get_audience_config,
    get_chart_recommendation,
    get_color_palette,
    get_plotly_layout_defaults,
    get_viz_workflow_summary,
)

logger = structlog.get_logger(__name__)

MAX_PIE_SEGMENTS = 5
MAX_CHART_COLORS = 7


class VizSpecialist(BaseSpecialist):
    name = "viz"
    description = (
        "Visualization specialist following Tufte's principles and the Analytics "
        "Visualization Ladder. Generates Plotly charts (bar, line, scatter, histogram, "
        "box, heatmap, pie) with enforced graphical integrity, colorblind-safe palettes, "
        "insight-driven titles, and audience-appropriate complexity. Includes a "
        "chart recommendation tool for automated chart type selection."
    )
    mode = SpecialistMode.TOOL
    timeout_seconds = 30
    system_prompt = (
        "You are the visualization specialist of a data analyst digital twin. "
        "You follow Edward Tufte's principles: maximize data-ink ratio, eliminate "
        "chartjunk, maintain graphical integrity. Your charts enforce: bar charts "
        "start at zero, max 5 pie segments, colorblind-safe palettes, insight-driven "
        "titles, and axis labels with units. Never create 3D charts or dual Y-axes."
    )

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "viz_bar_chart",
                "description": (
                    "[Descriptive/Diagnostic] Create a bar chart for comparing categories. "
                    "Y-axis enforced to start at zero (Tufte rule). Labels directly on bars "
                    "when <= 10 categories. Supports horizontal/vertical orientation and "
                    "optional grouping. Use for: category comparisons, rankings, part-to-whole "
                    "with stacked bars."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "x": {"type": "string", "description": "Column for x-axis (categories)"},
                        "y": {"type": "string", "description": "Column for y-axis (values)"},
                        "color": {"type": "string", "description": "Optional column to color/group bars"},
                        "orientation": {
                            "type": "string",
                            "enum": ["v", "h"],
                            "description": "Vertical (v) or horizontal (h). Use horizontal for long category names. Default: v.",
                        },
                        "barmode": {
                            "type": "string",
                            "enum": ["group", "stack", "relative"],
                            "description": "How to arrange grouped bars. Default: group.",
                        },
                        "title": {"type": "string", "description": "Insight-driven title (e.g. 'Engineering leads hiring at 40%')"},
                        "sort": {
                            "type": "boolean",
                            "description": "Sort bars by value (descending). Default: true.",
                        },
                    },
                    "required": ["dataset_id", "x", "y"],
                },
            },
            {
                "name": "viz_line_chart",
                "description": (
                    "[Descriptive/Predictive] Create a line chart for trends over time. "
                    "Supports multiple series. Non-zero Y-axis allowed when variation is "
                    "the story. Annotates turning points if detected. Use for: temporal "
                    "trends, period-over-period comparisons, forecast visualization."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "x": {"type": "string", "description": "Column for x-axis (typically dates/time)"},
                        "y": {
                            "type": "string",
                            "description": "Column for y-axis (values). For multiple series, use the color parameter.",
                        },
                        "color": {"type": "string", "description": "Optional column to split into multiple lines"},
                        "markers": {
                            "type": "boolean",
                            "description": "Show data point markers on the line. Default: false.",
                        },
                        "title": {"type": "string", "description": "Insight-driven title"},
                    },
                    "required": ["dataset_id", "x", "y"],
                },
            },
            {
                "name": "viz_scatter_plot",
                "description": (
                    "[Diagnostic] Create a scatter plot for correlation analysis. "
                    "Optional color encoding for a 3rd variable and size for a 4th. "
                    "Can overlay a trend line (OLS). Use for: relationship discovery, "
                    "outlier identification, cluster visualization."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "x": {"type": "string", "description": "Column for x-axis"},
                        "y": {"type": "string", "description": "Column for y-axis"},
                        "color": {"type": "string", "description": "Optional column for color encoding (categorical or numeric)"},
                        "size": {"type": "string", "description": "Optional column for bubble size (numeric)"},
                        "trendline": {
                            "type": "string",
                            "enum": ["ols", "lowess", "none"],
                            "description": "Add a trend line. Default: none.",
                        },
                        "title": {"type": "string", "description": "Insight-driven title"},
                    },
                    "required": ["dataset_id", "x", "y"],
                },
            },
            {
                "name": "viz_histogram",
                "description": (
                    "[Descriptive] Create a histogram to show distribution of a numeric "
                    "column. Auto-selects optimal bin count. Consistent bin sizes enforced "
                    "(Tufte rule). Use for: understanding spread, skew, normality, and outliers."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "column": {"type": "string", "description": "Numeric column to visualize"},
                        "nbins": {
                            "type": "integer",
                            "description": "Number of bins. If omitted, auto-selected using Sturges' rule.",
                        },
                        "color": {"type": "string", "description": "Optional column to split into overlapping histograms"},
                        "title": {"type": "string", "description": "Insight-driven title"},
                    },
                    "required": ["dataset_id", "column"],
                },
            },
            {
                "name": "viz_box_plot",
                "description": (
                    "[Descriptive/Diagnostic] Create a box plot for distribution comparison "
                    "across categories. Highlights outliers. Optional overlay of individual "
                    "points. Use for: comparing spread/median across groups, identifying "
                    "outliers within segments."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "y": {"type": "string", "description": "Numeric column for values"},
                        "x": {"type": "string", "description": "Optional categorical column for grouping"},
                        "color": {"type": "string", "description": "Optional additional grouping by color"},
                        "points": {
                            "type": "string",
                            "enum": ["all", "outliers", "none"],
                            "description": "Which points to show. Default: outliers.",
                        },
                        "title": {"type": "string", "description": "Insight-driven title"},
                    },
                    "required": ["dataset_id", "y"],
                },
            },
            {
                "name": "viz_heatmap",
                "description": (
                    "[Diagnostic] Create a heatmap for visualizing matrices, cross-tabulations, "
                    "or multi-variable patterns. Sequential colorblind-safe palette auto-applied. "
                    "Annotated cells for readability. Use for: correlation matrices, "
                    "pivot tables, feature importance grids."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "x": {"type": "string", "description": "Column for x-axis categories"},
                        "y": {"type": "string", "description": "Column for y-axis categories"},
                        "values": {"type": "string", "description": "Column for cell values (numeric). If 'correlation', computes correlation matrix of all numeric columns."},
                        "title": {"type": "string", "description": "Insight-driven title"},
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "viz_pie_chart",
                "description": (
                    "[Descriptive] Create a pie chart for part-to-whole composition. "
                    "GUARDRAIL: Maximum 5 segments enforced — remaining values are grouped as "
                    "'Other'. Prefer viz_bar_chart with barmode='stack' for more than 5 "
                    "categories. Use sparingly — stacked bars are almost always better."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "names": {"type": "string", "description": "Column for slice labels (categorical)"},
                        "values": {"type": "string", "description": "Column for slice sizes (numeric)"},
                        "title": {"type": "string", "description": "Insight-driven title"},
                    },
                    "required": ["dataset_id", "names", "values"],
                },
            },
            {
                "name": "viz_recommend",
                "description": (
                    "[Meta] Given a data description and analytical goal, recommend the "
                    "best chart type, configuration, and color palette. Does NOT render a "
                    "chart — returns a recommendation for the LLM to use when calling the "
                    "actual rendering tool. Use before creating a chart when unsure which "
                    "type fits best."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "goal": {
                            "type": "string",
                            "description": "What the chart should communicate (e.g. 'compare sales by region', 'show revenue trend over time', 'find correlation between age and salary')",
                        },
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Columns involved in the visualization",
                        },
                    },
                    "required": ["dataset_id", "goal"],
                },
            },
        ]

    async def _execute_tool_mode(
        self, tool_name: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        raw_id = params.get("dataset_id") or params.get("dataset_name") or ""
        dataset_id = context.resolve_dataset_id(raw_id) or raw_id
        if dataset_id not in context.datasets:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Dataset '{dataset_id}' not found. Available: {context.dataset_ids}",
                error=f"Dataset not found: {dataset_id}",
            )

        df = context.datasets[dataset_id]

        dispatch = {
            "viz_bar_chart": self._bar_chart,
            "viz_line_chart": self._line_chart,
            "viz_scatter_plot": self._scatter_plot,
            "viz_histogram": self._histogram,
            "viz_box_plot": self._box_plot,
            "viz_heatmap": self._heatmap,
            "viz_pie_chart": self._pie_chart,
            "viz_recommend": self._recommend,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Unknown viz tool: {tool_name}",
                error=f"Unknown tool: {tool_name}",
            )

        return await handler(df, dataset_id, params, context)

    # ─── Tool implementations ─────────────────────────────────────────

    async def _bar_chart(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        x, y = params["x"], params["y"]
        missing = [c for c in [x, y] if c not in df.columns]
        if missing:
            return self._col_not_found(missing)

        color = params.get("color")
        if color and color not in df.columns:
            return self._col_not_found([color])

        orientation = params.get("orientation", "v")
        barmode = params.get("barmode", "group")
        sort_bars = params.get("sort", True)
        title = params.get("title", f"{y} by {x}")

        plot_df = df[[c for c in [x, y, color] if c is not None]].dropna(subset=[x, y])

        if sort_bars and color is None:
            plot_df = plot_df.sort_values(y, ascending=(orientation == "h"))

        fig_kwargs: dict[str, Any] = {"data_frame": plot_df, "title": title}
        if orientation == "h":
            fig_kwargs.update(x=y, y=x, orientation="h")
        else:
            fig_kwargs.update(x=x, y=y)

        if color:
            fig_kwargs["color"] = color
            fig_kwargs["color_discrete_sequence"] = get_color_palette("categorical", MAX_CHART_COLORS)
        else:
            fig_kwargs["color_discrete_sequence"] = get_color_palette("categorical", 1)

        fig_kwargs["barmode"] = barmode
        fig = px.bar(**fig_kwargs)

        # Apply Tufte defaults
        layout = get_plotly_layout_defaults(title)
        layout = apply_tufte_axes(layout, "bar")
        layout["barmode"] = barmode

        # Direct labels when <= 10 categories
        if plot_df[x if orientation == "v" else y].nunique() <= 10:
            fig.update_traces(textposition="outside", texttemplate="%{value:.4s}")

        # Single series: hide legend (Tufte: no legend if avoidable)
        if not color:
            layout["showlegend"] = False

        fig.update_layout(**layout)

        chart_json = json.loads(fig.to_json())

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.CHART,
            data={
                "chart_type": "bar",
                "chart_config": chart_json,
                "dataset_id": dataset_id,
                "columns_used": [x, y] + ([color] if color else []),
                "record_count": len(plot_df),
                "analytics_level": "descriptive",
            },
            summary=(
                f"Bar chart: {y} by {x}"
                + (f" (grouped by {color})" if color else "")
                + f". {len(plot_df)} records plotted."
            ),
        )

    async def _line_chart(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        x, y = params["x"], params["y"]
        missing = [c for c in [x, y] if c not in df.columns]
        if missing:
            return self._col_not_found(missing)

        color = params.get("color")
        if color and color not in df.columns:
            return self._col_not_found([color])

        markers = params.get("markers", False)
        title = params.get("title", f"{y} over {x}")

        plot_df = df[[c for c in [x, y, color] if c is not None]].dropna(subset=[x, y])
        plot_df = plot_df.sort_values(x)

        fig_kwargs: dict[str, Any] = {
            "data_frame": plot_df, "x": x, "y": y,
            "title": title, "markers": markers,
        }
        if color:
            fig_kwargs["color"] = color
            fig_kwargs["color_discrete_sequence"] = get_color_palette("categorical", MAX_CHART_COLORS)

        fig = px.line(**fig_kwargs)

        layout = get_plotly_layout_defaults(title)
        layout = apply_tufte_axes(layout, "line")

        if not color:
            layout["showlegend"] = False

        fig.update_layout(**layout)

        chart_json = json.loads(fig.to_json())

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.CHART,
            data={
                "chart_type": "line",
                "chart_config": chart_json,
                "dataset_id": dataset_id,
                "columns_used": [x, y] + ([color] if color else []),
                "record_count": len(plot_df),
                "analytics_level": "descriptive",
            },
            summary=(
                f"Line chart: {y} over {x}"
                + (f" (series: {color})" if color else "")
                + f". {len(plot_df)} data points."
            ),
        )

    async def _scatter_plot(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        x, y = params["x"], params["y"]
        missing = [c for c in [x, y] if c not in df.columns]
        if missing:
            return self._col_not_found(missing)

        color = params.get("color")
        size_col = params.get("size")
        trendline = params.get("trendline", "none")
        title = params.get("title", f"{y} vs {x}")

        extra_cols = [c for c in [color, size_col] if c is not None]
        for c in extra_cols:
            if c not in df.columns:
                return self._col_not_found([c])

        cols = [x, y] + extra_cols
        plot_df = df[cols].dropna(subset=[x, y])

        fig_kwargs: dict[str, Any] = {
            "data_frame": plot_df, "x": x, "y": y, "title": title,
        }
        if color:
            fig_kwargs["color"] = color
            if pd.api.types.is_numeric_dtype(plot_df[color]):
                fig_kwargs["color_continuous_scale"] = "Viridis"
            else:
                fig_kwargs["color_discrete_sequence"] = get_color_palette("categorical", MAX_CHART_COLORS)
        if size_col:
            fig_kwargs["size"] = size_col

        if trendline and trendline != "none":
            fig_kwargs["trendline"] = trendline

        fig = px.scatter(**fig_kwargs)

        layout = get_plotly_layout_defaults(title)
        layout = apply_tufte_axes(layout, "scatter")
        if not color:
            layout["showlegend"] = False
        fig.update_layout(**layout)

        chart_json = json.loads(fig.to_json())

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.CHART,
            data={
                "chart_type": "scatter",
                "chart_config": chart_json,
                "dataset_id": dataset_id,
                "columns_used": cols,
                "record_count": len(plot_df),
                "trendline": trendline,
                "analytics_level": "diagnostic",
            },
            summary=(
                f"Scatter plot: {y} vs {x}"
                + (f" (color: {color})" if color else "")
                + (f" (size: {size_col})" if size_col else "")
                + (f" with {trendline} trend line" if trendline != "none" else "")
                + f". {len(plot_df)} points."
            ),
        )

    async def _histogram(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        column = params["column"]
        if column not in df.columns:
            return self._col_not_found([column])

        color = params.get("color")
        if color and color not in df.columns:
            return self._col_not_found([color])

        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if len(series) == 0:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Column '{column}' has no valid numeric values for histogram.",
                error="No numeric data",
            )

        # Auto-select bins using Sturges' rule if not provided
        nbins = params.get("nbins")
        if nbins is None:
            nbins = max(int(np.ceil(np.log2(len(series)) + 1)), 5)

        title = params.get("title", f"Distribution of {column}")

        plot_df = df[[c for c in [column, color] if c is not None]].copy()
        plot_df[column] = pd.to_numeric(plot_df[column], errors="coerce")
        plot_df = plot_df.dropna(subset=[column])

        fig_kwargs: dict[str, Any] = {
            "data_frame": plot_df, "x": column, "nbins": nbins, "title": title,
        }
        if color:
            fig_kwargs["color"] = color
            fig_kwargs["color_discrete_sequence"] = get_color_palette("categorical", MAX_CHART_COLORS)
            fig_kwargs["barmode"] = "overlay"
            fig_kwargs["opacity"] = 0.7

        fig = px.histogram(**fig_kwargs)

        layout = get_plotly_layout_defaults(title)
        layout = apply_tufte_axes(layout, "histogram")
        layout["yaxis"]["title"] = {"text": "Count"}
        if not color:
            layout["showlegend"] = False
        fig.update_layout(**layout)

        # Compute summary stats for the response
        stats = {
            "mean": round(float(series.mean()), 2),
            "median": round(float(series.median()), 2),
            "std": round(float(series.std()), 2),
            "skew": round(float(series.skew()), 2),
        }

        chart_json = json.loads(fig.to_json())

        skew_desc = "roughly symmetric"
        if stats["skew"] > 0.5:
            skew_desc = "right-skewed"
        elif stats["skew"] < -0.5:
            skew_desc = "left-skewed"

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.CHART,
            data={
                "chart_type": "histogram",
                "chart_config": chart_json,
                "dataset_id": dataset_id,
                "column": column,
                "nbins": nbins,
                "stats": stats,
                "record_count": len(series),
                "analytics_level": "descriptive",
            },
            summary=(
                f"Histogram of {column}: {len(series)} values, {nbins} bins. "
                f"Mean={stats['mean']}, median={stats['median']}, {skew_desc} (skew={stats['skew']})."
            ),
        )

    async def _box_plot(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        y_col = params["y"]
        if y_col not in df.columns:
            return self._col_not_found([y_col])

        x_col = params.get("x")
        color = params.get("color")
        points = params.get("points", "outliers")
        title = params.get("title", f"Distribution of {y_col}" + (f" by {x_col}" if x_col else ""))

        for c in [x_col, color]:
            if c and c not in df.columns:
                return self._col_not_found([c])

        cols = [c for c in [y_col, x_col, color] if c is not None]
        plot_df = df[cols].dropna(subset=[y_col])

        fig_kwargs: dict[str, Any] = {
            "data_frame": plot_df, "y": y_col, "title": title,
        }
        if x_col:
            fig_kwargs["x"] = x_col
        if color:
            fig_kwargs["color"] = color
            fig_kwargs["color_discrete_sequence"] = get_color_palette("categorical", MAX_CHART_COLORS)
        if points == "all":
            fig_kwargs["points"] = "all"
        elif points == "outliers":
            fig_kwargs["points"] = "outliers"
        else:
            fig_kwargs["points"] = False

        fig = px.box(**fig_kwargs)

        layout = get_plotly_layout_defaults(title)
        layout = apply_tufte_axes(layout, "box")
        if not color and not x_col:
            layout["showlegend"] = False
        fig.update_layout(**layout)

        chart_json = json.loads(fig.to_json())

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.CHART,
            data={
                "chart_type": "box",
                "chart_config": chart_json,
                "dataset_id": dataset_id,
                "columns_used": cols,
                "record_count": len(plot_df),
                "analytics_level": "descriptive",
            },
            summary=(
                f"Box plot: {y_col}"
                + (f" grouped by {x_col}" if x_col else "")
                + (f" (color: {color})" if color else "")
                + f". {len(plot_df)} values. Points shown: {points}."
            ),
        )

    async def _heatmap(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        values_col = params.get("values", "")
        title = params.get("title", "Heatmap")

        # Correlation matrix mode
        if values_col == "correlation" or (not params.get("x") and not params.get("y")):
            numeric_df = df.select_dtypes(include=[np.number])
            if numeric_df.shape[1] < 2:
                return SpecialistResult(
                    success=False, specialist_name=self.name,
                    result_type=ResultType.ERROR, data=None,
                    summary="Need at least 2 numeric columns for a correlation heatmap.",
                    error="Insufficient numeric columns",
                )

            corr = numeric_df.corr()
            title = title if title != "Heatmap" else "Correlation matrix"

            fig = go.Figure(data=go.Heatmap(
                z=corr.values,
                x=corr.columns.tolist(),
                y=corr.index.tolist(),
                colorscale="RdBu_r",
                zmid=0,
                text=np.round(corr.values, 2),
                texttemplate="%{text}",
                textfont={"size": 10},
                hoverongaps=False,
            ))

            layout = get_plotly_layout_defaults(title)
            layout = apply_tufte_axes(layout, "heatmap")
            layout["yaxis"]["autorange"] = "reversed"
            fig.update_layout(**layout)

            chart_json = json.loads(fig.to_json())

            return SpecialistResult(
                success=True,
                specialist_name=self.name,
                result_type=ResultType.CHART,
                data={
                    "chart_type": "heatmap",
                    "chart_config": chart_json,
                    "dataset_id": dataset_id,
                    "mode": "correlation",
                    "columns": corr.columns.tolist(),
                    "analytics_level": "diagnostic",
                },
                summary=f"Correlation heatmap for {len(corr.columns)} numeric columns. Diverging palette (blue=negative, red=positive).",
            )

        # Cross-tabulation / pivot mode
        x_col = params.get("x", "")
        y_col = params.get("y", "")
        for c in [x_col, y_col, values_col]:
            if c and c not in df.columns:
                return self._col_not_found([c])

        if not x_col or not y_col or not values_col:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary="Heatmap requires x, y, and values columns (or set values='correlation' for a correlation matrix).",
                error="Missing required columns",
            )

        pivot = df.pivot_table(index=y_col, columns=x_col, values=values_col, aggfunc="mean")

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[str(c) for c in pivot.columns],
            y=[str(r) for r in pivot.index],
            colorscale="Viridis",
            text=np.round(pivot.values, 2),
            texttemplate="%{text}",
            textfont={"size": 10},
            hoverongaps=False,
        ))

        title = title if title != "Heatmap" else f"{values_col} by {y_col} and {x_col}"
        layout = get_plotly_layout_defaults(title)
        layout = apply_tufte_axes(layout, "heatmap")
        layout["yaxis"]["autorange"] = "reversed"
        fig.update_layout(**layout)

        chart_json = json.loads(fig.to_json())

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.CHART,
            data={
                "chart_type": "heatmap",
                "chart_config": chart_json,
                "dataset_id": dataset_id,
                "mode": "pivot",
                "columns_used": [x_col, y_col, values_col],
                "analytics_level": "diagnostic",
            },
            summary=f"Heatmap: {values_col} by {y_col} x {x_col}. {pivot.shape[0]} rows x {pivot.shape[1]} columns.",
        )

    async def _pie_chart(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        names_col = params["names"]
        values_col = params["values"]
        for c in [names_col, values_col]:
            if c not in df.columns:
                return self._col_not_found([c])

        title = params.get("title", f"Composition of {values_col} by {names_col}")

        plot_df = df[[names_col, values_col]].dropna()
        agg = plot_df.groupby(names_col)[values_col].sum().reset_index()
        agg = agg.sort_values(values_col, ascending=False)

        # Enforce max 5 segments — group remainder as "Other"
        grouped = False
        if len(agg) > MAX_PIE_SEGMENTS:
            top = agg.head(MAX_PIE_SEGMENTS - 1)
            other_sum = agg.iloc[MAX_PIE_SEGMENTS - 1:][values_col].sum()
            other_row = pd.DataFrame([{names_col: "Other", values_col: other_sum}])
            agg = pd.concat([top, other_row], ignore_index=True)
            grouped = True

        fig = px.pie(
            agg, names=names_col, values=values_col, title=title,
            color_discrete_sequence=get_color_palette("categorical", len(agg)),
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hoverinfo="label+percent+value",
        )

        layout = get_plotly_layout_defaults(title)
        fig.update_layout(**layout)

        chart_json = json.loads(fig.to_json())

        segment_info = f"{len(agg)} segments"
        if grouped:
            segment_info += f" (top {MAX_PIE_SEGMENTS - 1} + 'Other')"

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.CHART,
            data={
                "chart_type": "pie",
                "chart_config": chart_json,
                "dataset_id": dataset_id,
                "columns_used": [names_col, values_col],
                "segment_count": len(agg),
                "grouped_to_other": grouped,
                "analytics_level": "descriptive",
                "note": "Consider using a stacked bar chart for more precise comparison." if grouped else "",
            },
            summary=(
                f"Pie chart: {values_col} by {names_col}. {segment_info}."
                + (" Values beyond top 4 grouped as 'Other'." if grouped else "")
            ),
        )

    async def _recommend(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        goal = params.get("goal", "")
        columns = params.get("columns", [])

        # Classify columns
        col_info = {}
        for col in columns:
            if col not in df.columns:
                continue
            series = df[col]
            if pd.api.types.is_numeric_dtype(series):
                col_info[col] = "numeric"
            elif pd.api.types.is_datetime64_any_dtype(series):
                col_info[col] = "datetime"
            elif pd.api.types.is_bool_dtype(series):
                col_info[col] = "boolean"
            else:
                nunique = series.nunique()
                col_info[col] = "categorical" if nunique <= 20 else "high_cardinality"

        # Infer chart goal from user description
        goal_lower = goal.lower()
        inferred_goal = None

        goal_keywords = {
            ChartGoal.SHOW_TREND: ["trend", "over time", "temporal", "time series", "forecast", "growth"],
            ChartGoal.COMPARE_CATEGORIES: ["compare", "category", "categories", "ranking", "rank", "by group", "versus"],
            ChartGoal.SHOW_CORRELATION: ["correlation", "relationship", "scatter", "vs", "against"],
            ChartGoal.SHOW_DISTRIBUTION: ["distribution", "spread", "histogram", "shape", "skew", "normal"],
            ChartGoal.SHOW_COMPOSITION: ["composition", "part of", "proportion", "breakdown", "share", "split"],
            ChartGoal.SHOW_MANY_VARIABLES: ["heatmap", "matrix", "many variables", "cross-tab", "pivot"],
        }

        for chart_goal, keywords in goal_keywords.items():
            if any(kw in goal_lower for kw in keywords):
                inferred_goal = chart_goal
                break

        # Fallback: infer from column types
        if inferred_goal is None:
            types = list(col_info.values())
            has_datetime = "datetime" in types
            numeric_count = types.count("numeric")
            has_categorical = "categorical" in types

            if has_datetime and numeric_count >= 1:
                inferred_goal = ChartGoal.SHOW_TREND
            elif numeric_count >= 2:
                inferred_goal = ChartGoal.SHOW_CORRELATION
            elif has_categorical and numeric_count >= 1:
                inferred_goal = ChartGoal.COMPARE_CATEGORIES
            elif numeric_count == 1:
                inferred_goal = ChartGoal.SHOW_DISTRIBUTION
            else:
                inferred_goal = ChartGoal.COMPARE_CATEGORIES

        rec = get_chart_recommendation(inferred_goal.value)

        # Determine color palette type
        palette_type = "categorical"
        if inferred_goal in (ChartGoal.SHOW_TREND, ChartGoal.SHOW_DISTRIBUTION):
            palette_type = "sequential"
        elif inferred_goal == ChartGoal.SHOW_MANY_VARIABLES:
            palette_type = "diverging"

        n_categories = max(
            (df[col].nunique() for col in col_info if col_info[col] == "categorical"),
            default=3,
        )
        palette = get_color_palette(palette_type, min(n_categories, MAX_CHART_COLORS))

        recommendation = {
            "inferred_goal": inferred_goal.value,
            "recommended_chart": rec.primary_chart if rec else "bar",
            "recommended_tool": rec.tool_name if rec else "viz_bar_chart",
            "alternatives": rec.alternatives if rec else [],
            "column_types": col_info,
            "palette_type": palette_type,
            "palette_colors": palette,
            "anti_patterns_relevant": [
                ap for ap in CHART_ANTI_PATTERNS
                if any(kw in ap["pattern"].lower() for kw in [rec.primary_chart if rec else ""])
            ],
            "rationale": rec.when_to_use if rec else "Default recommendation.",
        }

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.TEXT,
            data=recommendation,
            summary=(
                f"Recommendation: use {recommendation['recommended_chart']} chart "
                f"(tool: {recommendation['recommended_tool']}). "
                f"Goal: {inferred_goal.value}. Palette: {palette_type}."
            ),
        )

    # ─── Helpers ──────────────────────────────────────────────────────

    def _col_not_found(self, columns: list[str]) -> SpecialistResult:
        return SpecialistResult(
            success=False,
            specialist_name=self.name,
            result_type=ResultType.ERROR,
            data=None,
            summary=f"Column(s) not found: {columns}",
            error=f"Missing columns: {columns}",
        )
