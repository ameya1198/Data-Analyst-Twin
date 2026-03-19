"""
Pydantic output schemas for all specialists.

Each schema defines the exact JSON shape a specialist tool returns, validated
at construction time.  Every schema also exposes a `to_markdown()` method that
renders the result with proper tables and bullet points for the synthesis LLM.

Design principles (from @pydantic-ai structured-output pattern):
- Every field is typed — no stray `Any` dicts
- Optional fields have explicit defaults
- `to_markdown()` is the single source of formatted output
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Build a markdown table from headers and rows."""
    if not rows:
        return ""
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    body_lines = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([header_line, sep_line, *body_lines])


def _bullet(items: list[str]) -> str:
    """Render a list as markdown bullet points."""
    return "\n".join(f"- {item}" for item in items) if items else ""


# ═══════════════════════════════════════════════════════════════════════════════
# EDA Specialist Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class ColumnProfile(BaseModel):
    name: str
    dtype: str = ""
    inferred_type: str = ""
    non_null: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    unique: int = 0
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    avg_length: Optional[float] = None
    max_length: Optional[int] = None
    avg_words: Optional[float] = None
    top_values: Optional[dict[str, int]] = None

    model_config = {"extra": "allow"}


class ProfileResult(BaseModel):
    """eda_profile output."""
    dataset_id: str
    rows: int
    columns: int
    total_cells: int = 0
    null_cells: int = 0
    null_pct: float = 0.0
    duplicate_rows: int = 0
    duplicate_pct: float = 0.0
    quality_score: int = 0
    column_profiles: list[ColumnProfile] = Field(default_factory=list)
    workflow_phase: str = ""
    recommended_next: str = ""
    sampling_note: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [
            f"**Dataset**: {self.rows} rows × {self.columns} columns | "
            f"**Quality**: {self.quality_score}/100",
            "",
        ]
        # Column type counts
        type_counts: dict[str, int] = {}
        for cp in self.column_profiles:
            t = cp.inferred_type or "unknown"
            type_counts[t] = type_counts.get(t, 0) + 1
        type_str = ", ".join(f"{v} {k}" for k, v in type_counts.items())
        lines.append(f"**Column types**: {type_str}")
        lines.append("")

        # Column table
        headers = ["Column", "Type", "Non-null", "Nulls %", "Unique", "Mean", "Median", "Std", "Min", "Max"]
        rows: list[list[str]] = []
        for cp in self.column_profiles[:20]:
            rows.append([
                cp.name,
                cp.inferred_type or cp.dtype,
                str(cp.non_null),
                f"{cp.null_pct:.1f}%",
                str(cp.unique),
                f"{cp.mean:.2f}" if cp.mean is not None else "—",
                f"{cp.median:.2f}" if cp.median is not None else "—",
                f"{cp.std:.2f}" if cp.std is not None else "—",
                f"{cp.min:.2f}" if cp.min is not None else "—",
                f"{cp.max:.2f}" if cp.max is not None else "—",
            ])
        lines.append(_md_table(headers, rows))
        lines.append("")

        # Key findings
        flags: list[str] = []
        high_null = [cp for cp in self.column_profiles if cp.null_pct > 5]
        if high_null:
            worst = max(high_null, key=lambda c: c.null_pct)
            flags.append(f"Highest null rate: **{worst.name}** at **{worst.null_pct:.1f}%**")
        if self.duplicate_rows > 0:
            flags.append(f"Duplicate rows: **{self.duplicate_rows}** ({self.duplicate_pct:.1f}%)")
        if self.quality_score < 70:
            flags.append(f"Quality score below 70 — cleaning recommended before analysis")
        if flags:
            lines.append("**Key findings**:")
            lines.append(_bullet(flags))

        return "\n".join(lines)


class OutlierInfo(BaseModel):
    mild: int = 0
    extreme: int = 0
    pct: float = 0.0
    lower_fence: Optional[float] = None
    upper_fence: Optional[float] = None
    assessment: str = ""

    model_config = {"extra": "allow"}


class ColumnDescription(BaseModel):
    type: str = ""
    total_rows: int = 0
    non_null_count: int = 0
    null_count: int = 0
    unique: int = 0
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    min: Optional[Any] = None
    max: Optional[Any] = None
    q25: Optional[float] = None
    q75: Optional[float] = None
    skewness: Optional[float] = None
    skewness_label: Optional[str] = None
    skewness_action: Optional[str] = None
    kurtosis: Optional[float] = None
    heavy_tailed: Optional[bool] = None
    outliers: Optional[OutlierInfo] = None
    avg_char_length: Optional[float] = None
    max_char_length: Optional[int] = None
    avg_word_count: Optional[float] = None
    max_word_count: Optional[int] = None
    samples: Optional[list[str]] = None
    top_values: Optional[dict[str, int]] = None
    value_distribution_pct: Optional[dict[str, float]] = None
    range_days: Optional[int] = None

    model_config = {"extra": "allow"}


class DescribeResult(BaseModel):
    """eda_describe output."""
    dataset_id: str
    descriptions: dict[str, ColumnDescription]
    workflow_phase: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines: list[str] = []
        # Find total_rows from first description
        first = next(iter(self.descriptions.values()), None)
        if first and first.total_rows:
            lines.append(f"**Dataset**: {first.total_rows} rows")
            lines.append("")

        # Numeric columns table
        numeric_cols = {k: v for k, v in self.descriptions.items() if v.mean is not None}
        if numeric_cols:
            headers = ["Column", "Type", "Mean", "Median", "Std", "Min", "Max", "Skew", "Kurtosis", "Nulls"]
            rows: list[list[str]] = []
            for col, d in numeric_cols.items():
                rows.append([
                    col, d.type,
                    f"{d.mean:.2f}" if d.mean is not None else "—",
                    f"{d.median:.2f}" if d.median is not None else "—",
                    f"{d.std:.2f}" if d.std is not None else "—",
                    str(d.min) if d.min is not None else "—",
                    str(d.max) if d.max is not None else "—",
                    f"{d.skewness:.2f}" if d.skewness is not None else "—",
                    f"{d.kurtosis:.2f}" if d.kurtosis is not None else "—",
                    str(d.null_count),
                ])
            lines.append(_md_table(headers, rows))
            lines.append("")

        # Categorical columns table
        cat_cols = {k: v for k, v in self.descriptions.items()
                    if v.type in ("categorical", "text") and v.mean is None}
        if cat_cols:
            lines.append("**Categorical / Text columns**:")
            headers = ["Column", "Type", "Unique", "Top Value", "Nulls"]
            rows = []
            for col, d in cat_cols.items():
                top = "—"
                if d.top_values:
                    top_k = next(iter(d.top_values))
                    top = f"{top_k} ({d.top_values[top_k]})"
                rows.append([col, d.type, str(d.unique), top, str(d.null_count)])
            lines.append(_md_table(headers, rows))
            lines.append("")

        # Flags
        flags: list[str] = []
        for col, d in self.descriptions.items():
            if d.skewness is not None and abs(d.skewness) > 1:
                flags.append(f"**{col}**: skewness = {d.skewness:.2f} ({d.skewness_label or 'significant'})")
            if d.kurtosis is not None and d.kurtosis > 3:
                flags.append(f"**{col}**: kurtosis = {d.kurtosis:.2f} (heavy-tailed)")
            if d.outliers and d.outliers.pct > 0:
                total_outliers = d.outliers.mild + d.outliers.extreme
                detail_parts = [f"**{col}**: {total_outliers} outliers ({d.outliers.pct:.1f}%)"]
                if d.outliers.mild and d.outliers.extreme:
                    detail_parts.append(f"{d.outliers.mild} mild, {d.outliers.extreme} extreme")
                elif d.outliers.mild:
                    detail_parts.append(f"{d.outliers.mild} mild")
                elif d.outliers.extreme:
                    detail_parts.append(f"{d.outliers.extreme} extreme")
                flags.append(" — ".join(detail_parts))
        if flags:
            lines.append("**Flags**:")
            lines.append(_bullet(flags))

        return "\n".join(lines)


class CorrelationPair(BaseModel):
    col1: str
    col2: str
    correlation: float
    strength: str

    model_config = {"extra": "allow"}


class CorrelationsResult(BaseModel):
    """eda_correlations output."""
    dataset_id: str
    method: str = "pearson"
    matrix: dict[str, dict[str, float]] = Field(default_factory=dict)
    all_notable_pairs: list[CorrelationPair] = Field(default_factory=list)
    strong_correlations: list[CorrelationPair] = Field(default_factory=list)
    multicollinear_pairs: list[CorrelationPair] = Field(default_factory=list)
    numeric_columns: list[str] = Field(default_factory=list)
    workflow_phase: str = ""
    diagnostics: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines: list[str] = []

        notable = [p for p in self.all_notable_pairs if abs(p.correlation) >= 0.3]
        if notable:
            lines.append("**Notable correlations** (|r| ≥ 0.3):")
            lines.append("")
            headers = ["Variable A", "Variable B", "r", "Strength"]
            rows = [[p.col1, p.col2, f"{p.correlation:.3f}", p.strength] for p in notable]
            lines.append(_md_table(headers, rows))
            lines.append("")

        if self.multicollinear_pairs:
            mc = ", ".join(f"{p.col1} ↔ {p.col2} ({p.correlation:.3f})" for p in self.multicollinear_pairs)
            lines.append(f"**Multicollinearity flags**: {mc}")
        else:
            lines.append("**Multicollinearity flags**: None detected")

        if self.diagnostics:
            lines.append("")
            lines.append("**Diagnostics**:")
            lines.append(_bullet(self.diagnostics))

        return "\n".join(lines)


class ValueCountEntry(BaseModel):
    value: Optional[str] = None
    count: int = 0
    percentage: float = 0.0

    model_config = {"extra": "allow"}


class ValueCountsResult(BaseModel):
    """eda_value_counts output."""
    dataset_id: str
    column: str
    values: list[ValueCountEntry] = Field(default_factory=list)
    total_non_null: int = 0
    null_count: int = 0
    unique_count: int = 0
    workflow_phase: str = ""
    diagnostics: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [f"**{self.column}**: {self.unique_count} unique values, {self.null_count} nulls", ""]
        headers = ["Value", "Count", "%"]
        rows = [[str(v.value), str(v.count), f"{v.percentage:.1f}%"] for v in self.values[:20]]
        lines.append(_md_table(headers, rows))
        return "\n".join(lines)


class SmartStructureResult(BaseModel):
    """eda_smart_structure output."""
    original_dataset_id: str
    clean_dataset_id: str
    changes: list[str] = Field(default_factory=list)
    change_count: int = 0
    original_shape: list[int] = Field(default_factory=list)
    clean_shape: list[int] = Field(default_factory=list)
    quality_score_before: int = 0
    quality_score_after: int = 0
    quality_delta: int = 0
    workflow_phase: str = ""
    recommended_next: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        orig = f"{self.original_shape[0]}×{self.original_shape[1]}" if len(self.original_shape) == 2 else "?"
        clean = f"{self.clean_shape[0]}×{self.clean_shape[1]}" if len(self.clean_shape) == 2 else "?"
        lines = [
            f"**Before**: {orig} | **After**: {clean}",
            f"**Quality**: {self.quality_score_before} → {self.quality_score_after} (+{self.quality_delta})",
            "",
            f"**Changes applied** ({self.change_count}):",
            _bullet(self.changes),
        ]
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# SQL Specialist Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class SQLColumnSchema(BaseModel):
    name: str
    pandas_dtype: str = ""
    sql_type: str = ""
    null_pct: float = 0.0
    sample_values: list[Any] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class SQLTableSchema(BaseModel):
    dataset_id: str
    table_name: str
    rows: int = 0
    columns: list[SQLColumnSchema] = Field(default_factory=list)
    create_statement: str = ""

    model_config = {"extra": "allow"}


class SQLSchemaResult(BaseModel):
    """sql_schema output."""
    schemas: list[SQLTableSchema] = Field(default_factory=list)
    table_count: int = 0
    create_statements: str = ""
    usage_hint: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines: list[str] = []
        for tbl in self.schemas:
            lines.append(f"**Table `{tbl.table_name}`**: {tbl.rows} rows")
            lines.append("")
            headers = ["Column", "SQL Type", "Nulls %", "Samples"]
            rows = [
                [c.name, c.sql_type, f"{c.null_pct:.1f}%",
                 ", ".join(str(s) for s in c.sample_values[:3])]
                for c in tbl.columns
            ]
            lines.append(_md_table(headers, rows))
            lines.append("")
        return "\n".join(lines)


class AntiPatternWarning(BaseModel):
    pattern: str = ""
    problem: str = ""
    fix: str = ""

    model_config = {"extra": "allow"}


class SQLExecuteResult(BaseModel):
    """sql_execute output."""
    columns: list[str] = Field(default_factory=list)
    column_count: int = 0
    row_count: int = 0
    has_more_rows: bool = False
    preview: list[dict[str, Any]] = Field(default_factory=list)
    execution_ms: float = 0.0
    query: str = ""
    anti_pattern_warnings: list[AntiPatternWarning] = Field(default_factory=list)
    saved_as: Optional[str] = None

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines: list[str] = []
        if self.query:
            lines.append("```sql")
            lines.append(self.query)
            lines.append("```")
            lines.append("")

        if self.preview and self.columns:
            lines.append(f"**Result**: {self.row_count} rows × {self.column_count} columns ({self.execution_ms:.0f}ms)")
            lines.append("")
            headers = self.columns
            rows = []
            for row_dict in self.preview[:20]:
                rows.append([str(row_dict.get(c, "")) for c in headers])
            lines.append(_md_table(headers, rows))
            if self.has_more_rows:
                lines.append(f"_(showing first {len(self.preview)} of {self.row_count} rows)_")

        if self.anti_pattern_warnings:
            lines.append("")
            lines.append("**Warnings**:")
            lines.append(_bullet([f"**{w.pattern}**: {w.problem} → {w.fix}" for w in self.anti_pattern_warnings]))

        return "\n".join(lines)


class SQLValidateFinding(BaseModel):
    type: str = ""
    severity: str = ""
    issue: str = ""
    detail: str = ""
    fix: str = ""

    model_config = {"extra": "allow"}


class SQLValidateResult(BaseModel):
    """sql_validate output."""
    query: str = ""
    verdict: str = ""
    findings: list[SQLValidateFinding] = Field(default_factory=list)
    anti_pattern_count: int = 0
    style_issue_count: int = 0
    total_findings: int = 0

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [f"**Verdict**: {self.verdict} ({self.total_findings} findings)"]
        if self.findings:
            lines.append("")
            headers = ["Severity", "Type", "Issue", "Fix"]
            rows = [[f.severity, f.type, f.issue, f.fix] for f in self.findings]
            lines.append(_md_table(headers, rows))
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Viz Specialist Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class ChartResult(BaseModel):
    """Output for all viz_* chart tools."""
    chart_type: str
    chart_config: dict[str, Any] = Field(default_factory=dict)
    dataset_id: str = ""
    columns_used: list[str] = Field(default_factory=list)
    record_count: int = 0
    analytics_level: str = "descriptive"
    # Scatter-specific
    trendline: Optional[str] = None
    # Histogram-specific
    column: Optional[str] = None
    nbins: Optional[int] = None
    stats: Optional[dict[str, float]] = None
    # Pie-specific
    segment_count: Optional[int] = None
    grouped_to_other: Optional[bool] = None
    # Heatmap-specific
    mode: Optional[str] = None
    columns: Optional[list[str]] = None
    note: Optional[str] = None

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [f"**Chart**: {self.chart_type} | {self.record_count} records | columns: {', '.join(self.columns_used)}"]
        if self.stats:
            stat_parts = [f"{k}={v:.2f}" for k, v in self.stats.items()]
            lines.append(f"**Stats**: {', '.join(stat_parts)}")
        if self.note:
            lines.append(f"- {self.note}")
        return "\n".join(lines)


class VizRecommendResult(BaseModel):
    """viz_recommend output."""
    inferred_goal: str = ""
    recommended_chart: str = ""
    recommended_tool: str = ""
    alternatives: list[str] = Field(default_factory=list)
    column_types: dict[str, str] = Field(default_factory=dict)
    palette_type: str = ""
    palette_colors: list[str] = Field(default_factory=list)
    anti_patterns_relevant: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [
            f"**Recommended**: {self.recommended_chart} (`{self.recommended_tool}`)",
            f"**Goal**: {self.inferred_goal}",
            f"**Rationale**: {self.rationale}",
        ]
        if self.alternatives:
            lines.append(f"**Alternatives**: {', '.join(self.alternatives)}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Stats Specialist Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class NormalityResult(BaseModel):
    test: str = ""
    statistic: float = 0.0
    p_value: float = 0.0
    is_normal: bool = False
    n: int = 0

    model_config = {"extra": "allow"}


class EqualVarianceResult(BaseModel):
    levene_statistic: float = 0.0
    p_value: float = 0.0
    equal_variance: bool = False

    model_config = {"extra": "allow"}


class GroupStats(BaseModel):
    n: int = 0
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0

    model_config = {"extra": "allow"}


class StatsTestResult(BaseModel):
    """stats_test output."""
    dataset_id: str = ""
    column: str = ""
    group_column: Optional[str] = None
    test_name: str = ""
    test_statistic: Optional[float] = None
    p_value: float = 0.0
    alpha: float = 0.05
    significant: bool = False
    effect_size: Optional[float] = None
    effect_metric: Optional[str] = None
    effect_label: str = ""
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    assumptions: Optional[dict[str, Any]] = None
    interpretation: str = ""
    effect_interpretation: str = ""
    caveats: list[str] = Field(default_factory=list)
    group_stats: Optional[dict[str, GroupStats]] = None

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        sig_label = "Significant" if self.significant else "Not significant"
        lines = [f"**Result**: {sig_label} — {self.interpretation}", ""]

        headers = ["Metric", "Value"]
        rows = [
            ["Test", self.test_name],
            ["Statistic", f"{self.test_statistic:.4f}" if self.test_statistic is not None else "—"],
            ["p-value", f"{self.p_value:.4f}"],
            ["Effect size", f"{self.effect_size:.4f} ({self.effect_label})" if self.effect_size is not None else "—"],
        ]
        if self.ci_lower is not None and self.ci_upper is not None:
            rows.append(["95% CI", f"[{self.ci_lower:.4f}, {self.ci_upper:.4f}]"])
        lines.append(_md_table(headers, rows))

        if self.group_stats:
            lines.append("")
            lines.append("**Group statistics**:")
            g_headers = ["Group", "N", "Mean", "Median", "Std"]
            g_rows = [
                [name, str(gs.n), f"{gs.mean:.4f}", f"{gs.median:.4f}", f"{gs.std:.4f}"]
                for name, gs in self.group_stats.items()
            ]
            lines.append(_md_table(g_headers, g_rows))

        if self.caveats:
            lines.append("")
            lines.append("**Caveats**:")
            lines.append(_bullet(self.caveats))

        return "\n".join(lines)


class RegressionCoefficient(BaseModel):
    variable: str
    coefficient: float = 0.0
    p_value: float = 0.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    significant: bool = False
    odds_ratio: Optional[float] = None

    model_config = {"extra": "allow"}


class VIFEntry(BaseModel):
    variable: str
    vif: float = 0.0
    multicollinear: bool = False

    model_config = {"extra": "allow"}


class StatsRegressionResult(BaseModel):
    """stats_regression output."""
    regression_type: str = "linear"
    dataset_id: str = ""
    coefficients: list[RegressionCoefficient] = Field(default_factory=list)
    r_squared: Optional[float] = None
    adj_r_squared: Optional[float] = None
    f_statistic: Optional[float] = None
    f_p_value: Optional[float] = None
    n_observations: int = 0
    n_predictors: int = 0
    aic: Optional[float] = None
    bic: Optional[float] = None
    vif: list[VIFEntry] = Field(default_factory=list)
    residual_normality: Optional[NormalityResult] = None
    diagnostics: list[str] = Field(default_factory=list)
    # Logistic-specific
    auc: Optional[float] = None
    confusion_matrix: Optional[dict[str, int]] = None
    accuracy: Optional[float] = None
    pseudo_r_squared: Optional[float] = None
    log_likelihood: Optional[float] = None

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines: list[str] = []
        if self.regression_type == "linear":
            lines.append(f"**Linear Regression**: R² = {self.r_squared:.4f}, Adj R² = {self.adj_r_squared:.4f}, "
                         f"F = {self.f_statistic:.2f} (p = {self.f_p_value:.4f})" if self.r_squared is not None else "**Linear Regression**")
        else:
            parts = [f"**Logistic Regression**"]
            if self.auc is not None:
                parts.append(f"AUC = {self.auc:.4f}")
            if self.accuracy is not None:
                parts.append(f"Accuracy = {self.accuracy:.4f}")
            lines.append(", ".join(parts))

        lines.append(f"N = {self.n_observations}, Predictors = {self.n_predictors}")
        lines.append("")

        # Coefficients table
        if self.regression_type == "logistic":
            headers = ["Variable", "Coeff", "Odds Ratio", "p-value", "95% CI", "Sig"]
            rows = [
                [c.variable, f"{c.coefficient:.4f}",
                 f"{c.odds_ratio:.4f}" if c.odds_ratio is not None else "—",
                 f"{c.p_value:.4f}", f"[{c.ci_lower:.4f}, {c.ci_upper:.4f}]",
                 "✓" if c.significant else "✗"]
                for c in self.coefficients
            ]
        else:
            headers = ["Variable", "Coefficient", "p-value", "95% CI", "Sig"]
            rows = [
                [c.variable, f"{c.coefficient:.4f}", f"{c.p_value:.4f}",
                 f"[{c.ci_lower:.4f}, {c.ci_upper:.4f}]",
                 "✓" if c.significant else "✗"]
                for c in self.coefficients
            ]
        lines.append(_md_table(headers, rows))

        # VIF
        mc_flags = [v for v in self.vif if v.multicollinear]
        if mc_flags:
            lines.append("")
            lines.append("**Multicollinearity flags**:")
            lines.append(_bullet([f"**{v.variable}**: VIF = {v.vif:.2f}" for v in mc_flags]))

        if self.diagnostics:
            lines.append("")
            lines.append("**Diagnostics**:")
            lines.append(_bullet(self.diagnostics))

        return "\n".join(lines)


class SRMCheck(BaseModel):
    p_value: float = 0.0
    ok: bool = True
    observed_ratio: float = 0.0

    model_config = {"extra": "allow"}


class ABGroupStats(BaseModel):
    label: str = ""
    n: int = 0
    mean: float = 0.0
    std: float = 0.0

    model_config = {"extra": "allow"}


class StatsABTestResult(BaseModel):
    """stats_ab_test output."""
    dataset_id: str = ""
    control: ABGroupStats = Field(default_factory=ABGroupStats)
    treatment: ABGroupStats = Field(default_factory=ABGroupStats)
    difference: float = 0.0
    relative_uplift_pct: float = 0.0
    p_value: float = 0.0
    significant: bool = False
    cohens_d: float = 0.0
    effect_label: str = ""
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    srm_check: Optional[SRMCheck] = None
    practical_significance: bool = False
    mde: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        verdict = "Significant" if self.significant else "Not significant"
        direction = "outperforms" if self.difference > 0 else "underperforms"
        lines = [
            f"**Verdict**: {verdict} — {self.treatment.label} {direction} "
            f"{self.control.label} by **{abs(self.relative_uplift_pct):.1f}%**",
            "",
        ]

        # Group comparison table
        lines.append(_md_table(
            ["Metric", "Control", "Treatment"],
            [
                ["N", str(self.control.n), str(self.treatment.n)],
                ["Mean", f"{self.control.mean:.4f}", f"{self.treatment.mean:.4f}"],
                ["Std", f"{self.control.std:.4f}", f"{self.treatment.std:.4f}"],
            ],
        ))
        lines.append("")

        # Stats table
        srm_status = "OK" if (self.srm_check and self.srm_check.ok) else "WARNING"
        lines.append(_md_table(
            ["Metric", "Value"],
            [
                ["Absolute difference", f"{self.difference:.4f}"],
                ["p-value", f"{self.p_value:.4f}"],
                ["Cohen's d", f"{self.cohens_d:.4f} ({self.effect_label})"],
                ["95% CI", f"[{self.ci_lower:.4f}, {self.ci_upper:.4f}]"],
                ["SRM check", srm_status],
            ],
        ))

        if self.warnings:
            lines.append("")
            lines.append("**Warnings**:")
            lines.append(_bullet(self.warnings))

        return "\n".join(lines)


class StatsPowerResult(BaseModel):
    """stats_power output."""
    mode: str = ""
    n_per_group: int = 0
    total_n: int = 0
    effect_size: float = 0.0
    alpha: float = 0.05
    power: Optional[float] = None
    achieved_power: Optional[float] = None
    adequate: Optional[bool] = None
    interpretation: str = ""
    test_type: Optional[str] = None
    baseline_rate: Optional[float] = None
    expected_new_rate: Optional[float] = None

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        pwr = self.achieved_power if self.achieved_power is not None else self.power
        lines = [
            f"**Power analysis** ({self.mode})",
            "",
            _md_table(
                ["Metric", "Value"],
                [
                    ["N per group", str(self.n_per_group)],
                    ["Total N", str(self.total_n)],
                    ["Effect size", f"{self.effect_size:.4f}"],
                    ["Alpha", f"{self.alpha}"],
                    ["Power", f"{pwr:.4f}" if pwr is not None else "—"],
                ],
            ),
            "",
            f"**Interpretation**: {self.interpretation}",
        ]
        return "\n".join(lines)


class AssumptionColumnResult(BaseModel):
    n: int = 0
    error: Optional[str] = None
    normality: Optional[NormalityResult] = None
    suggested_transformation: Optional[str] = None
    equal_variance: Optional[EqualVarianceResult] = None
    recommended_test: Optional[dict[str, Any]] = None

    model_config = {"extra": "allow"}


class StatsAssumptionsResult(BaseModel):
    """stats_check_assumptions output."""
    dataset_id: str = ""
    columns_checked: list[str] = Field(default_factory=list)
    results: dict[str, AssumptionColumnResult] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    group_column: Optional[str] = None

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines: list[str] = []
        headers = ["Column", "N", "Normal?", "Test", "p-value", "Suggested Transform"]
        rows: list[list[str]] = []
        for col, ar in self.results.items():
            if ar.error:
                rows.append([col, str(ar.n), "Error", "—", "—", ar.error])
                continue
            norm = ar.normality
            rows.append([
                col, str(ar.n),
                "Yes" if (norm and norm.is_normal) else "No",
                norm.test if norm else "—",
                f"{norm.p_value:.4f}" if norm else "—",
                ar.suggested_transformation or "—",
            ])
        lines.append(_md_table(headers, rows))

        if self.recommendations:
            lines.append("")
            lines.append("**Recommendations**:")
            lines.append(_bullet(self.recommendations))

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Cleaning Specialist Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class CleaningChange(BaseModel):
    action: str = ""
    detail: str = ""
    columns: Optional[str] = None

    model_config = {"extra": "allow"}


class CleanStructuralResult(BaseModel):
    """clean_structural output."""
    original_id: str = ""
    clean_id: str = ""
    rows_before: int = 0
    rows_after: int = 0
    changes: list[CleaningChange] = Field(default_factory=list)
    change_count: int = 0
    pipeline_stage: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [
            f"**Before**: {self.rows_before} rows | **After**: {self.rows_after} rows",
            "",
            f"**Changes applied** ({self.change_count}):",
            _bullet([f"**{c.action}**: {c.detail}" for c in self.changes]),
        ]
        return "\n".join(lines)


class CleanDeduplicateResult(BaseModel):
    """clean_deduplicate output."""
    original_id: str = ""
    clean_id: str = ""
    rows_before: int = 0
    rows_after: int = 0
    duplicates_found: int = 0
    duplicates_removed: int = 0
    strategy: str = ""
    subset: Optional[list[str]] = None
    pipeline_stage: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [
            f"**Duplicates found**: {self.duplicates_found} | **Removed**: {self.duplicates_removed}",
            f"**Strategy**: {self.strategy}",
            f"**Rows**: {self.rows_before} → {self.rows_after}",
        ]
        if self.subset:
            lines.append(f"**Subset columns**: {', '.join(self.subset)}")
        return "\n".join(lines)


class MissingAction(BaseModel):
    column: str = ""
    null_count: int = 0
    null_pct: float = 0.0
    method: str = ""
    result: str = ""

    model_config = {"extra": "allow"}


class CleanMissingResult(BaseModel):
    """clean_missing output."""
    original_id: str = ""
    clean_id: str = ""
    rows_before: int = 0
    rows_after: int = 0
    columns_before: int = 0
    columns_after: int = 0
    actions: list[MissingAction] = Field(default_factory=list)
    action_count: int = 0
    pipeline_stage: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [
            f"**Before**: {self.rows_before} rows × {self.columns_before} cols | "
            f"**After**: {self.rows_after} rows × {self.columns_after} cols",
            "",
        ]
        if self.actions:
            headers = ["Column", "Nulls", "Null %", "Method", "Result"]
            rows = [
                [a.column, str(a.null_count), f"{a.null_pct:.1f}%", a.method, a.result]
                for a in self.actions
            ]
            lines.append(_md_table(headers, rows))
        return "\n".join(lines)


class CleanStandardiseResult(BaseModel):
    """clean_standardise output."""
    original_id: str = ""
    clean_id: str = ""
    changes: list[CleaningChange] = Field(default_factory=list)
    change_count: int = 0
    operations_applied: list[str] = Field(default_factory=list)
    pipeline_stage: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [
            f"**Changes applied** ({self.change_count}):",
            _bullet([f"**{c.action}**: {c.detail}" for c in self.changes]),
        ]
        if self.operations_applied:
            lines.append(f"**Operations**: {', '.join(self.operations_applied)}")
        return "\n".join(lines)


class Derivation(BaseModel):
    type: str = ""
    column: str = ""
    result: str = ""

    model_config = {"extra": "allow"}


class CleanDeriveResult(BaseModel):
    """clean_derive output."""
    original_id: str = ""
    clean_id: str = ""
    columns_before: int = 0
    columns_after: int = 0
    new_columns: int = 0
    derivations: list[Derivation] = Field(default_factory=list)
    pipeline_stage: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [
            f"**New columns**: {self.new_columns} ({self.columns_before} → {self.columns_after} total)",
            "",
        ]
        if self.derivations:
            headers = ["Type", "Column", "Result"]
            rows = [[d.type, d.column, d.result] for d in self.derivations]
            lines.append(_md_table(headers, rows))
        return "\n".join(lines)


class ValidationCheck(BaseModel):
    check: str = ""
    column: Optional[str] = None
    passed: bool = True
    detail: str = ""

    model_config = {"extra": "allow"}


class CleanValidateResult(BaseModel):
    """clean_validate output."""
    dataset_id: str = ""
    checks: list[ValidationCheck] = Field(default_factory=list)
    passed: int = 0
    failed: int = 0
    total: int = 0
    verdict: str = ""
    pipeline_stage: str = ""

    model_config = {"extra": "allow"}

    def to_markdown(self) -> str:
        lines = [
            f"**Verdict**: {self.verdict} — {self.passed}/{self.total} checks passed",
            "",
        ]
        if self.checks:
            headers = ["Check", "Column", "Status", "Detail"]
            rows = [
                [c.check, c.column or "—", "✓" if c.passed else "✗", c.detail]
                for c in self.checks
            ]
            lines.append(_md_table(headers, rows))
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Schema registry — maps tool names to their Pydantic model class
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_SCHEMA_MAP: dict[str, type[BaseModel]] = {
    # EDA
    "eda_profile": ProfileResult,
    "eda_describe": DescribeResult,
    "eda_correlations": CorrelationsResult,
    "eda_value_counts": ValueCountsResult,
    "eda_smart_structure": SmartStructureResult,
    # SQL
    "sql_schema": SQLSchemaResult,
    "sql_execute": SQLExecuteResult,
    "sql_validate": SQLValidateResult,
    # Viz
    "viz_bar_chart": ChartResult,
    "viz_line_chart": ChartResult,
    "viz_scatter_plot": ChartResult,
    "viz_histogram": ChartResult,
    "viz_box_plot": ChartResult,
    "viz_heatmap": ChartResult,
    "viz_pie_chart": ChartResult,
    "viz_recommend": VizRecommendResult,
    # Stats
    "stats_test": StatsTestResult,
    "stats_regression": StatsRegressionResult,
    "stats_ab_test": StatsABTestResult,
    "stats_power": StatsPowerResult,
    "stats_check_assumptions": StatsAssumptionsResult,
    # Cleaning
    "clean_structural": CleanStructuralResult,
    "clean_deduplicate": CleanDeduplicateResult,
    "clean_missing": CleanMissingResult,
    "clean_standardise": CleanStandardiseResult,
    "clean_derive": CleanDeriveResult,
    "clean_validate": CleanValidateResult,
}


def validate_and_render(tool_name: str, data: dict[str, Any]) -> str | None:
    """Validate data against the schema for *tool_name* and return markdown.

    Returns ``None`` if no schema is registered for the tool, so the caller
    can fall back to the old rendering path.
    """
    schema_cls = TOOL_SCHEMA_MAP.get(tool_name)
    if schema_cls is None:
        return None
    try:
        model = schema_cls.model_validate(data)
        return model.to_markdown()
    except Exception:
        # Validation failure — fall back gracefully
        return None
