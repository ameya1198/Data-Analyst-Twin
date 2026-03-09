"""
Data Cleaning & Transformation Knowledge Base — 13 domains of rigorous data hygiene.

Grounded in the three laws of data cleaning:
1. Never modify source data — always work on a copy.
2. Document every transformation.
3. Validate before and after.

Sections:
 1. Foundational Philosophy (3 laws, mindset, cost of skipping)
 2. Data Cleaning Pipeline (8-step standard sequence)
 3. Data Profiling (shape, column-level metrics, red flags)
 4. Structural Fixes (naming, type casting, encoding)
 5. Deduplication (types, decision framework, fuzzy matching)
 6. Missing Values (MCAR/MAR/MNAR, treatment options, thresholds)
 7. Outlier Handling (3 questions, decision framework, capping)
 8. Standardisation (date, numeric, categorical, text)
 9. Derived Features (time, behavioral, financial, encoding)
10. Data Validation (structural, business logic, distribution)
11. SQL Transformation Patterns
12. Cleaning Anti-Patterns
13. Data Quality Reporting
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─── 1. Foundational Philosophy ──────────────────────────────────────────────

CLEANING_PHILOSOPHY: dict[str, Any] = {
    "three_laws": [
        "Never modify source data. Always work on a copy. The raw data is sacred.",
        "Document every transformation. If you can't explain why, it shouldn't have been made.",
        "Validate before and after. Row counts, distributions, and business logic must pass at every stage.",
    ],
    "mindset": (
        "Dirty data doesn't announce itself. It hides in plain sight as plausible-looking "
        "numbers that are subtly wrong. Assume the data has problems until proven otherwise."
    ),
    "cost_of_skipping": [
        "Garbage in → garbage out: No sophisticated analysis rescues a corrupted input",
        "Silent errors are worse than loud errors: A wrong dashboard number isn't caught",
        "Downstream trust: One bad number destroys stakeholder credibility for months",
    ],
}


# ─── 2. Pipeline Sequence ────────────────────────────────────────────────────

class CleaningStage(str, Enum):
    PROFILE = "profile_and_audit"
    STRUCTURAL = "structural_fixes"
    DEDUPLICATION = "deduplication"
    MISSING_VALUES = "missing_values"
    OUTLIER_HANDLING = "outlier_handling"
    STANDARDISATION = "standardisation"
    DERIVED_FEATURES = "derived_features"
    VALIDATION = "validation"


PIPELINE_STAGES: list[dict[str, str]] = [
    {"stage": "1", "name": "Profile & Audit", "action": "Understand what you have before touching anything"},
    {"stage": "2", "name": "Structural Fixes", "action": "Schema, types, column names, encodings"},
    {"stage": "3", "name": "Deduplication", "action": "Remove or flag duplicate records"},
    {"stage": "4", "name": "Missing Values", "action": "Assess, classify (MCAR/MAR/MNAR), and handle"},
    {"stage": "5", "name": "Outlier Handling", "action": "Detect, investigate, decide"},
    {"stage": "6", "name": "Standardisation", "action": "Formats, units, categories, text"},
    {"stage": "7", "name": "Derived Features", "action": "Calculate new columns from clean base"},
    {"stage": "8", "name": "Validation", "action": "Business logic checks, row counts, distributions"},
]

PIPELINE_RULE = "Never skip profiling. Jumping to transformations without understanding the data is the most common cause of re-work."


# ─── 3. Profiling Red Flags ──────────────────────────────────────────────────

PROFILING_RED_FLAGS: list[dict[str, str]] = [
    {"flag": "Null % > 20% on key column", "implication": "Major data quality issue — investigate source"},
    {"flag": "Impossible min/max (age = -3 or 999)", "implication": "Data entry error or system default value"},
    {"flag": "Dates stored as VARCHAR", "implication": "Cannot sort or filter correctly — cast to DATE"},
    {"flag": "Numerics stored as VARCHAR", "implication": "Non-numeric values hiding inside — investigate"},
    {"flag": "Distinct count = 1", "implication": "Zero variance — useless for analysis, consider dropping"},
    {"flag": "Distinct count = row count on category", "implication": "Column is unique per row — not a real category"},
    {"flag": "Free text in category column (847 distinct)", "implication": "Needs standardisation or NLP extraction"},
]


# ─── 4. Structural Fixes ─────────────────────────────────────────────────────

COLUMN_NAMING_RULES: list[str] = [
    "Use snake_case — never spaces, camelCase, or special characters",
    "Be explicit: order_date not date, customer_id not id",
    "Units in name: revenue_usd, session_duration_seconds, weight_kg",
    "Boolean prefix: is_, has_, did_ → is_active, has_churned",
    "Timestamp suffix: _at → created_at, updated_at, deleted_at",
]

TYPE_CASTING_PRIORITIES: list[dict[str, str]] = [
    {"wrong": "Date as VARCHAR", "correct": "DATE / DATETIME", "action": "CAST + validate format"},
    {"wrong": "Numbers as VARCHAR", "correct": "INT / FLOAT", "action": "CAST — check for hidden non-numeric values"},
    {"wrong": "Boolean as 0/1 INT", "correct": "BOOLEAN", "action": "CAST or map"},
    {"wrong": "Boolean as 'Y'/'N'", "correct": "BOOLEAN", "action": "MAP to TRUE/FALSE"},
    {"wrong": "Category as INT codes", "correct": "VARCHAR", "action": "JOIN or MAP to labels"},
    {"wrong": "Mixed timezone timestamps", "correct": "UTC TIMESTAMP", "action": "Normalise to UTC first"},
]


# ─── 5. Deduplication ────────────────────────────────────────────────────────

class DuplicateType(str, Enum):
    EXACT = "exact"
    KEY = "key_duplicate"
    FUZZY = "fuzzy"
    CROSS_SOURCE = "cross_source"


DUPLICATE_TYPES: list[dict[str, str]] = [
    {"type": "Exact duplicate", "description": "Identical across every column", "example": "Same row inserted twice"},
    {"type": "Key duplicate", "description": "Same ID, different column values", "example": "User updated twice, both rows kept"},
    {"type": "Fuzzy duplicate", "description": "Same entity, slightly different representation", "example": "'John Smith' vs 'Jon Smith'"},
    {"type": "Cross-source duplicate", "description": "Same record from two systems", "example": "CRM + ERP both contain same customer"},
]

DEDUP_STRATEGIES: list[dict[str, str]] = [
    {"strategy": "Keep first occurrence", "when": "Event logs where first event is canonical"},
    {"strategy": "Keep last occurrence", "when": "User records where latest update is correct"},
    {"strategy": "Keep most complete", "when": "Records where one version has more non-null fields"},
    {"strategy": "Aggregate", "when": "Transactional data where rows should be summed"},
    {"strategy": "Flag and review", "when": "Business logic is unclear — don't silently drop"},
]


# ─── 6. Missing Values ───────────────────────────────────────────────────────

MISSING_TREATMENTS: list[dict[str, str]] = [
    {"method": "Drop rows", "when": "MCAR, low % (<5%), row not needed", "risk": "Reduces sample size"},
    {"method": "Drop column", "when": ">50% missing, column not critical", "risk": "Loses signal"},
    {"method": "Mean imputation", "when": "MCAR, numeric, no outliers", "risk": "Reduces variance, distorts distribution"},
    {"method": "Median imputation", "when": "MCAR, numeric, skewed", "risk": "Better than mean for skewed; still reduces variance"},
    {"method": "Mode imputation", "when": "MCAR, categorical", "risk": "Over-represents dominant category"},
    {"method": "Forward fill", "when": "Time series — carry last known value", "risk": "Only valid where temporal continuity applies"},
    {"method": "Model-based", "when": "MAR — use other columns to predict", "risk": "Best accuracy; computationally heavy"},
    {"method": "Indicator flag", "when": "MNAR — add is_[col]_missing flag", "risk": "Preserves the signal of missing data"},
    {"method": "Business logic fill", "when": "Domain knowledge (no end_date = still active)", "risk": "Must be documented and justified"},
]

MISSING_THRESHOLDS: list[dict[str, str]] = [
    {"range": "< 5% missing", "guidance": "Imputation is generally safe"},
    {"range": "5–20% missing", "guidance": "Impute carefully; document method; flag in outputs"},
    {"range": "20–50% missing", "guidance": "Impute only with strong justification; consider dropping column"},
    {"range": "> 50% missing", "guidance": "Drop column unless missingness itself is the signal"},
]


# ─── 7. Outlier Handling ─────────────────────────────────────────────────────

OUTLIER_QUESTIONS: list[str] = [
    "Is it a data error? (Wrong unit, typo, system glitch) → Correct or remove",
    "Is it a legitimate extreme value? (Real high-value customer) → Keep",
    "Is it ambiguous? → Flag it; don't silently remove it",
]

OUTLIER_ACTIONS: list[dict[str, str]] = [
    {"type": "Impossible value (age = 300)", "investigation": "Check source system", "action": "Correct or NULL"},
    {"type": "Plausible but extreme", "investigation": "Verify with business", "action": "Keep and flag"},
    {"type": "Instrument/sensor error", "investigation": "Cross-check other sensors", "action": "Interpolate or NULL"},
    {"type": "Data entry error", "investigation": "Pattern matching", "action": "Correct with documentation"},
    {"type": "Legitimate outlier affecting model", "investigation": "Domain analysis", "action": "Segment analysis; robust statistics"},
]


# ─── 8. Standardisation ──────────────────────────────────────────────────────

STANDARDISATION_RULES: dict[str, list[str]] = {
    "dates": [
        "Always store timestamps in UTC — convert to local at display layer only",
        "Normalise to ISO 8601: YYYY-MM-DD for dates, YYYY-MM-DDTHH:MM:SSZ for timestamps",
        "Watch for: Excel serial numbers, Unix timestamps, mixed formats in same column",
    ],
    "numeric": [
        "Consistent decimal separators (. vs , — common in European data)",
        "Strip thousands separators (commas from '1,234,567')",
        "Unit consistency: same currency, same weight unit across all rows",
        "Percentage representation: pick 50 or 0.5, document, apply consistently",
    ],
    "categorical": [
        "Lowercase all values before comparison",
        "Define canonical values and map all variants: {'UK', 'U.K.', 'GB'} → 'United Kingdom'",
        "Handle legacy/deprecated categories — map to current taxonomy",
        "Maintain a category mapping table — never hardcode inline",
    ],
    "text": [
        "Strip leading/trailing whitespace always",
        "Collapse multiple spaces to single",
        "Consistent case: lowercase or title case depending on use",
        "Remove HTML tags, control characters, zero-width spaces",
    ],
}


# ─── 9. Derived Features ─────────────────────────────────────────────────────

DERIVED_FEATURE_PATTERNS: dict[str, list[str]] = {
    "time_based": [
        "Age/tenure: days since signup",
        "Recency: days since last activity",
        "Day of week, hour of day, week of year — seasonality",
        "Is weekend, is holiday — binary flags",
        "Days to event — countdown features",
    ],
    "behavioral": [
        "Frequency: count of events in a time window",
        "Monetary: sum of transactions (RFM framework)",
        "Session depth: pages per session, actions per session",
        "Funnel position: how far through a conversion funnel",
    ],
    "financial": [
        "Revenue per unit: revenue / quantity",
        "Gross margin: (revenue - cogs) / revenue",
        "Running total: cumulative sum partitioned by entity",
        "Period-over-period delta: (current - previous) / previous",
    ],
    "encoding": [
        "Binary: yes/no → 1/0",
        "One-hot: one column per category (watch cardinality)",
        "Ordinal: ordered categories → 1, 2, 3 (only when order is meaningful)",
        "Target encoding: category → mean of target (risk of leakage — use CV)",
    ],
}


# ─── 10. Validation ──────────────────────────────────────────────────────────

STRUCTURAL_VALIDATIONS: list[str] = [
    "Row count matches expectation (or explain the delta)",
    "Column count and names match schema",
    "No nulls in primary key columns",
    "Primary key is actually unique",
    "All foreign keys resolve to valid values",
    "Date ranges are plausible (no future dates where unexpected)",
    "Numeric ranges within business-logical bounds",
]

DISTRIBUTION_VALIDATIONS: list[str] = [
    "Row counts by key segment match historical pattern",
    "Null rates per column within expected range",
    "Mean/median of key numeric columns within expected range",
    "Category frequency distribution hasn't shifted dramatically",
    "No new unexpected category values appeared",
]

VALIDATION_FAILURE_PROTOCOL: list[str] = [
    "Log the failure — which check, which column, how many rows affected",
    "Quarantine affected rows — do not let bad data flow downstream",
    "Escalate if > 1% of data affected — likely a source system issue",
    "Never patch and proceed without documentation",
]


# ─── 11. SQL Patterns (reference) ────────────────────────────────────────────

SQL_CLEANING_PATTERNS: dict[str, str] = {
    "null_replace": "COALESCE(column_name, 0) or COALESCE(column_name, 'Unknown')",
    "safe_cast": "TRY_CAST(col AS INTEGER) — returns NULL instead of error",
    "date_trunc": "DATE_TRUNC('month', order_date)",
    "trim_whitespace": "TRIM(column_name)",
    "collapse_spaces": "REGEXP_REPLACE(column_name, '\\s+', ' ')",
    "lowercase": "LOWER(column_name)",
    "case_mapping": "CASE WHEN status = 'A' THEN 'Active' ... END AS status_label",
    "cap_outlier": "LEAST(GREATEST(value, lower_bound), upper_bound)",
    "flag_creation": "CASE WHEN revenue > 1000 THEN TRUE ELSE FALSE END AS is_high_value",
}


# ─── 12. Anti-Patterns ───────────────────────────────────────────────────────

CLEANING_ANTI_PATTERNS: list[dict[str, str]] = [
    {"pattern": "Modifying raw source files", "why": "Destroys reproducibility", "fix": "Always work on copies; raw data is read-only"},
    {"pattern": "Silent NULL drops", "why": "Hidden data loss with no audit trail", "fix": "Log every row removed, with reason"},
    {"pattern": "Imputing without classifying missingness", "why": "May introduce systematic bias", "fix": "Classify MCAR/MAR/MNAR first"},
    {"pattern": "Mean-imputing skewed data", "why": "Distorts distribution further", "fix": "Use median or model-based imputation"},
    {"pattern": "Dropping outliers without investigation", "why": "May delete legitimate records", "fix": "Always investigate before removing"},
    {"pattern": "Hardcoded category mappings", "why": "Brittle, undocumented", "fix": "Maintain mapping tables; reference them"},
    {"pattern": "No validation after cleaning", "why": "Can't detect if cleaning introduced errors", "fix": "Run before/after checks at every step"},
    {"pattern": "Over-cleaning for modelling", "why": "Removing variance that matters", "fix": "Understand the use case before cleaning"},
    {"pattern": "Cleaning in place with no version", "why": "Can't roll back", "fix": "Version datasets; keep pre/post snapshots"},
    {"pattern": "Fixing data instead of fixing source", "why": "Symptoms treated, root cause ignored", "fix": "Escalate systematic issues upstream"},
]


# ─── 13. Quality Report ──────────────────────────────────────────────────────

QUALITY_REPORT_TEMPLATE: list[str] = [
    "Dataset: [name, source, date received]",
    "Row count (raw): [n]",
    "Column count: [n]",
    "Primary key: [column] — Unique: [Yes/No]",
    "Date range: [min] to [max]",
    "Issues found: [list with column, type, rows affected, %]",
    "Actions taken: [list with what, why, rows affected]",
    "Row count (clean): [n] (delta: [n, %])",
    "Null rates (key columns): [list]",
    "Validation checks: [passed] / [total]",
    "Known limitations: [unresolved issues or assumptions]",
]


# ─── Composite Knowledge Export ───────────────────────────────────────────────

CLEANING_KNOWLEDGE: dict[str, Any] = {
    "philosophy": CLEANING_PHILOSOPHY,
    "pipeline_stages": PIPELINE_STAGES,
    "pipeline_rule": PIPELINE_RULE,
    "profiling_red_flags": PROFILING_RED_FLAGS,
    "column_naming_rules": COLUMN_NAMING_RULES,
    "type_casting_priorities": TYPE_CASTING_PRIORITIES,
    "duplicate_types": DUPLICATE_TYPES,
    "dedup_strategies": DEDUP_STRATEGIES,
    "missing_treatments": MISSING_TREATMENTS,
    "missing_thresholds": MISSING_THRESHOLDS,
    "outlier_questions": OUTLIER_QUESTIONS,
    "outlier_actions": OUTLIER_ACTIONS,
    "standardisation_rules": STANDARDISATION_RULES,
    "derived_feature_patterns": DERIVED_FEATURE_PATTERNS,
    "structural_validations": STRUCTURAL_VALIDATIONS,
    "distribution_validations": DISTRIBUTION_VALIDATIONS,
    "validation_failure_protocol": VALIDATION_FAILURE_PROTOCOL,
    "anti_patterns": CLEANING_ANTI_PATTERNS,
    "quality_report_template": QUALITY_REPORT_TEMPLATE,
}


# ─── Utility Functions ────────────────────────────────────────────────────────

def normalise_column_name(name: str) -> str:
    """Convert a column name to snake_case per the naming standards."""
    cleaned = name.strip()
    cleaned = re.sub(r"[^a-zA-Z0-9_\s]", "", cleaned)
    cleaned = cleaned.strip().lower()
    cleaned = re.sub(r"[\s]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"col_{cleaned}"
    return cleaned


def recommend_missing_treatment(
    null_pct: float,
    missingness_type: str = "MCAR",
    data_type: str = "numeric",
    is_skewed: bool = False,
) -> dict[str, str]:
    """Recommend a missing value treatment based on characteristics.

    Args:
        null_pct: Percentage of null values (0-100)
        missingness_type: 'MCAR', 'MAR', or 'MNAR'
        data_type: 'numeric', 'categorical', 'datetime'
        is_skewed: Whether the distribution is significantly skewed
    """
    if null_pct > 50:
        if missingness_type == "MNAR":
            return {"method": "indicator_flag", "reason": "MNAR with >50% missing — missingness is the signal. Add is_[col]_missing flag."}
        return {"method": "drop_column", "reason": f"{null_pct:.0f}% missing — column unlikely to contribute useful signal."}

    if missingness_type == "MNAR":
        return {"method": "indicator_flag", "reason": "MNAR — missingness itself is informative. Do NOT impute blindly. Add indicator flag."}

    if missingness_type == "MAR":
        return {"method": "model_based", "reason": "MAR — use other columns to predict missing values. Model-based imputation recommended."}

    if null_pct < 5:
        if data_type == "numeric":
            method = "median_imputation" if is_skewed else "mean_imputation"
            return {"method": method, "reason": f"MCAR, <5% missing, {data_type}. Safe to impute with {'median (skewed)' if is_skewed else 'mean'}."}
        if data_type == "categorical":
            return {"method": "mode_imputation", "reason": "MCAR, <5% missing, categorical. Mode imputation is appropriate."}
        return {"method": "drop_rows", "reason": f"MCAR, <5% missing, {data_type}. Dropping rows is acceptable."}

    if null_pct < 20:
        if data_type == "numeric":
            return {"method": "median_imputation", "reason": f"MCAR, {null_pct:.0f}% missing. Median imputation preserves distribution better."}
        return {"method": "mode_imputation", "reason": f"MCAR, {null_pct:.0f}% missing, categorical. Mode imputation with documentation."}

    return {"method": "model_based", "reason": f"{null_pct:.0f}% missing. High rate — consider model-based imputation or dropping."}


def recommend_dedup_strategy(
    has_timestamps: bool = False,
    has_completeness_variation: bool = False,
    is_transactional: bool = False,
    business_logic_clear: bool = True,
) -> dict[str, str]:
    """Recommend a deduplication strategy based on data characteristics."""
    if not business_logic_clear:
        return {"strategy": "flag_and_review", "reason": "Business logic unclear — flag duplicates for human review rather than auto-removing."}
    if is_transactional:
        return {"strategy": "aggregate", "reason": "Transactional data — aggregate duplicate rows (sum amounts, etc.)."}
    if has_completeness_variation:
        return {"strategy": "keep_most_complete", "reason": "Varying completeness — keep the version with the fewest NULLs."}
    if has_timestamps:
        return {"strategy": "keep_last", "reason": "Has timestamps — keep the most recent version of each record."}
    return {"strategy": "keep_first", "reason": "Default — keep first occurrence of each duplicate."}


def classify_column_issues(
    dtype: str,
    null_pct: float,
    unique_count: int,
    row_count: int,
    min_val: Any = None,
    max_val: Any = None,
    avg_str_len: float = 0,
) -> list[dict[str, str]]:
    """Identify profiling red flags for a column."""
    issues: list[dict[str, str]] = []
    unique_ratio = unique_count / row_count if row_count > 0 else 0

    if null_pct > 20:
        issues.append({"flag": "high_nulls", "detail": f"{null_pct:.0f}% null — investigate source", "severity": "high" if null_pct > 50 else "medium"})

    if unique_count <= 1 and row_count > 1:
        issues.append({"flag": "zero_variance", "detail": "Only 1 unique value — useless for analysis", "severity": "medium"})

    if "object" in dtype.lower() or "str" in dtype.lower():
        if unique_ratio > 0.9 and avg_str_len < 20:
            issues.append({"flag": "possible_id_column", "detail": "Very high cardinality — may be an ID not a category", "severity": "low"})
        if avg_str_len > 50:
            issues.append({"flag": "free_text", "detail": "Long text in what may be a category column", "severity": "low"})

    if min_val is not None and max_val is not None:
        try:
            min_f, max_f = float(min_val), float(max_val)
            if min_f < 0 and "age" in dtype.lower():
                issues.append({"flag": "impossible_value", "detail": f"Negative minimum ({min_f}) in age-like column", "severity": "high"})
        except (ValueError, TypeError):
            pass

    return issues


def get_pipeline_next_step(completed_stages: list[str]) -> dict[str, str]:
    """Given completed stages, return what should be done next."""
    stage_order = [s["name"] for s in PIPELINE_STAGES]
    for stage in stage_order:
        if stage not in completed_stages:
            matching = next(s for s in PIPELINE_STAGES if s["name"] == stage)
            return {"next_stage": stage, "action": matching["action"]}
    return {"next_stage": "complete", "action": "All pipeline stages complete. Dataset is clean."}


def validate_column_name(name: str) -> dict[str, Any]:
    """Check if a column name meets the naming standards."""
    issues: list[str] = []
    suggested = normalise_column_name(name)

    if name != name.strip():
        issues.append("Has leading/trailing whitespace")
    if " " in name.strip():
        issues.append("Contains spaces — use snake_case")
    if name != name.lower():
        issues.append("Contains uppercase — use lowercase")
    if re.search(r"[^a-zA-Z0-9_\s]", name):
        issues.append("Contains special characters")
    if name.startswith("Unnamed"):
        issues.append("Has no meaningful header name")

    return {
        "original": name,
        "clean": suggested,
        "is_clean": len(issues) == 0,
        "issues": issues,
    }
