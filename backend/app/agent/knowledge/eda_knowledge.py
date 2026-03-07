"""
EDA Specialist Knowledge Base — grounded in John Tukey's philosophy (1977).

10 knowledge domains:
1.  Foundational Philosophy (Tukey's mindset rules)
2.  The EDA Process — Sequential Phases (Overview → Univariate → Bivariate → Multivariate → Time)
3.  Data Quality Assessment (missingness types, duplicates, type issues, consistency)
4.  Outlier Detection Framework (univariate → multivariate → decision framework)
5.  Distribution Analysis Rules (shape diagnostics, normality testing, transformations)
6.  Correlation & Relationship Analysis (Pearson/Spearman/Kendall, strength guide, multicollinearity)
7.  EDA Anti-Patterns (p-hacking, data leakage, confirmation bias, over-cleaning)
8.  EDA Chart Selection by Analysis Type
9.  EDA Output Deliverables (the written brief every EDA should produce)
10. The Two Master Questions (Tukey: variation + covariation)

This knowledge is embedded directly in the specialist (Level 1) and injected
into prompts as few-shot context (Level 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─── 1. FOUNDATIONAL PHILOSOPHY ───────────────────────────────────────────────

TUKEY_PHILOSOPHY = {
    "origin": "John Tukey, 1977 — Exploratory Data Analysis",
    "core_principle": (
        "EDA was championed by John Tukey to encourage analysts to explore data "
        "and formulate hypotheses, rather than placing too much emphasis on "
        "confirmatory hypothesis testing."
    ),
    "mindset_rules": [
        "EDA is not a formal process with a strict set of rules — more than anything, it is a state of mind. During initial phases, feel free to investigate every idea that occurs to you.",
        "EDA is not about plotting everything you can think of — it is about reducing uncertainty. It answers one question: Do I understand this dataset well enough to trust what comes next?",
        "EDA is always iterative: question → visualize → transform → refine → new question.",
        "Data scientists spend 80% of their time cleaning and exploring data before building models. Effective EDA isn't optional — it's the foundation of trustworthy analytics.",
    ],
    "two_master_questions": [
        "What type of variation occurs within my variables?",
        "What type of covariation occurs between my variables?",
    ],
}


# ─── 2. EDA PROCESS — SEQUENTIAL PHASES ───────────────────────────────────────

class EDAPhase(str, Enum):
    DATASET_OVERVIEW = "dataset_overview"
    UNIVARIATE = "univariate"
    BIVARIATE = "bivariate"
    MULTIVARIATE = "multivariate"
    TEMPORAL = "temporal"


@dataclass
class PhaseSpec:
    phase: EDAPhase
    name: str
    objective: str
    key_actions: list[str]
    tools: list[str]
    outputs: list[str]
    decision_rules: list[str]
    examples: list[dict[str, str]] = field(default_factory=list)


EDA_WORKFLOW: list[PhaseSpec] = [
    PhaseSpec(
        phase=EDAPhase.DATASET_OVERVIEW,
        name="Phase 1: Dataset Overview",
        objective=(
            "Record row count, column count, data types, overall missing rate, "
            "duplicate percentage. Check schema: column names, units, expected ranges, "
            "primary keys. Characterize data relative to number of observations, "
            "number and types of features."
        ),
        key_actions=[
            "Record row count, column count, data types",
            "Compute overall missing rate and duplicate percentage",
            "Check schema: column names, units, expected ranges, primary keys",
            "Classify columns: numeric, categorical, text, datetime, nested/JSON",
            "Compute quality score based on completeness, consistency, validity",
        ],
        tools=["eda_profile", "eda_data_quality"],
        outputs=["row_count", "column_count", "type_classification", "missing_rate", "duplicate_pct", "quality_score"],
        decision_rules=[
            "If first time seeing this dataset → always run full profile first",
            "If dataset > 100K rows → note for sampling consideration in later phases",
            "If quality score < 70 → run eda_smart_structure before deeper analysis",
            "If missing rate > 40% for any column → flag, consider dropping that feature",
            "If duplicate percentage > 5% → investigate whether duplicates are legitimate",
        ],
        examples=[
            {
                "finding": "Dataset has 50,000 rows x 12 columns. 3 columns have >30% nulls. 2% duplicate rows.",
                "action": "Flag the 3 high-null columns as caveats. Investigate duplicates — check if they represent repeated events or data entry errors.",
            },
        ],
    ),
    PhaseSpec(
        phase=EDAPhase.UNIVARIATE,
        name="Phase 2: Univariate Analysis",
        objective=(
            "Analyze one variable at a time. Compute central tendency, spread, "
            "and shape. Flag skewness, heavy tails, boundary spikes, zero-inflation, "
            "and rare categories."
        ),
        key_actions=[
            "Numeric: mean, median, std, min, max, quartiles, skewness, kurtosis",
            "Categorical: frequency table, cardinality, mode, rare categories",
            "Visual: histograms, density plots, box plots, violin plots",
            "Flag: skewness > 1 or < -1, heavy tails (kurtosis > 3), bimodal distributions",
            "Flag: zero-inflation, boundary spikes, constant columns",
        ],
        tools=["eda_describe", "eda_value_counts"],
        outputs=["distribution_summaries", "skewness_flags", "outlier_candidates", "rare_category_flags"],
        decision_rules=[
            "For numeric columns: always report mean, median, std, and skewness",
            "If skewness > 1 or < -1 → note as significantly skewed, may need transformation",
            "If kurtosis > 3 → heavy tails, be cautious with mean-based statistics",
            "If a categorical has >20 unique values → may be high-cardinality (potential ID field)",
            "If a categorical has 80%+ in one category → flag as highly imbalanced",
            "If a column has only 1 unique value → flag as constant (zero information)",
            "If a column has exactly 2 unique values → binary, good for segmentation",
        ],
        examples=[
            {
                "finding": "Salary column: mean=$85K, median=$72K, skewness=1.8",
                "interpretation": "Right-skewed — a few high earners pull the mean up. Median is more representative. Consider log transform for modeling.",
            },
            {
                "finding": "Status column: 'active' 92%, 'inactive' 6%, 'suspended' 2%",
                "interpretation": "Highly imbalanced. Any model predicting status will be biased toward 'active'. Consider oversampling for minority classes.",
            },
        ],
    ),
    PhaseSpec(
        phase=EDAPhase.BIVARIATE,
        name="Phase 3: Bivariate Analysis",
        objective=(
            "Analyze relationships between pairs of variables. Numeric vs Numeric: "
            "correlation, scatter. Numeric vs Categorical: grouped statistics. "
            "Categorical vs Categorical: cross-tabulation."
        ),
        key_actions=[
            "Numeric vs Numeric: scatter plots with trend lines, Pearson/Spearman correlation",
            "Numeric vs Categorical: grouped box plots, point plots, mean comparisons",
            "Categorical vs Categorical: cross-tabulation, frequency comparison",
            "Flag strong correlations (|r| > 0.6), multicollinearity (|r| > 0.8)",
            "Note: correlation ≠ causation — always state this explicitly",
        ],
        tools=["eda_correlations", "eda_describe", "eda_value_counts"],
        outputs=["correlation_matrix", "strong_pairs", "multicollinearity_warnings", "segment_differences"],
        decision_rules=[
            "|r| 0.00–0.19 → negligible, |r| 0.20–0.39 → weak, |r| 0.40–0.59 → moderate",
            "|r| 0.60–0.79 → strong, |r| 0.80–1.00 → very strong",
            "If |r| > 0.8 between two predictors → multicollinearity warning",
            "If |r| > 0.9 → likely redundant — consider dropping one or creating composite",
            "Always check if a confounding third variable drives the correlation",
            "Use Spearman instead of Pearson when data is non-normal or has outliers",
            "Use Kendall for small samples or many tied values",
        ],
        examples=[
            {
                "pattern": "Salary correlates with tenure (r=0.85) but weakly with performance (r=0.3)",
                "insight": "Pay is primarily driven by seniority, not performance. Retention risk for high performers with low tenure.",
            },
            {
                "pattern": "Churn is 3x higher in 'Basic' plan vs 'Premium' plan",
                "insight": "Plan tier is a strong predictor of churn. Hypothesis: Basic plan lacks engagement-driving features.",
            },
        ],
    ),
    PhaseSpec(
        phase=EDAPhase.MULTIVARIATE,
        name="Phase 4: Multivariate Analysis",
        objective=(
            "Analyze three or more variables simultaneously. Techniques include pair plots, "
            "correlation heatmaps, PCA for structure and redundancy, and clustering for "
            "segment discovery."
        ),
        key_actions=[
            "Pair plots (scatter matrices) for many-variable overview",
            "Correlation heatmap for all numeric pairs at once",
            "PCA for dimensionality reduction and structure discovery",
            "Clustering for segment/group discovery",
            "Parallel coordinates for high-dimensional patterns",
        ],
        tools=["eda_correlations"],
        outputs=["full_correlation_heatmap", "cluster_candidates", "dimension_reduction_insights"],
        decision_rules=[
            "Use pair plots when exploring < 8 numeric variables",
            "Use correlation heatmap when > 8 numeric variables",
            "If many features are correlated → PCA can reveal underlying structure",
            "If natural groupings suspected → explore with clustering",
            "Always proceed from univariate → bivariate → multivariate; never skip phases",
        ],
    ),
    PhaseSpec(
        phase=EDAPhase.TEMPORAL,
        name="Phase 5: Time-based Analysis",
        objective=(
            "Check for seasonality, trends, cyclical patterns, structural breaks, "
            "and regime changes in temporal data. Align time series before comparing."
        ),
        key_actions=[
            "Check for overall trend (upward, downward, flat)",
            "Check for seasonality (monthly, quarterly, weekly patterns)",
            "Check for cyclical patterns (longer-term economic cycles)",
            "Detect structural breaks and regime changes",
            "Align time series before comparing across sources",
        ],
        tools=["eda_describe"],
        outputs=["trend_direction", "seasonality_flags", "structural_breaks"],
        decision_rules=[
            "If datetime column exists → always check for temporal patterns",
            "If time series → sort by date before any analysis",
            "If comparing multiple time series → align to same time granularity first",
            "If trend detected → check if trend is real or driven by seasonality",
            "If structural break → investigate what external event caused it",
        ],
    ),
]


# ─── 3. DATA QUALITY ASSESSMENT ───────────────────────────────────────────────

MISSING_VALUE_TYPES = {
    "MCAR": {
        "name": "Missing Completely At Random",
        "description": "Missingness has no relationship with any variable. Safe to drop or impute.",
        "detection": "Check if missing rate is uniform across all subgroups.",
        "treatment": ["Drop rows (if < 5%)", "Mean/median imputation", "Random imputation"],
    },
    "MAR": {
        "name": "Missing At Random",
        "description": "Missingness depends on observed variables but not the missing value itself.",
        "detection": "Missingness correlates with other columns (e.g., nulls concentrated in one department).",
        "treatment": ["Impute using related variables", "Model-based imputation", "Multiple imputation"],
    },
    "MNAR": {
        "name": "Missing Not At Random",
        "description": "Missingness depends on the unobserved value itself. The missingness IS informative.",
        "detection": "Cannot be fully tested — requires domain knowledge. Example: high earners not reporting salary.",
        "treatment": ["Do NOT blindly drop", "Create missingness indicator feature", "Domain-specific handling"],
    },
}

DATA_QUALITY_CHECKS = [
    {"category": "missing_values", "rule": "What % of a column is missing? If >40%, consider dropping the feature.", "severity": "high"},
    {"category": "missing_values", "rule": "Visualize missing patterns — heatmaps of nulls reveal structural gaps.", "severity": "medium"},
    {"category": "missing_values", "rule": "Classify missingness type (MCAR/MAR/MNAR) before deciding treatment.", "severity": "high"},
    {"category": "duplicates", "rule": "Check for exact duplicates (all columns match).", "severity": "medium"},
    {"category": "duplicates", "rule": "Check for near-duplicates (same entity, different IDs).", "severity": "medium"},
    {"category": "duplicates", "rule": "Understand WHY duplicates exist before removing — they may be legitimate repeated events.", "severity": "high"},
    {"category": "data_types", "rule": "Dates stored as strings, numbers stored as objects, booleans as integers — always validate.", "severity": "high"},
    {"category": "data_types", "rule": "Check for mixed types within a single column.", "severity": "high"},
    {"category": "consistency", "rule": "Values outside logical bounds (e.g. age=200, revenue=-50000).", "severity": "high"},
    {"category": "consistency", "rule": "Categorical values with inconsistent casing ('Male', 'male', 'MALE').", "severity": "medium"},
    {"category": "consistency", "rule": "Free text fields with structural patterns (phone numbers, postcodes).", "severity": "low"},
]

IMPUTATION_RULES = [
    {"data_type": "numeric", "methods": ["mean", "median", "model-based"], "prefer": "median (robust to outliers)"},
    {"data_type": "categorical", "methods": ["mode", "separate 'Unknown' category"], "prefer": "mode or 'Unknown'"},
    {"data_type": "time_series", "methods": ["forward-fill", "interpolation", "seasonal decomposition"], "prefer": "forward-fill"},
    {"data_type": "any", "rule": "If >40% missing, consider dropping the feature entirely."},
    {"data_type": "any", "rule": "Prefer imputation over dropping rows when < 20% null."},
]


# ─── 4. OUTLIER DETECTION FRAMEWORK ───────────────────────────────────────────

OUTLIER_FRAMEWORK = {
    "step_1_univariate": {
        "name": "Univariate Outliers",
        "methods": [
            {
                "name": "Z-score",
                "rule": "Flag absolute Z-scores > 3 as potential outliers.",
                "assumption": "Assumes approximately normal distribution.",
                "when_to_use": "Normally distributed numeric data.",
            },
            {
                "name": "IQR (Interquartile Range)",
                "rule": "Mild outliers: beyond 1.5 x IQR from Q1/Q3. Extreme: beyond 3 x IQR.",
                "assumption": "No distributional assumptions — robust for non-normal data.",
                "when_to_use": "Any numeric data, especially non-normal distributions.",
            },
        ],
    },
    "step_2_multivariate": {
        "name": "Multivariate Outliers",
        "description": (
            "Data points that are not outliers in any single variable but become "
            "outliers when analyzing variable combinations."
        ),
        "methods": [
            "Mahalanobis distance — measures distance from centroid accounting for correlations.",
            "Isolation Forest — tree-based anomaly detection.",
            "PCA — outliers in reduced dimension space.",
        ],
    },
    "step_3_decision": {
        "name": "Outlier Decision Framework",
        "rules": [
            "Investigate before removing — never auto-delete outliers.",
            "Ask: data entry error? Measurement failure? Rare but valid event? Fraud? System anomaly?",
            "Repeat analysis with and without outliers to assess impact.",
            "If outliers have minimal effect and are unexplainable → replace with missing values.",
            "If outliers have substantial effect → do NOT drop without documented justification.",
            "Document every outlier decision with reasoning.",
        ],
    },
}


# ─── 5. DISTRIBUTION ANALYSIS RULES ───────────────────────────────────────────

DISTRIBUTION_RULES = {
    "shape_diagnostics": [
        {"condition": "Skewness > 1 or < -1", "meaning": "Significantly skewed", "action": "Consider log or square root transformation."},
        {"condition": "Kurtosis > 3", "meaning": "Heavy tails — outliers likely", "action": "Be cautious with mean-based statistics."},
        {"condition": "Bimodal distribution", "meaning": "Possible subpopulations", "action": "Investigate grouping variable — there may be two distinct populations."},
        {"condition": "Uniform distribution", "meaning": "May indicate generated/synthetic feature", "action": "Check if this is a real data column or an artifact."},
        {"condition": "Spike at zero or boundary", "meaning": "Zero-inflation pattern", "action": "May need special modeling treatment (zero-inflated models)."},
    ],
    "normality_testing": {
        "visual": "QQ plot (quantile-normal plot) — points should follow the diagonal line.",
        "statistical": [
            {"test": "Shapiro-Wilk", "when": "Small samples (< 50 observations)"},
            {"test": "Kolmogorov-Smirnov", "when": "Large samples (>= 50 observations)"},
        ],
        "golden_rule": "Never assume normality without checking — most real-world data is not normal.",
    },
    "transformations": [
        {"problem": "Right skew (long right tail)", "transforms": ["Log", "Square root", "Box-Cox"]},
        {"problem": "Left skew (long left tail)", "transforms": ["Square", "Cube", "Exponential"]},
        {"problem": "Wide range / multiple scales", "transforms": ["Min-max normalization", "Standardization (z-score)"]},
        {"problem": "Categorical with many levels", "transforms": ["Frequency encoding", "Target encoding", "Grouping rare levels"]},
        {"problem": "Date/time", "transforms": ["Extract: day of week, month, quarter, hour, time since event"]},
    ],
}


# ─── 6. CORRELATION & RELATIONSHIP ANALYSIS ───────────────────────────────────

CORRELATION_GUIDE = {
    "methods": {
        "pearson": {"when": "Linear relationships between continuous variables", "requires": "Approximate normality"},
        "spearman": {"when": "Monotonic relationships, robust to outliers", "requires": "Ranked data — works on any ordinal/numeric"},
        "kendall": {"when": "Small samples or many tied values", "requires": "Ordinal or ranked data"},
    },
    "strength_interpretation": [
        {"range": "0.00 – 0.19", "label": "Negligible"},
        {"range": "0.20 – 0.39", "label": "Weak"},
        {"range": "0.40 – 0.59", "label": "Moderate"},
        {"range": "0.60 – 0.79", "label": "Strong"},
        {"range": "0.80 – 1.00", "label": "Very strong"},
    ],
    "multicollinearity": {
        "heatmap_threshold": 0.8,
        "vif_threshold": 5,
        "action": "Drop one of the correlated pair, or create a composite feature.",
    },
    "caution": "Correlation ≠ causation — always note this explicitly. Beware of spurious correlations driven by confounding third variables.",
}


# ─── 7. EDA ANTI-PATTERNS ─────────────────────────────────────────────────────

ANTI_PATTERNS = [
    {
        "name": "P-hacking",
        "description": "Repeated slicing of data without proper statistical correction increases the chance of false discoveries.",
        "prevention": "Pre-register hypotheses. Use Bonferroni or FDR correction for multiple comparisons.",
    },
    {
        "name": "Dropping MNAR records",
        "description": "Dropping observations that are Missing Not At Random biases results — the missingness itself carries meaningful information.",
        "prevention": "Classify missingness type before treatment. Create indicator features for MNAR.",
    },
    {
        "name": "Data leakage",
        "description": "Using variables recorded after the target event, or that act as proxies for the target, leaks information and invalidates evaluation.",
        "prevention": "Check temporal ordering of features. Remove features that are consequences of the target.",
    },
    {
        "name": "Confirmation bias",
        "description": "Exploring only data that confirms your initial hypothesis.",
        "prevention": "Actively look for disconfirming evidence. Test the opposite hypothesis.",
    },
    {
        "name": "Over-cleaning",
        "description": "Removing too many rows/outliers until the dataset no longer represents reality.",
        "prevention": "Track removal stats. Compare cleaned vs original distributions. Never remove > 10% without justification.",
    },
    {
        "name": "Ignoring data generation process",
        "description": "Not asking 'how was this data collected?' affects every interpretation.",
        "prevention": "Always document data source, collection method, and known biases.",
    },
    {
        "name": "Treating all missingness equally",
        "description": "Different missing types (MCAR/MAR/MNAR) require different treatments.",
        "prevention": "Classify missingness before choosing imputation strategy.",
    },
    {
        "name": "Stopping at univariate",
        "description": "Patterns only emerge across dimensions. Always proceed to bivariate and multivariate.",
        "prevention": "Follow the full 5-phase EDA process. Never skip phases.",
    },
]


# ─── 8. EDA CHART SELECTION ───────────────────────────────────────────────────

EDA_CHART_SELECTION = [
    {"analysis": "Single numeric distribution", "charts": ["histogram", "density plot", "box plot", "violin plot"]},
    {"analysis": "Single categorical distribution", "charts": ["bar chart", "frequency table"]},
    {"analysis": "Numeric over time", "charts": ["line chart", "area chart"]},
    {"analysis": "Numeric vs numeric", "charts": ["scatter plot", "hex bin (large data)", "line of best fit"]},
    {"analysis": "Numeric vs categorical", "charts": ["grouped box plot", "violin plot", "strip plot"]},
    {"analysis": "Categorical vs categorical", "charts": ["heatmap", "mosaic plot", "grouped bar"]},
    {"analysis": "Many variables at once", "charts": ["pair plot (scatter matrix)", "correlation heatmap"]},
    {"analysis": "High dimensional data", "charts": ["PCA biplot", "t-SNE", "parallel coordinates"]},
    {"analysis": "Missing data patterns", "charts": ["nullity matrix", "missing value heatmap"]},
    {"analysis": "Outlier identification", "charts": ["box plot", "scatter plot", "Z-score plot"]},
]


# ─── 9. EDA OUTPUT DELIVERABLES ───────────────────────────────────────────────

EDA_DELIVERABLES = [
    "Data Profile: row/column counts, types, missing rates, duplicates",
    "Key Distributions: shape, skewness, notable outliers for each important variable",
    "Top Correlations: strongest relationships found, with caveats",
    "Data Quality Issues: a ranked list of problems and recommended fixes",
    "Feature Candidates: variables likely to be predictive of the target",
    "Transformation Plan: what needs to be cleaned, encoded, scaled, or engineered before modeling",
    "Open Questions: anomalies or patterns that require domain expert input",
    "Hypotheses Generated: 3-5 testable hypotheses surfaced during exploration",
]


# ─── 10. THE TWO MASTER QUESTIONS ─────────────────────────────────────────────
# (Defined in TUKEY_PHILOSOPHY.two_master_questions above)


# ─── UTILITY FUNCTIONS ────────────────────────────────────────────────────────

def get_phase_spec(phase: EDAPhase) -> PhaseSpec:
    for spec in EDA_WORKFLOW:
        if spec.phase == phase:
            return spec
    raise ValueError(f"Unknown phase: {phase}")


def get_workflow_summary() -> str:
    """Text summary of the full EDA workflow — for LLM prompt injection."""
    lines = []
    lines.append("=== EDA Knowledge Base (John Tukey, 1977) ===")
    lines.append("")
    lines.append("Core mindset: EDA is about reducing uncertainty — do I understand this dataset")
    lines.append("well enough to trust what comes next? Always iterative: question → visualize → transform → refine.")
    lines.append("")
    lines.append("Two Master Questions:")
    lines.append("  1. What type of variation occurs within my variables?")
    lines.append("  2. What type of covariation occurs between my variables?")
    lines.append("")

    for spec in EDA_WORKFLOW:
        tools_str = ", ".join(spec.tools) if spec.tools else "none (synthesis)"
        lines.append(f"{spec.name}")
        lines.append(f"  Objective: {spec.objective[:120]}...")
        lines.append(f"  Tools: {tools_str}")
        lines.append(f"  Key rules:")
        for rule in spec.decision_rules[:3]:
            lines.append(f"    - {rule}")
        lines.append("")

    lines.append("Correlation Strength: |r| 0.0-0.19 negligible, 0.2-0.39 weak, 0.4-0.59 moderate, 0.6-0.79 strong, 0.8-1.0 very strong")
    lines.append("Multicollinearity: flag |r| > 0.8, VIF > 5")
    lines.append("")
    lines.append("Anti-patterns: p-hacking, dropping MNAR, data leakage, confirmation bias, over-cleaning, stopping at univariate")
    lines.append("")
    lines.append("Outliers: investigate before removing. Z-score > 3 (normal data), IQR 1.5x (any data). Never auto-delete.")
    lines.append("")
    lines.append("Missingness: MCAR (safe to drop/impute), MAR (impute with related vars), MNAR (DO NOT blindly drop)")

    return "\n".join(lines)


def get_decision_rules_for_tool(tool_name: str) -> list[str]:
    """Get all decision rules relevant to a specific tool."""
    rules = []
    for spec in EDA_WORKFLOW:
        if tool_name in spec.tools:
            rules.extend(spec.decision_rules)
    return rules


def get_examples_for_phase(phase: EDAPhase) -> list[dict[str, str]]:
    spec = get_phase_spec(phase)
    return spec.examples


def get_correlation_label(r: float) -> str:
    """Return human-readable strength label for a correlation coefficient."""
    abs_r = abs(r)
    if abs_r < 0.2:
        return "negligible"
    elif abs_r < 0.4:
        return "weak"
    elif abs_r < 0.6:
        return "moderate"
    elif abs_r < 0.8:
        return "strong"
    return "very strong"


def get_skewness_assessment(skewness: float) -> dict[str, str]:
    """Interpret skewness value using distribution analysis rules."""
    if abs(skewness) < 0.5:
        return {"label": "roughly symmetric", "action": "No transformation needed."}
    elif abs(skewness) < 1.0:
        direction = "right" if skewness > 0 else "left"
        return {"label": f"moderately {direction}-skewed", "action": f"Monitor — may need transformation for modeling."}
    else:
        direction = "right" if skewness > 0 else "left"
        transforms = "log or square root" if skewness > 0 else "square or exponential"
        return {"label": f"significantly {direction}-skewed", "action": f"Consider {transforms} transformation."}


def get_outlier_assessment(values: list[float]) -> dict[str, Any]:
    """Apply IQR method to detect outliers."""
    import numpy as np
    arr = np.array(values)
    q1, q3 = np.percentile(arr, [25, 75])
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    extreme_lower = q1 - 3.0 * iqr
    extreme_upper = q3 + 3.0 * iqr

    mild = int(((arr < lower) | (arr > upper)).sum())
    extreme = int(((arr < extreme_lower) | (arr > extreme_upper)).sum())

    return {
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(iqr),
        "lower_fence": float(lower),
        "upper_fence": float(upper),
        "mild_outliers": mild,
        "extreme_outliers": extreme,
        "outlier_pct": round(mild / len(arr) * 100, 1) if len(arr) > 0 else 0,
        "assessment": (
            "No outliers detected."
            if mild == 0
            else f"{mild} mild outlier(s) ({round(mild/len(arr)*100, 1)}%). "
                 + (f"{extreme} extreme." if extreme > 0 else "")
                 + (" Investigate before removing." if mild > 0 else "")
        ),
    }


def classify_missingness(null_pct: float, is_concentrated: bool) -> dict[str, str]:
    """Classify likely missingness type based on pattern."""
    if null_pct == 0:
        return {"type": "none", "treatment": "No treatment needed."}
    if null_pct > 40:
        return {
            "type": "consider_drop",
            "treatment": f"Column is {null_pct:.0f}% null. Consider dropping unless domain-critical.",
        }
    if is_concentrated:
        return {
            "type": "MAR_or_MNAR",
            "treatment": "Nulls are concentrated (systematic pattern). Likely MAR or MNAR — do NOT blindly drop. Use model-based imputation or create missingness indicator.",
        }
    return {
        "type": "likely_MCAR",
        "treatment": "Nulls appear random. Safe to impute with median (numeric) or mode (categorical).",
    }


# Combined knowledge object for easy import
EDA_KNOWLEDGE = {
    "philosophy": TUKEY_PHILOSOPHY,
    "workflow": EDA_WORKFLOW,
    "workflow_summary": get_workflow_summary(),
    "phase_count": len(EDA_WORKFLOW),
    "data_quality_checks": DATA_QUALITY_CHECKS,
    "missing_value_types": MISSING_VALUE_TYPES,
    "imputation_rules": IMPUTATION_RULES,
    "outlier_framework": OUTLIER_FRAMEWORK,
    "distribution_rules": DISTRIBUTION_RULES,
    "correlation_guide": CORRELATION_GUIDE,
    "anti_patterns": ANTI_PATTERNS,
    "chart_selection": EDA_CHART_SELECTION,
    "deliverables": EDA_DELIVERABLES,
    "total_decision_rules": sum(len(s.decision_rules) for s in EDA_WORKFLOW),
    "total_anti_patterns": len(ANTI_PATTERNS),
}
