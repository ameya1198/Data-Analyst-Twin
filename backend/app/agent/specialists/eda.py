"""
EDA Specialist — Exploratory Data Analysis in ToolMode.

Grounded in John Tukey's EDA philosophy (1977): "EDA is not a formal process
with a strict set of rules — more than anything, it is a state of mind."

Knowledge framework covers 10 domains:
1.  Tukey's foundational philosophy and mindset rules
2.  5-phase sequential process (Overview → Univariate → Bivariate → Multivariate → Temporal)
3.  Data quality assessment (MCAR/MAR/MNAR missingness classification)
4.  Outlier detection framework (Z-score, IQR, multivariate, decision rules)
5.  Distribution analysis (shape diagnostics, normality testing, transformations)
6.  Correlation & relationship analysis (strength guide, multicollinearity checks)
7.  Anti-patterns (p-hacking, data leakage, confirmation bias, over-cleaning)
8.  Chart selection by analysis type
9.  EDA output deliverables
10. Tukey's two master questions (variation + covariation)
"""

from __future__ import annotations

import re
import warnings
from typing import Any

import numpy as np
import pandas as pd
import structlog

from app.agent.specialists.base import BaseSpecialist, SpecialistMode, SpecialistResult, ResultType
from app.agent.specialists.context import AnalysisContext
from app.agent.knowledge.eda_knowledge import (
    EDA_KNOWLEDGE,
    EDAPhase,
    get_correlation_label,
    get_decision_rules_for_tool,
    get_outlier_assessment,
    get_skewness_assessment,
    get_workflow_summary,
    classify_missingness,
)

logger = structlog.get_logger(__name__)


class EDASpecialist(BaseSpecialist):
    name = "eda"
    description = (
        "Exploratory Data Analysis specialist grounded in John Tukey's EDA philosophy. "
        "Follows a 5-phase process: Dataset Overview → Univariate → Bivariate → "
        "Multivariate → Temporal. Profiles datasets, computes statistics, correlations, "
        "value counts, assesses data quality (MCAR/MAR/MNAR missingness), detects outliers "
        "(IQR/Z-score), evaluates distributions (skewness, normality), and auto-structures "
        "messy/semi-structured/text-heavy data. Answers Tukey's two master questions: "
        "what variation within variables? what covariation between variables?"
    )
    mode = SpecialistMode.TOOL
    timeout_seconds = 30
    system_prompt = (
        "You are the EDA specialist of a data analyst digital twin, grounded in "
        "John Tukey's philosophy: EDA is about reducing uncertainty — do I understand "
        "this dataset well enough to trust what comes next? "
        "Follow the 5-phase process: Dataset Overview → Univariate → Bivariate → "
        "Multivariate → Temporal. Always classify missingness (MCAR/MAR/MNAR) before "
        "treatment. Investigate outliers before removing — never auto-delete. "
        "Report correlation strength using standard labels (negligible/weak/moderate/"
        "strong/very strong). Avoid anti-patterns: p-hacking, confirmation bias, "
        "data leakage, over-cleaning, stopping at univariate."
    )

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "eda_profile",
                "description": (
                    "[Phase 1: Dataset Overview] Generate a full profile of a dataset: "
                    "row/column counts, data types, null percentages, duplicate rate, "
                    "basic statistics for numeric columns, unique counts for categoricals, "
                    "and an overall data quality score (0-100). ALWAYS run this first on a "
                    "new dataset — Tukey's rule: never skip the overview. "
                    "If quality < 70 → run eda_smart_structure. If quality >= 70 → proceed "
                    "to Phase 2 (eda_describe for univariate) or Phase 3 (eda_correlations)."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "ID of the dataset to profile",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "eda_describe",
                "description": (
                    "[Phase 2: Univariate Analysis] Get detailed statistical summary for "
                    "specific columns. For numeric: mean, median, std, quartiles, skewness "
                    "(flags >1 as significantly skewed), kurtosis (flags >3 as heavy-tailed). "
                    "For categorical: top values, frequency distribution, imbalance flags. "
                    "For text: avg length, word count stats, sample values. "
                    "Use after eda_profile. Answers Tukey's first master question: "
                    "what type of variation occurs within my variables?"
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Column names to describe. If empty, describes all columns.",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "eda_correlations",
                "description": (
                    "[Phase 3: Bivariate Analysis] Compute correlation matrix for numeric "
                    "columns. Labels strength: negligible (<0.2), weak (0.2-0.4), moderate "
                    "(0.4-0.6), strong (0.6-0.8), very strong (>0.8). "
                    "Flags multicollinearity (|r| > 0.8). Answers Tukey's second master "
                    "question: what type of covariation occurs between my variables? "
                    "Note: correlation ≠ causation — always beware confounding variables."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "method": {
                            "type": "string",
                            "enum": ["pearson", "spearman", "kendall"],
                            "description": "Correlation method. Use 'pearson' for linear relationships, 'spearman' for monotonic, 'kendall' for ordinal data. Default: pearson.",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "eda_value_counts",
                "description": (
                    "[Phase 2: Univariate / Phase 3: Bivariate] Get frequency distribution "
                    "for a categorical column. Shows top N values with counts and percentages. "
                    "Flags imbalanced classes (>80% single value — modeling risk), binary "
                    "columns (segmentation candidates), and rare categories (<1%). "
                    "Use to understand category distributions and find dominant/rare values."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "column": {"type": "string", "description": "Column name"},
                        "top_n": {
                            "type": "integer",
                            "description": "Number of top values to return. Default: 20.",
                        },
                    },
                    "required": ["dataset_id", "column"],
                },
            },
            {
                "name": "eda_data_quality",
                "description": (
                    "[Phase 1: Dataset Overview] Deep data quality assessment. "
                    "Detects: mixed types, inconsistent formats, duplicate rows, "
                    "messy headers, nested/JSON columns, text-heavy columns, constant columns. "
                    "Classifies null patterns as likely MCAR (random — safe to impute), "
                    "MAR/MNAR (systematic — do NOT blindly drop). Returns issues with "
                    "severity (high/medium/low) and Tukey-grounded recommendations."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "eda_smart_structure",
                "description": (
                    "[Data Preparation] Auto-detect and fix data quality issues to produce "
                    "a clean structured DataFrame. Normalizes headers, coerces mixed types, "
                    "flattens nested JSON, extracts text features (word_count, char_count), "
                    "and converts date strings to datetime. Anti-pattern guard: logs every "
                    "change (never silently drops data). Run when quality score < 70. "
                    "Returns cleaned dataset ID, change log, and quality delta."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                    },
                    "required": ["dataset_id"],
                },
            },
        ]

    async def _execute_tool_mode(
        self, tool_name: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)

        if df is None:
            available = ", ".join(context.dataset_ids) or "none"
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary=f"Dataset '{dataset_id}' not found. Available: {available}",
                error=f"Dataset not found: {dataset_id}",
            )

        dispatch = {
            "eda_profile": self._profile,
            "eda_describe": self._describe,
            "eda_correlations": self._correlations,
            "eda_value_counts": self._value_counts,
            "eda_data_quality": self._data_quality,
            "eda_smart_structure": self._smart_structure,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary=f"Unknown EDA tool: {tool_name}",
                error=f"Unknown tool: {tool_name}",
            )

        return await handler(df, dataset_id, params, context)

    # ─── Tool implementations ────────────────────────────────────────

    async def _profile(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        total_cells = df.shape[0] * df.shape[1]
        null_cells = int(df.isna().sum().sum())
        duplicate_rows = int(df.duplicated().sum())
        quality_score = self._compute_quality_score(df)

        column_profiles = []
        for col in df.columns:
            series = df[col]
            col_type = self._classify_column(series)
            profile: dict[str, Any] = {
                "name": str(col),
                "dtype": str(series.dtype),
                "inferred_type": col_type,
                "non_null": int(series.notna().sum()),
                "null_count": int(series.isna().sum()),
                "null_pct": round(series.isna().mean() * 100, 1),
                "unique": int(series.nunique()),
            }

            if col_type == "numeric":
                clean = pd.to_numeric(series, errors="coerce").dropna()
                if len(clean) > 0:
                    profile["mean"] = round(float(clean.mean()), 2)
                    profile["median"] = round(float(clean.median()), 2)
                    profile["std"] = round(float(clean.std()), 2)
                    profile["min"] = float(clean.min())
                    profile["max"] = float(clean.max())
            elif col_type == "text":
                lengths = series.dropna().astype(str).str.len()
                profile["avg_length"] = round(float(lengths.mean()), 1) if len(lengths) > 0 else 0
                profile["max_length"] = int(lengths.max()) if len(lengths) > 0 else 0
                word_counts = series.dropna().astype(str).str.split().str.len()
                profile["avg_words"] = round(float(word_counts.mean()), 1) if len(word_counts) > 0 else 0
            elif col_type == "categorical":
                top = series.value_counts().head(5)
                profile["top_values"] = {str(k): int(v) for k, v in top.items()}

            column_profiles.append(profile)

        sampling_note = ""
        if df.shape[0] > 100_000:
            sampling_note = f"Large dataset ({df.shape[0]:,} rows). Consider sampling for initial exploration."

        # Determine recommended next phase
        if quality_score >= 70:
            next_phase = "Phase 2 (Univariate) → run eda_describe, then Phase 3 (Bivariate) → eda_correlations"
        else:
            next_phase = "Data Preparation → run eda_smart_structure first (quality < 70)"

        dup_pct = round(duplicate_rows / df.shape[0] * 100, 1) if df.shape[0] > 0 else 0

        result_data = {
            "dataset_id": dataset_id,
            "rows": df.shape[0],
            "columns": df.shape[1],
            "total_cells": total_cells,
            "null_cells": null_cells,
            "null_pct": round((null_cells / total_cells) * 100, 1) if total_cells > 0 else 0,
            "duplicate_rows": duplicate_rows,
            "duplicate_pct": dup_pct,
            "quality_score": quality_score,
            "column_profiles": column_profiles,
            "workflow_phase": "Phase 1: Dataset Overview",
            "recommended_next": next_phase,
            "sampling_note": sampling_note,
        }

        summary = (
            f"[Phase 1: Dataset Overview] {df.shape[0]} rows x {df.shape[1]} columns. "
            f"Quality: {quality_score}/100. "
            f"Nulls: {null_cells} ({result_data['null_pct']}%). "
            f"Duplicates: {duplicate_rows} ({dup_pct}%). "
            f"Next: {next_phase}."
        )

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.TABLE,
            data=result_data,
            summary=summary,
        )

    async def _describe(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        columns = params.get("columns") or list(df.columns)
        missing = [c for c in columns if c not in df.columns]
        if missing:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Columns not found: {missing}",
                error=f"Missing columns: {missing}",
            )

        descriptions = {}
        for col in columns:
            series = df[col]
            col_type = self._classify_column(series)
            desc: dict[str, Any] = {
                "type": col_type,
                "count": int(series.notna().sum()),
                "null_count": int(series.isna().sum()),
                "unique": int(series.nunique()),
            }

            if col_type == "numeric":
                clean = pd.to_numeric(series, errors="coerce").dropna()
                if len(clean) > 0:
                    skew_val = round(float(clean.skew()), 4)
                    kurt_val = round(float(clean.kurtosis()), 4)
                    skew_assessment = get_skewness_assessment(skew_val)
                    outlier_info = get_outlier_assessment(clean.tolist()) if len(clean) >= 10 else {}

                    desc.update({
                        "mean": round(float(clean.mean()), 4),
                        "median": round(float(clean.median()), 4),
                        "std": round(float(clean.std()), 4),
                        "min": float(clean.min()),
                        "max": float(clean.max()),
                        "q25": round(float(clean.quantile(0.25)), 4),
                        "q75": round(float(clean.quantile(0.75)), 4),
                        "skewness": skew_val,
                        "skewness_label": skew_assessment["label"],
                        "skewness_action": skew_assessment["action"],
                        "kurtosis": kurt_val,
                        "heavy_tailed": kurt_val > 3,
                    })
                    if outlier_info:
                        desc["outliers"] = {
                            "mild": outlier_info["mild_outliers"],
                            "extreme": outlier_info["extreme_outliers"],
                            "pct": outlier_info["outlier_pct"],
                            "lower_fence": outlier_info["lower_fence"],
                            "upper_fence": outlier_info["upper_fence"],
                            "assessment": outlier_info["assessment"],
                        }
            elif col_type == "text":
                text_series = series.dropna().astype(str)
                lengths = text_series.str.len()
                words = text_series.str.split().str.len()
                desc.update({
                    "avg_char_length": round(float(lengths.mean()), 1) if len(lengths) > 0 else 0,
                    "max_char_length": int(lengths.max()) if len(lengths) > 0 else 0,
                    "avg_word_count": round(float(words.mean()), 1) if len(words) > 0 else 0,
                    "max_word_count": int(words.max()) if len(words) > 0 else 0,
                    "samples": text_series.head(3).tolist(),
                })
            elif col_type == "categorical":
                vc = series.value_counts()
                desc.update({
                    "top_values": {str(k): int(v) for k, v in vc.head(10).items()},
                    "value_distribution_pct": {
                        str(k): round(float(v), 1)
                        for k, v in (vc / len(series) * 100).head(10).items()
                    },
                })
            elif col_type == "datetime":
                dates = pd.to_datetime(series, errors="coerce").dropna()
                if len(dates) > 0:
                    desc.update({
                        "min": str(dates.min()),
                        "max": str(dates.max()),
                        "range_days": (dates.max() - dates.min()).days,
                    })

            descriptions[col] = desc

        # Build summary with distribution highlights
        flags = []
        for col, desc in descriptions.items():
            if desc.get("skewness_label") and "significantly" in desc["skewness_label"]:
                flags.append(f"{col} is {desc['skewness_label']}")
            if desc.get("heavy_tailed"):
                flags.append(f"{col} has heavy tails (kurtosis={desc['kurtosis']})")
            if desc.get("outliers", {}).get("mild", 0) > 0:
                flags.append(f"{col} has {desc['outliers']['mild']} outlier(s)")

        flag_str = " Flags: " + "; ".join(flags[:5]) + "." if flags else ""

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.TABLE,
            data={
                "dataset_id": dataset_id,
                "descriptions": descriptions,
                "workflow_phase": "Phase 2: Univariate Analysis",
            },
            summary=(
                f"[Phase 2: Univariate] Described {len(columns)} columns: "
                f"{', '.join(columns[:5])}"
                + (f" (+{len(columns)-5} more)" if len(columns) > 5 else "")
                + f".{flag_str}"
            ),
        )

    async def _correlations(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        method = params.get("method", "pearson")
        numeric_df = df.select_dtypes(include=[np.number])

        if numeric_df.shape[1] < 2:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary="Need at least 2 numeric columns for correlations.",
                error="Insufficient numeric columns",
            )

        corr_matrix = numeric_df.corr(method=method)

        # Find notable correlations (|r| > 0.2, excluding self-correlations)
        # and label using the correlation strength guide
        all_pairs = []
        cols = corr_matrix.columns.tolist()
        for i, c1 in enumerate(cols):
            for c2 in cols[i + 1:]:
                r = float(corr_matrix.loc[c1, c2])
                label = get_correlation_label(r)
                if abs(r) > 0.2:
                    all_pairs.append({
                        "col1": c1, "col2": c2,
                        "correlation": round(r, 4),
                        "strength": label,
                    })

        all_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        strong = [p for p in all_pairs if abs(p["correlation"]) > 0.4]

        corr_dict = {
            str(c1): {str(c2): round(float(v), 4) for c2, v in row.items()}
            for c1, row in corr_matrix.iterrows()
        }

        # Apply bivariate decision rules from knowledge base
        multicollinear = [p for p in all_pairs if abs(p["correlation"]) > 0.8]
        diagnostics = []
        if multicollinear:
            pairs = ", ".join(f"{p['col1']}↔{p['col2']} (r={p['correlation']:.2f})" for p in multicollinear[:3])
            diagnostics.append(f"Multicollinearity warning (|r| > 0.8): {pairs}. Consider dropping one or creating composite.")
        very_strong = [p for p in all_pairs if p["strength"] == "very strong"]
        if very_strong:
            diagnostics.append(f"{len(very_strong)} very strong pair(s) (|r| > 0.8).")
        strong_only = [p for p in all_pairs if p["strength"] == "strong"]
        if strong_only:
            diagnostics.append(f"{len(strong_only)} strong pair(s) (|r| 0.6–0.8) worth investigating.")
        diagnostics.append("Reminder: correlation ≠ causation — check for confounding variables.")

        result_data = {
            "dataset_id": dataset_id,
            "method": method,
            "matrix": corr_dict,
            "all_notable_pairs": all_pairs[:20],
            "strong_correlations": strong,
            "multicollinear_pairs": multicollinear,
            "numeric_columns": cols,
            "workflow_phase": "Phase 3: Bivariate Analysis",
            "diagnostics": diagnostics,
        }

        if all_pairs:
            top = all_pairs[0]
            diag_str = " ".join(diagnostics[:3])
            summary = (
                f"[Phase 3: Bivariate] Correlation ({method}) for {len(cols)} numeric columns. "
                f"{len(all_pairs)} notable pair(s). "
                f"Strongest: {top['col1']} ↔ {top['col2']} (r={top['correlation']}, {top['strength']}). "
                f"{diag_str}"
            )
        else:
            summary = f"[Phase 3: Bivariate] Correlation ({method}) for {len(cols)} numeric columns. No notable correlations (all |r| < 0.2)."

        # Store for downstream specialists (viz can use this)
        context.set_variable(f"corr_matrix_{dataset_id}", corr_matrix)

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.STATISTIC,
            data=result_data,
            summary=summary,
        )

    async def _value_counts(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        column = params.get("column", "")
        top_n = params.get("top_n", 20)

        if column not in df.columns:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Column '{column}' not found.",
                error=f"Column not found: {column}",
            )

        vc = df[column].value_counts().head(top_n)
        total = len(df[column].dropna())

        values = [
            {
                "value": str(k) if pd.notna(k) else None,
                "count": int(v),
                "percentage": round(float(v / total * 100), 1) if total > 0 else 0,
            }
            for k, v in vc.items()
        ]

        null_count = int(df[column].isna().sum())

        unique_count = int(df[column].nunique())
        diagnostics = []
        if len(vc) > 0 and total > 0:
            top_pct = vc.iloc[0] / total * 100
            if top_pct > 80:
                diagnostics.append(f"Highly imbalanced: '{vc.index[0]}' dominates at {round(top_pct, 1)}%. Modeling risk — consider oversampling minority classes.")
            elif unique_count == 2:
                diagnostics.append(f"Binary column — good candidate for group comparison / segmentation.")
            # Flag rare categories
            if total > 0:
                rare = [str(k) for k, v in vc.items() if v / total < 0.01]
                if rare:
                    diagnostics.append(f"{len(rare)} rare categor(ies) (<1%): {', '.join(rare[:3])}. Consider grouping.")

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.TABLE,
            data={
                "dataset_id": dataset_id,
                "column": column,
                "values": values,
                "total_non_null": total,
                "null_count": null_count,
                "unique_count": unique_count,
                "workflow_phase": "Phase 2: Univariate Analysis",
                "diagnostics": diagnostics,
            },
            summary=(
                f"[Phase 2: Univariate] Value counts for '{column}': {unique_count} unique values. "
                f"Top value: '{vc.index[0]}' ({int(vc.iloc[0])} occurrences, "
                f"{round(vc.iloc[0] / total * 100, 1)}%). "
                + (" ".join(diagnostics))
                if len(vc) > 0 else f"Column '{column}' has no non-null values."
            ),
        )

    async def _data_quality(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        issues: list[dict[str, Any]] = []

        # 1. Check for messy column headers
        for col in df.columns:
            col_str = str(col)
            if col_str != col_str.strip():
                issues.append({"type": "messy_header", "column": col_str,
                               "severity": "low", "detail": "Has leading/trailing whitespace"})
            if col_str.startswith("Unnamed"):
                issues.append({"type": "unnamed_header", "column": col_str,
                               "severity": "medium", "detail": "Column has no header name"})
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col_str):
                issues.append({"type": "non_standard_header", "column": col_str,
                               "severity": "low", "detail": "Header contains special characters or spaces"})

        # 2. Duplicate columns
        dup_cols = df.columns[df.columns.duplicated()].tolist()
        for col in dup_cols:
            issues.append({"type": "duplicate_column", "column": str(col),
                           "severity": "high", "detail": "Duplicate column name"})

        # 3. Duplicate rows
        dup_count = int(df.duplicated().sum())
        if dup_count > 0:
            issues.append({"type": "duplicate_rows", "column": None,
                           "severity": "medium", "detail": f"{dup_count} duplicate rows found"})

        # 4. Mixed types in columns
        for col in df.columns:
            series = df[col].dropna()
            if len(series) == 0:
                continue
            types = set(type(v).__name__ for v in series.head(100))
            if len(types) > 1:
                issues.append({"type": "mixed_types", "column": str(col),
                               "severity": "high", "detail": f"Mixed types detected: {types}"})

        # 5. Constant columns (zero variance)
        for col in df.columns:
            if df[col].nunique() <= 1:
                issues.append({"type": "constant_column", "column": str(col),
                               "severity": "low", "detail": "Column has only one unique value"})

        # 6. High null percentage columns
        for col in df.columns:
            null_pct = df[col].isna().mean() * 100
            if null_pct > 50:
                issues.append({"type": "high_nulls", "column": str(col),
                               "severity": "medium", "detail": f"{null_pct:.0f}% null values"})

        # 7. Detect text-heavy columns
        for col in df.columns:
            series = df[col].dropna()
            if self._is_string_like(series) and len(series) > 0:
                avg_len = series.astype(str).str.len().mean()
                if avg_len > 50:
                    issues.append({"type": "text_heavy", "column": str(col),
                                   "severity": "info",
                                   "detail": f"Text-heavy column (avg {avg_len:.0f} chars). Consider extracting features."})

        # 8. Detect nested/JSON-like columns
        for col in df.columns:
            sample = df[col].dropna().head(5)
            if self._is_string_like(sample):
                json_like = sum(1 for v in sample if isinstance(v, (dict, list))
                                or (isinstance(v, str) and v.strip().startswith(("{", "["))))
                if json_like >= 3:
                    issues.append({"type": "nested_data", "column": str(col),
                                   "severity": "medium",
                                   "detail": "Column contains nested/JSON data. Consider flattening."})

        # 9. Potential date columns stored as strings
        for col in df.columns:
            if self._is_string_like(df[col]):
                sample = df[col].dropna().head(20)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    parsed = pd.to_datetime(sample, errors="coerce")
                if parsed.notna().sum() >= len(sample) * 0.8 and len(sample) > 0:
                    issues.append({"type": "date_as_string", "column": str(col),
                                   "severity": "low",
                                   "detail": "Looks like a date column stored as string"})

        quality_score = self._compute_quality_score(df)

        severity_counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
        for issue in issues:
            severity_counts[issue["severity"]] = severity_counts.get(issue["severity"], 0) + 1

        recommendation = self._quality_recommendation(quality_score, issues)

        # Classify missingness per-column using MCAR/MAR/MNAR framework
        high_null_cols = [i["column"] for i in issues if i["type"] == "high_nulls"]
        is_concentrated = len(high_null_cols) > 0

        missingness_classifications = {}
        for col in df.columns:
            null_pct = df[col].isna().mean() * 100
            if null_pct > 0:
                col_concentrated = col in [str(c) for c in high_null_cols]
                missingness_classifications[col] = classify_missingness(null_pct, col_concentrated)

        null_pattern = "no missing values"
        if missingness_classifications:
            types = [v["type"] for v in missingness_classifications.values()]
            if any(t == "MAR_or_MNAR" for t in types):
                null_pattern = "systematic (likely MAR/MNAR) — do NOT blindly drop"
            elif any(t == "consider_drop" for t in types):
                null_pattern = "high missingness — consider dropping affected features"
            else:
                null_pattern = "likely MCAR (random) — safe to impute"

        result_data = {
            "dataset_id": dataset_id,
            "quality_score": quality_score,
            "total_issues": len(issues),
            "severity_counts": severity_counts,
            "issues": issues,
            "recommendation": recommendation,
            "null_pattern": null_pattern,
            "missingness_classifications": missingness_classifications,
            "workflow_phase": "Phase 1: Dataset Overview",
        }

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.TABLE,
            data=result_data,
            summary=(
                f"[Phase 1: Dataset Overview] Quality: {quality_score}/100. "
                f"{len(issues)} issues "
                f"({severity_counts['high']} high, {severity_counts['medium']} medium, "
                f"{severity_counts['low']} low). "
                f"Missingness: {null_pattern}. "
                f"{recommendation}"
            ),
        )

    async def _smart_structure(
        self, df: pd.DataFrame, dataset_id: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """Auto-detect issues and produce a clean structured DataFrame."""
        changes: list[str] = []
        clean_df = df.copy()

        # 1. Normalize column headers
        new_columns = {}
        for col in clean_df.columns:
            original = str(col)
            cleaned = original.strip().lower()
            cleaned = re.sub(r"[^a-z0-9_]", "_", cleaned)
            cleaned = re.sub(r"_+", "_", cleaned).strip("_")
            if not cleaned or cleaned[0].isdigit():
                cleaned = f"col_{cleaned}"
            if cleaned != original:
                new_columns[col] = cleaned
        if new_columns:
            clean_df = clean_df.rename(columns=new_columns)
            changes.append(f"Normalized {len(new_columns)} column headers: {new_columns}")

        # Handle duplicate column names after normalization
        seen: dict[str, int] = {}
        final_cols = []
        for c in clean_df.columns:
            c_str = str(c)
            if c_str in seen:
                seen[c_str] += 1
                final_cols.append(f"{c_str}_{seen[c_str]}")
            else:
                seen[c_str] = 0
                final_cols.append(c_str)
        if final_cols != list(clean_df.columns):
            clean_df.columns = final_cols
            changes.append("Resolved duplicate column names")

        # 2. Fix mixed types — attempt numeric coercion on string columns
        for col in clean_df.columns:
            if self._is_string_like(clean_df[col]):
                numeric_attempt = pd.to_numeric(clean_df[col], errors="coerce")
                non_null_original = clean_df[col].notna().sum()
                non_null_numeric = numeric_attempt.notna().sum()
                if non_null_original > 0 and non_null_numeric / non_null_original >= 0.8:
                    clean_df[col] = numeric_attempt
                    changes.append(f"Converted '{col}' from string to numeric ({non_null_numeric}/{non_null_original} values)")

        # 3. Detect and convert date columns
        for col in clean_df.columns:
            if self._is_string_like(clean_df[col]):
                sample = clean_df[col].dropna().head(30)
                if len(sample) == 0:
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    parsed = pd.to_datetime(sample, errors="coerce")
                if parsed.notna().sum() >= len(sample) * 0.8:
                    clean_df[col] = pd.to_datetime(clean_df[col], errors="coerce")
                    changes.append(f"Converted '{col}' to datetime")

        # 4. Flatten nested JSON columns
        json_cols_flattened = []
        for col in list(clean_df.columns):
            sample = clean_df[col].dropna().head(5)
            if not self._is_string_like(sample):
                continue
            json_like = sum(
                1 for v in sample
                if isinstance(v, (dict, list))
                or (isinstance(v, str) and v.strip().startswith(("{", "[")))
            )
            if json_like >= 3:
                try:
                    expanded = self._flatten_json_column(clean_df, col)
                    if expanded is not None:
                        clean_df = expanded
                        json_cols_flattened.append(col)
                except Exception as e:
                    logger.warning("json_flatten_failed", column=col, error=str(e))

        if json_cols_flattened:
            changes.append(f"Flattened nested JSON in columns: {json_cols_flattened}")

        # 5. Extract text features from text-heavy columns
        text_features_added = []
        for col in list(clean_df.columns):
            if not self._is_string_like(clean_df[col]):
                continue
            avg_len = clean_df[col].dropna().astype(str).str.len().mean()
            if avg_len > 50:
                text_col = clean_df[col].fillna("").astype(str)
                clean_df[f"{col}_word_count"] = text_col.str.split().str.len()
                clean_df[f"{col}_char_count"] = text_col.str.len()
                has_upper = text_col.str.isupper().any()
                if not has_upper:
                    clean_df[f"{col}_has_numbers"] = text_col.str.contains(r"\d", regex=True)
                text_features_added.append(col)

        if text_features_added:
            changes.append(f"Extracted text features (word_count, char_count) from: {text_features_added}")

        # 6. Remove fully empty rows and columns
        empty_rows_before = len(clean_df)
        clean_df = clean_df.dropna(how="all")
        dropped_rows = empty_rows_before - len(clean_df)
        if dropped_rows > 0:
            changes.append(f"Dropped {dropped_rows} completely empty rows")

        empty_cols = [c for c in clean_df.columns if clean_df[c].isna().all()]
        if empty_cols:
            clean_df = clean_df.drop(columns=empty_cols)
            changes.append(f"Dropped {len(empty_cols)} completely empty columns: {empty_cols}")

        # Register the cleaned dataset
        new_id = f"{dataset_id}_clean"
        schema = context.add_dataset(new_id, clean_df, f"cleaned_{context.schemas[dataset_id].filename}")

        score_before = self._compute_quality_score(df)
        score_after = self._compute_quality_score(clean_df)

        result_data = {
            "original_dataset_id": dataset_id,
            "clean_dataset_id": new_id,
            "changes": changes,
            "change_count": len(changes),
            "original_shape": list(df.shape),
            "clean_shape": list(clean_df.shape),
            "quality_score_before": score_before,
            "quality_score_after": score_after,
            "quality_delta": score_after - score_before,
            "workflow_phase": "Data Preparation",
            "recommended_next": (
                "Phase 2 (Univariate) → eda_describe, then Phase 3 (Bivariate) → eda_correlations on the cleaned dataset."
                if score_after >= 70
                else "Quality still below 70. Consider manual review of remaining issues."
            ),
        }

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.TABLE,
            data=result_data,
            summary=(
                f"[Data Preparation] Smart-structured dataset: {len(changes)} changes applied. "
                f"Shape: {df.shape} → {clean_df.shape}. "
                f"Quality: {score_before} → {score_after}/100 (Δ+{score_after - score_before}). "
                f"Clean dataset saved as '{new_id}'. "
                f"Next: {result_data['recommended_next']}"
            ),
        )

    # ─── Helper methods ──────────────────────────────────────────────

    @staticmethod
    def _is_string_like(series: pd.Series) -> bool:
        """Check if a series holds string data (works with both object and StringDtype in pandas 3.0+)."""
        return pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)

    def _classify_column(self, series: pd.Series) -> str:
        """Classify a column as numeric, categorical, text, datetime, or boolean."""
        if pd.api.types.is_bool_dtype(series):
            return "boolean"
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        if self._is_string_like(series):
            non_null = series.dropna()
            if len(non_null) == 0:
                return "empty"
            avg_len = non_null.astype(str).str.len().mean()
            unique_ratio = non_null.nunique() / len(non_null) if len(non_null) > 0 else 0
            if avg_len > 50:
                return "text"
            if unique_ratio > 0.9 and avg_len > 20:
                return "text"
            return "categorical"
        return "other"

    def _compute_quality_score(self, df: pd.DataFrame) -> int:
        """Compute 0-100 quality score based on completeness, consistency, and validity."""
        if df.empty:
            return 0

        total_cells = df.shape[0] * df.shape[1]
        null_cells = int(df.isna().sum().sum())
        completeness = (1 - null_cells / total_cells) * 100 if total_cells > 0 else 100

        dup_ratio = df.duplicated().mean() * 100
        consistency = 100 - min(dup_ratio * 5, 30)

        mixed_type_penalty = 0
        for col in df.columns:
            sample = df[col].dropna().head(100)
            if len(sample) > 0:
                types = set(type(v).__name__ for v in sample)
                if len(types) > 1:
                    mixed_type_penalty += 5
        validity = max(100 - mixed_type_penalty, 50)

        score = int(completeness * 0.5 + consistency * 0.3 + validity * 0.2)
        return min(max(score, 0), 100)

    def _quality_recommendation(self, score: int, issues: list[dict]) -> str:
        """Apply CRISP-DM Phase 2 decision rules to recommend next steps."""
        high_count = sum(1 for i in issues if i["severity"] == "high")
        has_text = any(i["type"] == "text_heavy" for i in issues)
        has_nested = any(i["type"] == "nested_data" for i in issues)
        has_dates = any(i["type"] == "date_as_string" for i in issues)

        parts = []
        if score >= 90 and high_count == 0:
            parts.append("Data quality is excellent. Ready for Explore phase (correlations, patterns).")
        elif score >= 70:
            parts.append("Data quality is good. Minor cleanup recommended before deep analysis.")
        elif score >= 50:
            parts.append("Data quality needs improvement. Run eda_smart_structure (Modify & Prepare phase) before analysis.")
        else:
            parts.append("Data quality is poor. Must run eda_smart_structure before any meaningful analysis.")

        if has_nested:
            parts.append("Nested JSON detected — flatten with eda_smart_structure before analysis.")
        if has_text:
            parts.append("Text-heavy columns found — consider extracting features with eda_smart_structure.")
        if has_dates:
            parts.append("Date columns stored as strings — will be auto-converted by eda_smart_structure.")

        return " ".join(parts)

    def _flatten_json_column(
        self, df: pd.DataFrame, col: str
    ) -> pd.DataFrame | None:
        """Attempt to flatten a column containing dicts/JSON strings into separate columns."""
        import json as json_mod

        def parse_value(v):
            if isinstance(v, dict):
                return v
            if isinstance(v, str):
                try:
                    parsed = json_mod.loads(v)
                    if isinstance(parsed, dict):
                        return parsed
                except (json_mod.JSONDecodeError, TypeError):
                    pass
            return None

        parsed = df[col].apply(parse_value)
        valid_count = parsed.notna().sum()

        if valid_count < len(parsed) * 0.5:
            return None

        expanded = pd.json_normalize(parsed.dropna().tolist())
        expanded.columns = [f"{col}_{c}" for c in expanded.columns]
        expanded.index = parsed.dropna().index

        result = df.drop(columns=[col]).join(expanded)
        return result
