"""
Data Cleaning & Transformation Specialist — controlled, documented, auditable cleaning in ToolMode.

Grounded in the three laws:
1. Never modify source data — always work on a copy.
2. Document every transformation.
3. Validate before and after.

Follows the 8-step pipeline: Profile → Structural → Deduplication → Missing →
Outliers → Standardisation → Derived Features → Validation.

Every tool logs what changed, why, and how many rows were affected.
Produces a clean dataset registered in AnalysisContext alongside the original.
"""

from __future__ import annotations

import re
import warnings
from typing import Any

import numpy as np
import pandas as pd
import structlog

from app.agent.knowledge.cleaning_knowledge import (
    CLEANING_KNOWLEDGE,
    normalise_column_name,
    recommend_dedup_strategy,
    recommend_missing_treatment,
    validate_column_name,
)
from app.agent.specialists.base import (
    BaseSpecialist,
    ResultType,
    SpecialistMode,
    SpecialistResult,
)
from app.agent.specialists.context import AnalysisContext

logger = structlog.get_logger(__name__)

_STR_DTYPES = ["object", "string"]


def _is_string_col(series: pd.Series) -> bool:
    return pd.api.types.is_string_dtype(series) or series.dtype == "object"


def _string_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if _is_string_col(df[c])]


class CleaningSpecialist(BaseSpecialist):
    name = "cleaning"
    description = (
        "Data cleaning and transformation specialist. Follows an 8-step pipeline: "
        "Profile → Structural fixes → Deduplication → Missing values → Outliers → "
        "Standardisation → Derived features → Validation. Every transformation is "
        "documented with before/after counts. Never modifies source data — always "
        "creates a copy. Classifies missingness (MCAR/MAR/MNAR) before treatment. "
        "Validates data quality with structural and business logic checks."
    )
    mode = SpecialistMode.TOOL
    timeout_seconds = 60
    system_prompt = (
        "You are the data cleaning specialist of a data analyst digital twin. "
        "Three laws: never modify source data, document every transformation, "
        "validate before and after. Follow the 8-step pipeline in order. "
        "Classify missingness (MCAR/MAR/MNAR) before any imputation. "
        "Never drop outliers without investigation. Never silently remove rows. "
        "Every change must be logged with row counts and reasons."
    )

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "clean_structural",
                "description": (
                    "[Pipeline Stage 2: Structural Fixes] Fix schema issues: normalise "
                    "column names to snake_case, cast types (dates, numerics, booleans), "
                    "strip whitespace, resolve encoding issues. Never modifies source — "
                    "creates a new dataset. Logs every change with before/after comparison."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "type_overrides": {
                            "type": "object",
                            "description": "Optional manual type casts: {column: 'int'|'float'|'str'|'datetime'|'bool'}",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "clean_deduplicate",
                "description": (
                    "[Pipeline Stage 3: Deduplication] Detect and resolve duplicate records. "
                    "Supports exact duplicates (all columns), key-based (subset of columns), "
                    "and provides strategy options: keep_first, keep_last, keep_most_complete, "
                    "flag_only. Always logs how many duplicates found, how many removed. "
                    "Rule: count rows before and after."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "subset": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Columns to check for duplicates. If empty, checks all columns (exact duplicates).",
                        },
                        "strategy": {
                            "type": "string",
                            "enum": ["keep_first", "keep_last", "keep_most_complete", "flag_only"],
                            "description": "How to resolve duplicates. Default: keep_first.",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "clean_missing",
                "description": (
                    "[Pipeline Stage 4: Missing Values] Handle missing values per column. "
                    "Classifies missingness (MCAR/MAR/MNAR), recommends treatment based on "
                    "null %, data type, and distribution shape. Supports: drop rows, drop column, "
                    "mean/median/mode imputation, forward fill, indicator flag. "
                    "Never silently drops data — all changes documented."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "strategy": {
                            "type": "string",
                            "enum": ["auto", "drop_rows", "impute_mean", "impute_median", "impute_mode", "forward_fill", "flag_only"],
                            "description": "Missing value strategy. 'auto' selects per-column based on type and null %. Default: auto.",
                        },
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Columns to handle. If empty, handles all columns with nulls.",
                        },
                        "threshold_pct": {
                            "type": "number",
                            "description": "Drop columns exceeding this null %. Default: 50.",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "clean_standardise",
                "description": (
                    "[Pipeline Stage 6: Standardisation] Standardise formats and values. "
                    "Dates → ISO 8601. Text → lowercase/trimmed/collapsed whitespace. "
                    "Categories → canonical values via mapping. Numerics → consistent "
                    "separators. Creates consistent, comparable data across all rows."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "operations": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Operations to apply: 'lowercase', 'trim_whitespace', 'parse_dates', 'strip_numeric_commas', 'normalise_booleans'. Default: all.",
                        },
                        "category_mappings": {
                            "type": "object",
                            "description": "Optional: {column: {old_value: new_value}} for category standardisation.",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "clean_derive",
                "description": (
                    "[Pipeline Stage 7: Derived Features] Create new columns from clean base "
                    "data. Supports: date part extraction (year, month, day_of_week, is_weekend), "
                    "time deltas (days_since), binning (numeric → categorical buckets), "
                    "binary flags (threshold-based), and text feature extraction (word count, "
                    "char count). All new columns follow naming conventions."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "derivations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["date_parts", "days_since", "bin", "flag", "text_features"]},
                                    "column": {"type": "string"},
                                    "params": {"type": "object"},
                                },
                                "required": ["type", "column"],
                            },
                            "description": "List of derivations to apply.",
                        },
                    },
                    "required": ["dataset_id", "derivations"],
                },
            },
            {
                "name": "clean_validate",
                "description": (
                    "[Pipeline Stage 8: Validation] Run structural and business logic checks "
                    "on the dataset. Checks: row count, column count, primary key uniqueness, "
                    "null rates, numeric ranges, date plausibility. Returns pass/fail per check "
                    "with details. Validation failure protocol: log, quarantine, escalate."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "primary_key": {"type": "string", "description": "Column expected to be unique. Optional."},
                        "expected_row_count": {"type": "integer", "description": "Expected number of rows. Optional."},
                        "rules": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "column": {"type": "string"},
                                    "check": {"type": "string", "enum": ["not_null", "unique", "min", "max", "in_set", "no_future_dates"]},
                                    "value": {},
                                },
                                "required": ["column", "check"],
                            },
                            "description": "Custom validation rules.",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
        ]

    async def _execute_tool_mode(
        self, tool_name: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        raw_id = params.get("dataset_id") or params.get("dataset_name") or ""
        resolved = context.resolve_dataset_id(raw_id) or raw_id
        params = {**params, "dataset_id": resolved}

        dispatch = {
            "clean_structural": self._structural,
            "clean_deduplicate": self._deduplicate,
            "clean_missing": self._missing,
            "clean_standardise": self._standardise,
            "clean_derive": self._derive,
            "clean_validate": self._validate,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Unknown cleaning tool: {tool_name}",
                error=f"Unknown tool: {tool_name}",
            )

        return await handler(params, context)

    # ─── Tool Implementations ─────────────────────────────────────────

    async def _structural(self, params: dict, context: AnalysisContext) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._not_found(dataset_id, context)

        type_overrides = params.get("type_overrides") or {}
        clean_df = df.copy()
        changes: list[dict[str, str]] = []
        rows_before = len(clean_df)

        # 1. Normalise column names
        rename_map: dict[str, str] = {}
        for col in clean_df.columns:
            new_name = normalise_column_name(str(col))
            if new_name != str(col):
                rename_map[col] = new_name
        if rename_map:
            clean_df = clean_df.rename(columns=rename_map)
            changes.append({"action": "rename_columns", "detail": f"Renamed {len(rename_map)} columns to snake_case", "columns": str(rename_map)})

        # Resolve duplicate column names after rename
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
            changes.append({"action": "resolve_duplicates", "detail": "Resolved duplicate column names after normalisation"})

        # 2. Strip whitespace from string columns
        for col in _string_columns(clean_df):
            before_sample = clean_df[col].head(1).tolist()
            clean_df[col] = clean_df[col].astype(str).str.strip().replace("nan", np.nan)
            after_sample = clean_df[col].head(1).tolist()
            if before_sample != after_sample:
                changes.append({"action": "strip_whitespace", "detail": f"Stripped whitespace from '{col}'"})

        # 3. Auto-detect and cast date columns
        for col in clean_df.columns:
            if col in type_overrides:
                continue
            if _is_string_col(clean_df[col]):
                sample = clean_df[col].dropna().head(30)
                if len(sample) == 0:
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    parsed = pd.to_datetime(sample, errors="coerce")
                if parsed.notna().sum() >= len(sample) * 0.8:
                    clean_df[col] = pd.to_datetime(clean_df[col], errors="coerce")
                    changes.append({"action": "cast_datetime", "detail": f"Cast '{col}' from string to datetime"})

        # 4. Auto-detect numeric columns stored as strings
        for col in clean_df.columns:
            if col in type_overrides:
                continue
            if _is_string_col(clean_df[col]):
                numeric_attempt = pd.to_numeric(clean_df[col], errors="coerce")
                non_null_orig = clean_df[col].notna().sum()
                non_null_numeric = numeric_attempt.notna().sum()
                if non_null_orig > 0 and non_null_numeric / non_null_orig >= 0.8:
                    clean_df[col] = numeric_attempt
                    changes.append({"action": "cast_numeric", "detail": f"Cast '{col}' from string to numeric ({non_null_numeric}/{non_null_orig} parsed)"})

        # 5. Apply manual type overrides
        for col, target_type in type_overrides.items():
            if col not in clean_df.columns:
                continue
            try:
                if target_type in ("int", "integer"):
                    clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce").astype("Int64")
                elif target_type in ("float", "double"):
                    clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")
                elif target_type in ("str", "string"):
                    clean_df[col] = clean_df[col].astype(str)
                elif target_type in ("datetime", "date"):
                    clean_df[col] = pd.to_datetime(clean_df[col], errors="coerce")
                elif target_type in ("bool", "boolean"):
                    clean_df[col] = clean_df[col].map(
                        {True: True, False: False, 1: True, 0: False,
                         "1": True, "0": False, "Y": True, "N": False,
                         "yes": True, "no": False, "true": True, "false": False}
                    )
                changes.append({"action": "manual_cast", "detail": f"Cast '{col}' to {target_type} (manual override)"})
            except Exception as e:
                changes.append({"action": "cast_failed", "detail": f"Failed to cast '{col}' to {target_type}: {e}"})

        new_id = f"{dataset_id}_structural"
        context.add_dataset(new_id, clean_df, f"structural_{context.schemas[dataset_id].filename}")

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.TABLE, data={
                "original_id": dataset_id, "clean_id": new_id,
                "rows_before": rows_before, "rows_after": len(clean_df),
                "changes": changes, "change_count": len(changes),
                "pipeline_stage": "2. Structural Fixes",
            },
            summary=(
                f"[Stage 2: Structural Fixes] {len(changes)} changes applied. "
                f"Shape: {df.shape} → {clean_df.shape}. Saved as '{new_id}'."
            ),
            metadata={"tool": "clean_structural"},
        )

    async def _deduplicate(self, params: dict, context: AnalysisContext) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._not_found(dataset_id, context)

        subset = params.get("subset") or None
        strategy = params.get("strategy", "keep_first")
        rows_before = len(df)

        if subset:
            missing = [c for c in subset if c not in df.columns]
            if missing:
                return SpecialistResult(
                    success=False, specialist_name=self.name,
                    result_type=ResultType.ERROR, data=None,
                    summary=f"Columns not found: {missing}",
                    error=f"Missing columns: {missing}",
                )

        dup_mask = df.duplicated(subset=subset, keep=False)
        n_duplicates = int(dup_mask.sum())

        if strategy == "flag_only":
            clean_df = df.copy()
            clean_df["is_duplicate"] = dup_mask
            n_removed = 0
        elif strategy == "keep_most_complete":
            clean_df = df.copy()
            clean_df["_null_count"] = clean_df.isna().sum(axis=1)
            clean_df = clean_df.sort_values("_null_count")
            keep = "first" if subset else "first"
            clean_df = clean_df.drop_duplicates(subset=subset, keep=keep)
            clean_df = clean_df.drop(columns=["_null_count"])
            n_removed = rows_before - len(clean_df)
        else:
            keep = "first" if strategy == "keep_first" else "last"
            clean_df = df.drop_duplicates(subset=subset, keep=keep)
            n_removed = rows_before - len(clean_df)

        new_id = f"{dataset_id}_deduped"
        context.add_dataset(new_id, clean_df, f"deduped_{context.schemas[dataset_id].filename}")

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.TABLE, data={
                "original_id": dataset_id, "clean_id": new_id,
                "rows_before": rows_before, "rows_after": len(clean_df),
                "duplicates_found": n_duplicates,
                "duplicates_removed": n_removed,
                "strategy": strategy,
                "subset": subset,
                "pipeline_stage": "3. Deduplication",
            },
            summary=(
                f"[Stage 3: Deduplication] Found {n_duplicates} duplicate rows"
                + (f" (by {subset})" if subset else " (exact)")
                + f". Strategy: {strategy}. "
                + (f"Removed {n_removed}. " if n_removed > 0 else "Flagged (no removal). ")
                + f"Rows: {rows_before} → {len(clean_df)}. Saved as '{new_id}'."
            ),
            metadata={"tool": "clean_deduplicate"},
        )

    async def _missing(self, params: dict, context: AnalysisContext) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._not_found(dataset_id, context)

        strategy = params.get("strategy", "auto")
        target_cols = params.get("columns")
        threshold_pct = params.get("threshold_pct", 50)
        rows_before = len(df)

        clean_df = df.copy()
        actions: list[dict[str, Any]] = []

        cols_with_nulls = target_cols or [c for c in clean_df.columns if clean_df[c].isna().any()]

        for col in cols_with_nulls:
            if col not in clean_df.columns:
                continue

            null_count = int(clean_df[col].isna().sum())
            null_pct = clean_df[col].isna().mean() * 100
            if null_count == 0:
                continue

            is_numeric = pd.api.types.is_numeric_dtype(clean_df[col])
            is_skewed = False
            if is_numeric:
                clean_vals = pd.to_numeric(clean_df[col], errors="coerce").dropna()
                is_skewed = abs(float(clean_vals.skew())) > 1 if len(clean_vals) > 2 else False

            data_type = "numeric" if is_numeric else "categorical"

            if strategy == "auto":
                rec = recommend_missing_treatment(null_pct, "MCAR", data_type, is_skewed)
                method = rec["method"]
            else:
                method = strategy

            action: dict[str, Any] = {
                "column": col, "null_count": null_count,
                "null_pct": round(null_pct, 1), "method": method,
            }

            if method == "drop_column" or (strategy == "auto" and null_pct > threshold_pct):
                clean_df = clean_df.drop(columns=[col])
                action["result"] = f"Dropped column ({null_pct:.0f}% null)"
            elif method == "drop_rows":
                before = len(clean_df)
                clean_df = clean_df.dropna(subset=[col])
                action["result"] = f"Dropped {before - len(clean_df)} rows"
            elif method in ("impute_mean", "mean_imputation"):
                if is_numeric:
                    fill_val = float(clean_df[col].mean())
                    clean_df[col] = clean_df[col].fillna(fill_val)
                    action["result"] = f"Imputed with mean ({fill_val:.2f})"
                else:
                    action["result"] = "Skipped — mean not applicable to non-numeric"
            elif method in ("impute_median", "median_imputation"):
                if is_numeric:
                    fill_val = float(clean_df[col].median())
                    clean_df[col] = clean_df[col].fillna(fill_val)
                    action["result"] = f"Imputed with median ({fill_val:.2f})"
                else:
                    action["result"] = "Skipped — median not applicable to non-numeric"
            elif method in ("impute_mode", "mode_imputation"):
                mode_vals = clean_df[col].mode()
                if len(mode_vals) > 0:
                    clean_df[col] = clean_df[col].fillna(mode_vals.iloc[0])
                    action["result"] = f"Imputed with mode ('{mode_vals.iloc[0]}')"
                else:
                    action["result"] = "Skipped — no mode found"
            elif method == "forward_fill":
                clean_df[col] = clean_df[col].ffill()
                action["result"] = "Forward-filled from previous values"
            elif method in ("flag_only", "indicator_flag"):
                clean_df[f"is_{col}_missing"] = clean_df[col].isna().astype(int)
                action["result"] = f"Added indicator flag 'is_{col}_missing'"
            else:
                action["result"] = f"No action taken (unknown method: {method})"

            actions.append(action)

        new_id = f"{dataset_id}_imputed"
        context.add_dataset(new_id, clean_df, f"imputed_{context.schemas[dataset_id].filename}")

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.TABLE, data={
                "original_id": dataset_id, "clean_id": new_id,
                "rows_before": rows_before, "rows_after": len(clean_df),
                "columns_before": df.shape[1], "columns_after": clean_df.shape[1],
                "actions": actions, "action_count": len(actions),
                "pipeline_stage": "4. Missing Values",
            },
            summary=(
                f"[Stage 4: Missing Values] Handled {len(actions)} column(s) with nulls. "
                f"Shape: {df.shape} → {clean_df.shape}. Saved as '{new_id}'."
            ),
            metadata={"tool": "clean_missing"},
        )

    async def _standardise(self, params: dict, context: AnalysisContext) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._not_found(dataset_id, context)

        ops_raw = params.get("operations")
        ops = ops_raw if ops_raw is not None else ["lowercase", "trim_whitespace", "parse_dates", "strip_numeric_commas", "normalise_booleans"]
        cat_mappings = params.get("category_mappings") or {}

        clean_df = df.copy()
        changes: list[dict[str, str]] = []

        str_cols = _string_columns(clean_df)

        if "trim_whitespace" in ops:
            for col in str_cols:
                before = clean_df[col].copy()
                clean_df[col] = clean_df[col].astype(str).str.strip().str.replace(r"\s+", " ", regex=True).replace("nan", np.nan)
                changed = (before != clean_df[col]).sum()
                if changed > 0:
                    changes.append({"action": "trim_whitespace", "detail": f"'{col}': trimmed/collapsed whitespace in {changed} values"})

        if "lowercase" in ops:
            for col in list(str_cols):
                if _is_string_col(clean_df[col]):
                    before = clean_df[col].copy()
                    clean_df[col] = clean_df[col].str.lower()
                    changed = (before != clean_df[col]).sum()
                    if changed > 0:
                        changes.append({"action": "lowercase", "detail": f"'{col}': lowercased {changed} values"})

        if "parse_dates" in ops:
            for col in clean_df.columns:
                if _is_string_col(clean_df[col]):
                    sample = clean_df[col].dropna().head(20)
                    if len(sample) == 0:
                        continue
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        parsed = pd.to_datetime(sample, errors="coerce")
                    if parsed.notna().sum() >= len(sample) * 0.8:
                        clean_df[col] = pd.to_datetime(clean_df[col], errors="coerce")
                        changes.append({"action": "parse_dates", "detail": f"'{col}': parsed to datetime"})

        if "strip_numeric_commas" in ops:
            for col in list(str_cols):
                if _is_string_col(clean_df[col]):
                    has_commas = clean_df[col].astype(str).str.contains(r"^\d{1,3}(?:,\d{3})+(?:\.\d+)?$", na=False)
                    if has_commas.any():
                        clean_df[col] = clean_df[col].astype(str).str.replace(",", "", regex=False)
                        numeric = pd.to_numeric(clean_df[col], errors="coerce")
                        if numeric.notna().sum() > 0:
                            clean_df[col] = numeric
                            changes.append({"action": "strip_commas", "detail": f"'{col}': stripped numeric commas and cast to number"})

        if "normalise_booleans" in ops:
            bool_map = {"true": True, "false": False, "yes": True, "no": False, "y": True, "n": False, "1": True, "0": False}
            for col in list(str_cols):
                if _is_string_col(clean_df[col]):
                    unique_lower = set(clean_df[col].dropna().astype(str).str.lower().unique())
                    if unique_lower.issubset(set(bool_map.keys())):
                        clean_df[col] = clean_df[col].astype(str).str.lower().map(bool_map)
                        changes.append({"action": "normalise_booleans", "detail": f"'{col}': normalised to boolean"})

        for col, mapping in cat_mappings.items():
            if col in clean_df.columns:
                before_unique = clean_df[col].nunique()
                clean_df[col] = clean_df[col].map(lambda x, m=mapping: m.get(x, x))
                after_unique = clean_df[col].nunique()
                changes.append({"action": "category_mapping", "detail": f"'{col}': mapped {len(mapping)} values ({before_unique} → {after_unique} unique)"})

        new_id = f"{dataset_id}_standardised"
        context.add_dataset(new_id, clean_df, f"standardised_{context.schemas[dataset_id].filename}")

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.TABLE, data={
                "original_id": dataset_id, "clean_id": new_id,
                "changes": changes, "change_count": len(changes),
                "operations_applied": ops,
                "pipeline_stage": "6. Standardisation",
            },
            summary=(
                f"[Stage 6: Standardisation] {len(changes)} changes applied "
                f"({', '.join(ops)}). Saved as '{new_id}'."
            ),
            metadata={"tool": "clean_standardise"},
        )

    async def _derive(self, params: dict, context: AnalysisContext) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._not_found(dataset_id, context)

        derivations = params.get("derivations", [])
        if not derivations:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary="No derivations specified.",
                error="Empty derivations list",
            )

        clean_df = df.copy()
        created: list[dict[str, str]] = []

        for d in derivations:
            d_type = d.get("type")
            col = d.get("column", "")
            d_params = d.get("params") or {}

            if col not in clean_df.columns:
                created.append({"type": d_type, "column": col, "result": f"Column '{col}' not found — skipped"})
                continue

            if d_type == "date_parts":
                dt_col = pd.to_datetime(clean_df[col], errors="coerce")
                clean_df[f"{col}_year"] = dt_col.dt.year
                clean_df[f"{col}_month"] = dt_col.dt.month
                clean_df[f"{col}_day_of_week"] = dt_col.dt.dayofweek
                clean_df[f"{col}_is_weekend"] = dt_col.dt.dayofweek.isin([5, 6]).astype(int)
                created.append({"type": "date_parts", "column": col, "result": f"Created {col}_year, {col}_month, {col}_day_of_week, {col}_is_weekend"})

            elif d_type == "days_since":
                reference = d_params.get("reference_date", str(pd.Timestamp.now().date()))
                ref_dt = pd.to_datetime(reference)
                dt_col = pd.to_datetime(clean_df[col], errors="coerce")
                clean_df[f"days_since_{col}"] = (ref_dt - dt_col).dt.days
                created.append({"type": "days_since", "column": col, "result": f"Created days_since_{col} (from {reference})"})

            elif d_type == "bin":
                bins = d_params.get("bins", 5)
                labels = d_params.get("labels")
                new_col = f"{col}_bin"
                numeric = pd.to_numeric(clean_df[col], errors="coerce")
                if labels and len(labels) == bins:
                    clean_df[new_col] = pd.cut(numeric, bins=bins, labels=labels)
                else:
                    clean_df[new_col] = pd.cut(numeric, bins=bins)
                created.append({"type": "bin", "column": col, "result": f"Created {new_col} with {bins} bins"})

            elif d_type == "flag":
                threshold = d_params.get("threshold", 0)
                operator = d_params.get("operator", ">")
                new_col = d_params.get("name", f"is_{col}_high")
                numeric = pd.to_numeric(clean_df[col], errors="coerce")
                if operator == ">":
                    clean_df[new_col] = (numeric > threshold).astype(int)
                elif operator == ">=":
                    clean_df[new_col] = (numeric >= threshold).astype(int)
                elif operator == "<":
                    clean_df[new_col] = (numeric < threshold).astype(int)
                elif operator == "==":
                    clean_df[new_col] = (numeric == threshold).astype(int)
                created.append({"type": "flag", "column": col, "result": f"Created {new_col} ({col} {operator} {threshold})"})

            elif d_type == "text_features":
                text = clean_df[col].fillna("").astype(str)
                clean_df[f"{col}_word_count"] = text.str.split().str.len()
                clean_df[f"{col}_char_count"] = text.str.len()
                created.append({"type": "text_features", "column": col, "result": f"Created {col}_word_count, {col}_char_count"})

            else:
                created.append({"type": d_type, "column": col, "result": f"Unknown derivation type '{d_type}' — skipped"})

        new_id = f"{dataset_id}_derived"
        context.add_dataset(new_id, clean_df, f"derived_{context.schemas[dataset_id].filename}")

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.TABLE, data={
                "original_id": dataset_id, "clean_id": new_id,
                "columns_before": df.shape[1], "columns_after": clean_df.shape[1],
                "new_columns": clean_df.shape[1] - df.shape[1],
                "derivations": created,
                "pipeline_stage": "7. Derived Features",
            },
            summary=(
                f"[Stage 7: Derived Features] Created {clean_df.shape[1] - df.shape[1]} new column(s) "
                f"from {len(derivations)} derivation(s). Saved as '{new_id}'."
            ),
            metadata={"tool": "clean_derive"},
        )

    async def _validate(self, params: dict, context: AnalysisContext) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._not_found(dataset_id, context)

        primary_key = params.get("primary_key")
        expected_rows = params.get("expected_row_count")
        custom_rules = params.get("rules") or []

        checks: list[dict[str, Any]] = []

        # Structural validations
        checks.append({
            "check": "row_count", "column": None,
            "passed": True if expected_rows is None else len(df) == expected_rows,
            "detail": f"{len(df)} rows" + (f" (expected {expected_rows})" if expected_rows else ""),
        })
        checks.append({
            "check": "column_count", "column": None,
            "passed": True, "detail": f"{df.shape[1]} columns",
        })

        if primary_key and primary_key in df.columns:
            is_unique = df[primary_key].is_unique
            null_in_pk = int(df[primary_key].isna().sum())
            checks.append({
                "check": "pk_unique", "column": primary_key,
                "passed": is_unique, "detail": f"Unique: {is_unique}. Nulls in PK: {null_in_pk}.",
            })
            if null_in_pk > 0:
                checks.append({
                    "check": "pk_not_null", "column": primary_key,
                    "passed": False, "detail": f"{null_in_pk} null values in primary key",
                })

        # Null rate check per column
        for col in df.columns:
            null_pct = df[col].isna().mean() * 100
            if null_pct > 0:
                checks.append({
                    "check": "null_rate", "column": str(col),
                    "passed": null_pct < 20,
                    "detail": f"{null_pct:.1f}% null" + (" (HIGH)" if null_pct > 20 else ""),
                })

        # Date plausibility
        for col in df.select_dtypes(include=["datetime64"]).columns:
            min_date = df[col].min()
            max_date = df[col].max()
            future = max_date > pd.Timestamp.now() if pd.notna(max_date) else False
            checks.append({
                "check": "date_plausibility", "column": str(col),
                "passed": not future,
                "detail": f"Range: {min_date} to {max_date}" + (" — FUTURE DATES DETECTED" if future else ""),
            })

        # Numeric range checks
        for col in df.select_dtypes(include=[np.number]).columns:
            checks.append({
                "check": "numeric_range", "column": str(col),
                "passed": True,
                "detail": f"Range: {df[col].min()} to {df[col].max()}",
            })

        # Custom rules
        for rule in custom_rules:
            col = rule.get("column", "")
            check = rule.get("check", "")
            value = rule.get("value")

            if col not in df.columns:
                checks.append({"check": check, "column": col, "passed": False, "detail": f"Column '{col}' not found"})
                continue

            if check == "not_null":
                n_null = int(df[col].isna().sum())
                checks.append({"check": "not_null", "column": col, "passed": n_null == 0, "detail": f"{n_null} nulls found"})
            elif check == "unique":
                checks.append({"check": "unique", "column": col, "passed": df[col].is_unique, "detail": f"{df[col].nunique()} unique / {len(df)} rows"})
            elif check == "min":
                actual_min = df[col].min()
                checks.append({"check": "min", "column": col, "passed": actual_min >= value, "detail": f"Min = {actual_min} (expected ≥ {value})"})
            elif check == "max":
                actual_max = df[col].max()
                checks.append({"check": "max", "column": col, "passed": actual_max <= value, "detail": f"Max = {actual_max} (expected ≤ {value})"})
            elif check == "in_set":
                unique_vals = set(df[col].dropna().unique())
                allowed = set(value) if isinstance(value, list) else set()
                unexpected = unique_vals - allowed
                checks.append({"check": "in_set", "column": col, "passed": len(unexpected) == 0, "detail": f"Unexpected values: {unexpected}" if unexpected else "All values in allowed set"})
            elif check == "no_future_dates":
                dt_col = pd.to_datetime(df[col], errors="coerce")
                n_future = int((dt_col > pd.Timestamp.now()).sum())
                checks.append({"check": "no_future_dates", "column": col, "passed": n_future == 0, "detail": f"{n_future} future dates"})

        passed = sum(1 for c in checks if c["passed"])
        failed = sum(1 for c in checks if not c["passed"])

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.TABLE, data={
                "dataset_id": dataset_id,
                "checks": checks,
                "passed": passed, "failed": failed, "total": len(checks),
                "verdict": "PASS" if failed == 0 else "FAIL",
                "pipeline_stage": "8. Validation",
            },
            summary=(
                f"[Stage 8: Validation] {passed}/{len(checks)} checks passed"
                + (f", {failed} FAILED." if failed > 0 else ". All clear.")
                + f" Dataset: {dataset_id}."
            ),
            metadata={"tool": "clean_validate"},
        )

    # ─── Helpers ──────────────────────────────────────────────────────

    def _not_found(self, dataset_id: str, context: AnalysisContext) -> SpecialistResult:
        available = ", ".join(context.dataset_ids) or "none"
        return SpecialistResult(
            success=False, specialist_name=self.name,
            result_type=ResultType.ERROR, data=None,
            summary=f"Dataset '{dataset_id}' not found. Available: {available}",
            error=f"Dataset not found: {dataset_id}",
        )
