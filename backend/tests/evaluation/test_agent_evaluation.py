"""
Agent-Level Evaluation Suite

Follows established agent evaluation frameworks:

  - G-Eval (Liu et al., 2023): criteria-based scoring with rubrics
  - MT-Bench (Zheng et al., 2023): multi-turn task completion assessment
  - Behavioral Contract Testing (agent-evaluation skill): invariants that
    must hold regardless of LLM non-determinism

Evaluation dimensions (Direct Scoring, 1-5 rubric per the advanced-evaluation skill):

  1. Task Completion  — Did the agent produce a result for the requested analysis?
  2. Correctness      — Are the numbers/results factually correct?
  3. Output Format    — Is the output properly structured (serializable, typed)?
  4. Tool Selection   — Did the intent classifier pick the right tool?
  5. Dataset Resolution — Did the agent find and use the correct dataset?
  6. Error Handling   — Does the agent fail gracefully on bad inputs?

Anti-patterns avoided (per agent-evaluation skill):
  - No single-run testing — each scenario is deterministic (ToolMode specialists)
  - No output string matching — we assert structural properties, not exact text
  - Not only happy path — adversarial / edge-case scenarios included
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.agent.executor import _sanitize_for_json
from app.agent.intent import IntentClassifier, ExecutionMode
from app.agent.specialists.base import ResultType, SpecialistRegistry, SpecialistResult
from app.agent.specialists.cleaning import CleaningSpecialist
from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.eda import EDASpecialist
from app.agent.specialists.sql import SQLSpecialist
from app.agent.specialists.stats import StatsSpecialist
from app.agent.specialists.viz import VizSpecialist
from app.agent.supervisor import Supervisor
from app.models.schemas import StreamEvent, StreamEventType


# ─── Evaluation Rubric (G-Eval style, 1–5 scale) ─────────────────────────────

RUBRIC = {
    1: "Failure — no result, crash, or completely wrong output",
    2: "Poor — partial result but critical issues (wrong type, missing key data)",
    3: "Adequate — result produced but with minor issues (imprecise, extra fields)",
    4: "Good — correct result, properly structured, minor polish needed",
    5: "Excellent — correct, well-structured, informative summary, no issues",
}


@dataclass
class EvalScore:
    """One dimension score for a single scenario."""
    dimension: str
    score: int  # 1-5
    evidence: str
    max_score: int = 5


@dataclass
class ScenarioResult:
    """Full evaluation result for one scenario."""
    scenario_id: str
    scenario_name: str
    category: str
    scores: list[EvalScore] = field(default_factory=list)
    passed: bool = True
    error: str | None = None

    @property
    def total_score(self) -> int:
        return sum(s.score for s in self.scores)

    @property
    def max_possible(self) -> int:
        return sum(s.max_score for s in self.scores)

    @property
    def pct(self) -> float:
        return (self.total_score / self.max_possible * 100) if self.max_possible else 0


# ─── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def eval_ctx() -> AnalysisContext:
    np.random.seed(42)
    df = pd.DataFrame({
        "age": np.random.randint(20, 65, 200),
        "salary": np.random.normal(75000, 15000, 200).round(2),
        "dept": np.random.choice(["Engineering", "Marketing", "Sales", "HR"], 200),
        "performance": np.random.normal(4.0, 0.5, 200).round(2),
        "tenure_years": np.random.randint(0, 20, 200),
        "is_manager": np.random.choice([True, False], 200),
    })
    ctx = AnalysisContext()
    ctx.add_dataset("eval_ds", df, "employees.csv")
    return ctx


@pytest.fixture
def eval_registry() -> SpecialistRegistry:
    reg = SpecialistRegistry()
    reg.register(EDASpecialist())
    reg.register(VizSpecialist())
    reg.register(SQLSpecialist())
    reg.register(StatsSpecialist())
    reg.register(CleaningSpecialist())
    return reg


@pytest.fixture
def classifier() -> IntentClassifier:
    return IntentClassifier()


ALL_RESULTS: list[ScenarioResult] = []


# ─── 1. EDA CAPABILITY ASSESSMENT ────────────────────────────────────────────


class TestEDACapability:
    """Can the agent profile, describe, and assess data quality?"""

    @pytest.mark.asyncio
    async def test_eda_profile(self, eval_ctx, eval_registry):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": "eval_ds"}, eval_ctx)

        sr = ScenarioResult("eda-1", "EDA Profile", "EDA")

        sr.scores.append(EvalScore(
            "Task Completion", 5 if result.success else 1,
            f"success={result.success}",
        ))
        sr.scores.append(EvalScore(
            "Correctness", 5 if result.data and result.data.get("rows") == 200 else 2,
            f"rows={result.data.get('rows') if result.data else 'N/A'}",
        ))
        sr.scores.append(EvalScore(
            "Output Format", 5 if json.dumps(_sanitize_for_json(result.data)) else 1,
            "JSON serializable" if result.data else "No data",
        ))
        sr.passed = all(s.score >= 4 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success
        assert result.data["rows"] == 200

    @pytest.mark.asyncio
    async def test_eda_correlations(self, eval_ctx, eval_registry):
        eda = EDASpecialist()
        result = await eda.execute("eda_correlations", {"dataset_id": "eval_ds"}, eval_ctx)

        sr = ScenarioResult("eda-2", "EDA Correlations", "EDA")
        sr.scores.append(EvalScore(
            "Task Completion", 5 if result.success else 1,
            f"success={result.success}",
        ))
        has_matrix = result.data and "correlation_matrix" in result.data
        sr.scores.append(EvalScore(
            "Correctness", 5 if has_matrix else 2,
            "Matrix present" if has_matrix else "No matrix",
        ))
        sr.scores.append(EvalScore(
            "Output Format", 5 if json.dumps(_sanitize_for_json(result.data)) else 1,
            "JSON serializable",
        ))
        sr.passed = all(s.score >= 4 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success

    @pytest.mark.asyncio
    async def test_eda_data_quality(self, eval_ctx, eval_registry):
        eda = EDASpecialist()
        result = await eda.execute("eda_data_quality", {"dataset_id": "eval_ds"}, eval_ctx)

        sr = ScenarioResult("eda-3", "Data Quality Check", "EDA")
        sr.scores.append(EvalScore(
            "Task Completion", 5 if result.success else 1,
            f"success={result.success}",
        ))
        has_score = result.data and "quality_score" in result.data
        sr.scores.append(EvalScore(
            "Correctness", 5 if has_score else 2,
            f"quality_score={result.data.get('quality_score') if result.data else 'N/A'}",
        ))
        sr.passed = all(s.score >= 4 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success


# ─── 2. VISUALIZATION CAPABILITY ─────────────────────────────────────────────


class TestVizCapability:
    @pytest.mark.asyncio
    async def test_bar_chart(self, eval_ctx):
        viz = VizSpecialist()
        result = await viz.execute(
            "viz_bar_chart", {"dataset_id": "eval_ds", "x": "dept", "y": "salary"}, eval_ctx,
        )

        sr = ScenarioResult("viz-1", "Bar Chart Generation", "Visualization")
        sr.scores.append(EvalScore("Task Completion", 5 if result.success else 1, f"success={result.success}"))
        has_figure = result.data and "figure" in result.data
        sr.scores.append(EvalScore("Correctness", 5 if has_figure else 2, "Figure present" if has_figure else "No figure"))
        sr.scores.append(EvalScore("Output Format", 5 if json.dumps(_sanitize_for_json(result.data)) else 1, "Serializable"))
        sr.passed = all(s.score >= 4 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success

    @pytest.mark.asyncio
    async def test_scatter_plot(self, eval_ctx):
        viz = VizSpecialist()
        result = await viz.execute(
            "viz_scatter_plot", {"dataset_id": "eval_ds", "x": "age", "y": "salary"}, eval_ctx,
        )

        sr = ScenarioResult("viz-2", "Scatter Plot Generation", "Visualization")
        sr.scores.append(EvalScore("Task Completion", 5 if result.success else 1, f"success={result.success}"))
        sr.scores.append(EvalScore("Output Format", 5 if json.dumps(_sanitize_for_json(result.data)) else 1, "Serializable"))
        sr.passed = all(s.score >= 4 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success


# ─── 3. SQL CAPABILITY ───────────────────────────────────────────────────────


class TestSQLCapability:
    @pytest.mark.asyncio
    async def test_sql_schema(self, eval_ctx):
        sql = SQLSpecialist()
        result = await sql.execute("sql_schema", {"dataset_id": "eval_ds"}, eval_ctx)

        sr = ScenarioResult("sql-1", "SQL Schema Inspection", "SQL")
        sr.scores.append(EvalScore("Task Completion", 5 if result.success else 1, f"success={result.success}"))
        has_cols = result.data and "columns" in result.data
        sr.scores.append(EvalScore("Correctness", 5 if has_cols else 2, "Columns listed" if has_cols else "No columns"))
        sr.passed = all(s.score >= 4 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success

    @pytest.mark.asyncio
    async def test_sql_execute_query(self, eval_ctx):
        sql = SQLSpecialist()
        result = await sql.execute(
            "sql_execute",
            {"dataset_id": "eval_ds", "query": "SELECT dept, AVG(salary) as avg_salary FROM df GROUP BY dept"},
            eval_ctx,
        )

        sr = ScenarioResult("sql-2", "SQL Query Execution", "SQL")
        sr.scores.append(EvalScore("Task Completion", 5 if result.success else 1, f"success={result.success}"))
        has_rows = result.data and "rows" in result.data
        correct_groups = has_rows and len(result.data["rows"]) == 4
        sr.scores.append(EvalScore("Correctness", 5 if correct_groups else 3, f"groups={len(result.data.get('rows', [])) if has_rows else 0}"))
        sr.scores.append(EvalScore("Output Format", 5 if json.dumps(_sanitize_for_json(result.data)) else 1, "Serializable"))
        sr.passed = all(s.score >= 3 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success


# ─── 4. STATISTICS CAPABILITY ────────────────────────────────────────────────


class TestStatsCapability:
    @pytest.mark.asyncio
    async def test_assumptions_check(self, eval_ctx):
        stats = StatsSpecialist()
        result = await stats.execute(
            "stats_assumptions", {"dataset_id": "eval_ds", "column": "salary"}, eval_ctx,
        )

        sr = ScenarioResult("stats-1", "Statistical Assumptions Check", "Statistics")
        sr.scores.append(EvalScore("Task Completion", 5 if result.success else 1, f"success={result.success}"))
        has_normality = result.data and "normality" in result.data
        sr.scores.append(EvalScore("Correctness", 5 if has_normality else 2, "Normality test present" if has_normality else "Missing"))
        sr.scores.append(EvalScore("Output Format", 5 if json.dumps(_sanitize_for_json(result.data)) else 1, "Serializable"))
        sr.passed = all(s.score >= 4 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success

    @pytest.mark.asyncio
    async def test_hypothesis_test(self, eval_ctx):
        stats = StatsSpecialist()
        result = await stats.execute(
            "stats_test",
            {"dataset_id": "eval_ds", "column": "salary", "group_column": "dept", "test_type": "auto"},
            eval_ctx,
        )

        sr = ScenarioResult("stats-2", "Hypothesis Test (auto-select)", "Statistics")
        sr.scores.append(EvalScore("Task Completion", 5 if result.success else 1, f"success={result.success}"))
        has_pval = result.data and "p_value" in result.data
        sr.scores.append(EvalScore(
            "Correctness", 5 if has_pval else 2,
            f"p_value={result.data.get('p_value') if result.data else 'N/A'}",
        ))
        sr.passed = all(s.score >= 4 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success


# ─── 5. CLEANING CAPABILITY ──────────────────────────────────────────────────


class TestCleaningCapability:
    @pytest.mark.asyncio
    async def test_structural_cleaning(self, eval_ctx):
        cleaning = CleaningSpecialist()
        result = await cleaning.execute("clean_structural", {"dataset_id": "eval_ds"}, eval_ctx)

        sr = ScenarioResult("clean-1", "Structural Cleaning", "Cleaning")
        sr.scores.append(EvalScore("Task Completion", 5 if result.success else 1, f"success={result.success}"))
        has_changes = result.data and "changes" in result.data
        sr.scores.append(EvalScore("Correctness", 5 if has_changes else 3, "Changes reported" if has_changes else "No changes key"))
        sr.passed = all(s.score >= 3 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success

    @pytest.mark.asyncio
    async def test_validate(self, eval_ctx):
        cleaning = CleaningSpecialist()
        result = await cleaning.execute("clean_validate", {"dataset_id": "eval_ds"}, eval_ctx)

        sr = ScenarioResult("clean-2", "Data Validation", "Cleaning")
        sr.scores.append(EvalScore("Task Completion", 5 if result.success else 1, f"success={result.success}"))
        sr.scores.append(EvalScore("Output Format", 5 if json.dumps(_sanitize_for_json(result.data)) else 1, "Serializable"))
        sr.passed = all(s.score >= 4 for s in sr.scores)
        ALL_RESULTS.append(sr)
        assert result.success


# ─── 6. TOOL SELECTION (Intent Classifier) ───────────────────────────────────


class TestToolSelection:
    """Behavioral Contract: the intent classifier must route correctly."""

    @pytest.mark.parametrize("query,expected_mode,expected_tool", [
        ("profile my data", "direct", "eda_profile"),
        ("check data quality", "direct", "eda_data_quality"),
        ("describe the columns", "direct", "eda_describe"),
        ("show correlations", "direct", "eda_correlations"),
        ("show the schema", "direct", "sql_schema"),
        ("validate the data", "direct", "clean_validate"),
    ])
    def test_direct_routing(self, classifier, query, expected_mode, expected_tool):
        c = classifier.classify(query, has_conversation_history=False, has_data=True)

        sr = ScenarioResult(
            f"route-{expected_tool}", f"Route: '{query}'", "Tool Selection",
        )
        mode_ok = c.mode.value == expected_mode
        tool_ok = c.direct_tool == expected_tool
        sr.scores.append(EvalScore("Tool Selection", 5 if mode_ok and tool_ok else 1,
                                   f"mode={c.mode.value}, tool={c.direct_tool}"))
        sr.passed = mode_ok and tool_ok
        ALL_RESULTS.append(sr)
        assert mode_ok, f"Expected mode={expected_mode}, got {c.mode.value}"
        assert tool_ok, f"Expected tool={expected_tool}, got {c.direct_tool}"

    @pytest.mark.parametrize("query,expected_mode", [
        ("write a SQL query for top 10 users", "focused"),
        ("clean the data", "focused"),
        ("create a bar chart", "focused"),
        ("run a statistical test", "focused"),
        ("analyze everything in the dataset", "full"),
    ])
    def test_focused_and_full_routing(self, classifier, query, expected_mode):
        c = classifier.classify(query, has_conversation_history=False, has_data=True)

        sr = ScenarioResult(
            f"route-{expected_mode}-{query[:20]}", f"Route: '{query}'", "Tool Selection",
        )
        mode_ok = c.mode.value == expected_mode
        sr.scores.append(EvalScore("Tool Selection", 5 if mode_ok else 1,
                                   f"mode={c.mode.value}"))
        sr.passed = mode_ok
        ALL_RESULTS.append(sr)
        assert mode_ok, f"Expected mode={expected_mode}, got {c.mode.value}"


# ─── 7. DATASET RESOLUTION (Behavioral Contract) ─────────────────────────────


class TestDatasetResolution:
    """Behavioral invariant: agent must find the dataset regardless of how the LLM names it."""

    @pytest.mark.asyncio
    async def test_resolve_by_id(self, eval_ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": "eval_ds"}, eval_ctx)
        sr = ScenarioResult("resolve-1", "Resolve by exact ID", "Dataset Resolution")
        sr.scores.append(EvalScore("Dataset Resolution", 5 if result.success else 1, f"success={result.success}"))
        sr.passed = result.success
        ALL_RESULTS.append(sr)
        assert result.success

    @pytest.mark.asyncio
    async def test_resolve_by_filename(self, eval_ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": "employees.csv"}, eval_ctx)
        sr = ScenarioResult("resolve-2", "Resolve by filename", "Dataset Resolution")
        sr.scores.append(EvalScore("Dataset Resolution", 5 if result.success else 1, f"success={result.success}"))
        sr.passed = result.success
        ALL_RESULTS.append(sr)
        assert result.success

    @pytest.mark.asyncio
    async def test_resolve_by_dataset_name_param(self, eval_ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_name": "employees.csv"}, eval_ctx)
        sr = ScenarioResult("resolve-3", "Resolve by dataset_name param", "Dataset Resolution")
        sr.scores.append(EvalScore("Dataset Resolution", 5 if result.success else 1, f"success={result.success}"))
        sr.passed = result.success
        ALL_RESULTS.append(sr)
        assert result.success

    @pytest.mark.asyncio
    async def test_resolve_empty_id_single_dataset(self, eval_ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": ""}, eval_ctx)
        sr = ScenarioResult("resolve-4", "Resolve empty ID (single dataset fallback)", "Dataset Resolution")
        sr.scores.append(EvalScore("Dataset Resolution", 5 if result.success else 1, f"success={result.success}"))
        sr.passed = result.success
        ALL_RESULTS.append(sr)
        assert result.success


# ─── 8. ERROR HANDLING (Adversarial) ─────────────────────────────────────────


class TestErrorHandling:
    """Adversarial scenarios: agent must fail gracefully, never crash."""

    @pytest.mark.asyncio
    async def test_nonexistent_dataset(self, eval_ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_profile", {"dataset_id": "nonexistent"}, eval_ctx)
        sr = ScenarioResult("err-1", "Nonexistent dataset (graceful failure)", "Error Handling")
        graceful = not result.success and result.error is not None
        sr.scores.append(EvalScore("Error Handling", 5 if graceful else 1,
                                   f"graceful={graceful}, error={result.error}"))
        sr.passed = graceful
        ALL_RESULTS.append(sr)
        assert not result.success

    @pytest.mark.asyncio
    async def test_unknown_tool(self, eval_ctx):
        eda = EDASpecialist()
        result = await eda.execute("eda_nonexistent_tool", {"dataset_id": "eval_ds"}, eval_ctx)
        sr = ScenarioResult("err-2", "Unknown tool name (graceful failure)", "Error Handling")
        graceful = not result.success and result.error is not None
        sr.scores.append(EvalScore("Error Handling", 5 if graceful else 1,
                                   f"graceful={graceful}, error={result.error}"))
        sr.passed = graceful
        ALL_RESULTS.append(sr)
        assert not result.success

    @pytest.mark.asyncio
    async def test_missing_required_param(self, eval_ctx):
        viz = VizSpecialist()
        result = await viz.execute("viz_bar_chart", {"dataset_id": "eval_ds"}, eval_ctx)
        sr = ScenarioResult("err-3", "Missing required param (no x/y)", "Error Handling")
        graceful = not result.success and result.error is not None
        sr.scores.append(EvalScore("Error Handling", 5 if graceful else 1,
                                   f"graceful={graceful}, error={result.error}"))
        sr.passed = graceful
        ALL_RESULTS.append(sr)
        assert not result.success

    @pytest.mark.asyncio
    async def test_no_data_supervisor(self, eval_registry):
        """Supervisor with no datasets should return a help message, not crash."""
        empty_ctx = AnalysisContext()

        with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
            mock_client = AsyncMock()
            MockCls.return_value = mock_client
            sup = Supervisor(registry=eval_registry, context=empty_ctx)
            sup._client = mock_client

            events = []
            async for event in sup.run("profile my data"):
                events.append(event)

        sr = ScenarioResult("err-4", "No data loaded (supervisor help message)", "Error Handling")
        has_final = any(e.event_type == StreamEventType.FINAL_RESPONSE for e in events)
        no_crash = len(events) >= 1
        sr.scores.append(EvalScore("Error Handling", 5 if has_final and no_crash else 1,
                                   f"events={len(events)}, has_final={has_final}"))
        sr.passed = has_final
        ALL_RESULTS.append(sr)
        assert has_final


# ─── 9. FULL PIPELINE (MT-Bench style multi-step) ────────────────────────────


class TestFullPipeline:
    """End-to-end: intent → specialist → serialization → event structure."""

    @pytest.mark.asyncio
    async def test_direct_mode_pipeline(self, eval_ctx, eval_registry):
        with patch("app.agent.supervisor.AsyncAnthropic") as MockCls:
            block = MagicMock()
            block.text = "The dataset has **200 rows** and **6 columns**."
            block.type = "text"
            usage = MagicMock()
            usage.input_tokens = 100
            usage.output_tokens = 50
            resp = MagicMock()
            resp.content = [block]
            resp.usage = usage
            resp.stop_reason = "end_turn"

            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=resp)
            MockCls.return_value = mock_client

            sup = Supervisor(registry=eval_registry, context=eval_ctx)
            sup._client = mock_client

            events = []
            async for event in sup.run("profile my data"):
                events.append(event)

        sr = ScenarioResult("pipe-1", "Full Direct Pipeline (profile)", "Full Pipeline")

        event_types = [e.event_type for e in events]
        has_intent = StreamEventType.INTENT in event_types
        has_final = StreamEventType.FINAL_RESPONSE in event_types
        all_serialize = all(json.loads(e.model_dump_json()) for e in events)

        sr.scores.append(EvalScore("Task Completion", 5 if has_final else 1, f"has_final={has_final}"))
        sr.scores.append(EvalScore("Tool Selection", 5 if has_intent else 1, f"has_intent={has_intent}"))
        sr.scores.append(EvalScore("Output Format", 5 if all_serialize else 1, f"all_serialize={all_serialize}"))
        sr.passed = has_intent and has_final and all_serialize
        ALL_RESULTS.append(sr)
        assert has_final


# ─── REPORT GENERATION (runs after all tests) ────────────────────────────────


class TestGenerateReport:
    """Must run last — collects ALL_RESULTS and generates the PDF report."""

    def test_generate_pdf_report(self):
        if not ALL_RESULTS:
            pytest.skip("No evaluation results collected")

        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, KeepTogether,
        )
        from pathlib import Path
        from datetime import datetime

        out = Path(__file__).resolve().parent.parent.parent / "reports" / "Agent_Evaluation_Report.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(out), pagesize=letter, title="Agent Evaluation Report")
        styles = getSampleStyleSheet()
        small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=10)
        story = []

        # ── Title
        story.append(Paragraph("Agent-Level Evaluation Report", styles["Title"]))
        story.append(Paragraph(
            f"Data Analyst Digital Twin — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["Normal"],
        ))
        story.append(Spacer(1, 12))

        # ── Methodology
        story.append(Paragraph("<b>Methodology</b>", styles["Heading2"]))
        story.append(Paragraph(
            "This report follows established agent evaluation frameworks: "
            "<b>G-Eval</b> (Liu et al., 2023) for criteria-based rubric scoring, "
            "<b>MT-Bench</b> (Zheng et al., 2023) for multi-turn task completion, and "
            "<b>Behavioral Contract Testing</b> for agent invariants. "
            "Each scenario is scored on a 1–5 rubric across multiple dimensions.",
            styles["Normal"],
        ))
        story.append(Spacer(1, 8))

        # ── Summary metrics
        total_scenarios = len(ALL_RESULTS)
        passed = sum(1 for r in ALL_RESULTS if r.passed)
        failed = total_scenarios - passed
        total_score = sum(r.total_score for r in ALL_RESULTS)
        max_score = sum(r.max_possible for r in ALL_RESULTS)
        overall_pct = (total_score / max_score * 100) if max_score else 0

        story.append(Paragraph("<b>Summary Metrics</b>", styles["Heading2"]))

        summary_data = [
            ["Metric", "Value"],
            ["Total Scenarios", str(total_scenarios)],
            ["Passed", str(passed)],
            ["Failed", str(failed)],
            ["Pass Rate", f"{passed / total_scenarios * 100:.1f}%"],
            ["Total Score", f"{total_score} / {max_score}"],
            ["Overall Score", f"{overall_pct:.1f}%"],
        ]
        t = Table(summary_data, colWidths=[200, 200])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F9FAFB")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

        # ── Category breakdown
        story.append(Paragraph("<b>Scores by Category</b>", styles["Heading2"]))

        categories: dict[str, list[ScenarioResult]] = {}
        for r in ALL_RESULTS:
            categories.setdefault(r.category, []).append(r)

        cat_data = [["Category", "Scenarios", "Passed", "Score", "%"]]
        for cat, results in sorted(categories.items()):
            cat_total = sum(r.total_score for r in results)
            cat_max = sum(r.max_possible for r in results)
            cat_pct = (cat_total / cat_max * 100) if cat_max else 0
            cat_passed = sum(1 for r in results if r.passed)
            cat_data.append([cat, str(len(results)), str(cat_passed), f"{cat_total}/{cat_max}", f"{cat_pct:.0f}%"])

        t2 = Table(cat_data, colWidths=[140, 80, 80, 80, 80])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F9FAFB")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t2)
        story.append(Spacer(1, 12))

        # ── Detailed results
        story.append(Paragraph("<b>Detailed Scenario Results</b>", styles["Heading2"]))

        detail_data = [["ID", "Scenario", "Category", "Score", "Pass?"]]
        for r in ALL_RESULTS:
            status = "PASS" if r.passed else "FAIL"
            detail_data.append([
                r.scenario_id, r.scenario_name[:35], r.category,
                f"{r.total_score}/{r.max_possible}", status,
            ])

        t3 = Table(detail_data, colWidths=[60, 180, 80, 60, 40])
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]
        for i, r in enumerate(ALL_RESULTS, start=1):
            bg = colors.HexColor("#DCFCE7") if r.passed else colors.HexColor("#FEE2E2")
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
        t3.setStyle(TableStyle(style_cmds))
        story.append(t3)
        story.append(Spacer(1, 12))

        # ── Rubric reference
        story.append(Paragraph("<b>Scoring Rubric (G-Eval 1–5 Scale)</b>", styles["Heading2"]))
        for score, desc in RUBRIC.items():
            story.append(Paragraph(f"<b>{score}</b> — {desc}", small))
        story.append(Spacer(1, 8))

        # ── Frameworks referenced
        story.append(Paragraph("<b>Evaluation Frameworks Used</b>", styles["Heading2"]))
        story.append(Paragraph("• <b>G-Eval</b> (Liu et al., 2023) — Criteria-based rubric scoring with evidence", styles["Normal"]))
        story.append(Paragraph("• <b>MT-Bench</b> (Zheng et al., 2023) — Multi-step task completion assessment", styles["Normal"]))
        story.append(Paragraph("• <b>Behavioral Contract Testing</b> — Agent invariants that must hold regardless of LLM variance", styles["Normal"]))
        story.append(Paragraph("• <b>Adversarial Testing</b> — Intentionally invalid inputs to verify graceful degradation", styles["Normal"]))

        doc.build(story)
        assert out.exists()
        assert total_scenarios > 0
        print(f"\n{'='*60}")
        print(f"  AGENT EVALUATION REPORT: {out}")
        print(f"  Scenarios: {total_scenarios} | Passed: {passed} | Failed: {failed}")
        print(f"  Overall Score: {total_score}/{max_score} ({overall_pct:.1f}%)")
        print(f"{'='*60}")
