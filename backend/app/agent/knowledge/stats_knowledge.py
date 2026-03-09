"""
Statistical Analysis Knowledge Base — 13 domains of rigorous statistical practice.

Grounded in the principle: Statistical significance and practical significance
are not the same thing. Always report all three: p-value + effect size +
confidence interval. Never report p-value alone.

Sections:
 1. Foundational Philosophy (3 questions, p-value definition)
 2. Hypothesis Testing Framework (5-step process, Type I/II errors)
 3. Effect Size (Cohen's d, r, η², OR — magnitude thresholds)
 4. Statistical Test Selection Guide (decision tree)
 5. Assumptions (normality, equal variance, independence, transformations)
 6. Confidence Intervals (interpretation, reporting standard)
 7. Statistical Power & Sample Size
 8. A/B Testing Standards
 9. Multiple Comparisons & P-Hacking
10. Regression Fundamentals (linear + logistic)
11. Descriptive Statistics Standards
12. Statistics Anti-Patterns
13. Communicating Statistics to Non-Technical Audiences
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─── 1. Foundational Philosophy ──────────────────────────────────────────────

STATS_PHILOSOPHY: dict[str, Any] = {
    "three_questions": [
        "Is the effect real? (Hypothesis testing — could this be chance?)",
        "How big is the effect? (Effect size — does it matter practically?)",
        "How certain are we? (Confidence intervals — what's the plausible range?)",
    ],
    "core_principle": (
        "Statistical significance and practical significance are not the same thing. "
        "A result can be statistically significant but meaningless in the real world, "
        "and practically important but statistically underpowered. "
        "Always report all three: p-value + effect size + confidence interval."
    ),
    "p_value_is": (
        "The probability of observing data this extreme or more extreme, "
        "assuming the null hypothesis is true."
    ),
    "p_value_is_not": [
        "The probability the null hypothesis is true",
        "The probability your result happened by chance",
        "Proof that your result is important or meaningful",
        "That p > 0.05 means 'no effect exists'",
    ],
    "mantra": "Absence of evidence is not evidence of absence.",
}


# ─── 2. Hypothesis Testing Framework ─────────────────────────────────────────

HYPOTHESIS_STEPS: list[dict[str, str]] = [
    {"step": "1", "action": "State hypotheses", "detail": "H₀ (null) and H₁ (alternative) — before looking at data"},
    {"step": "2", "action": "Set significance level", "detail": "α = 0.05 (standard), 0.01 (stricter), 0.10 (exploratory)"},
    {"step": "3", "action": "Check assumptions", "detail": "Normality, independence, equal variance — test before running"},
    {"step": "4", "action": "Calculate test statistic", "detail": "Choose correct test (see test selection guide)"},
    {"step": "5", "action": "Interpret with context", "detail": "p-value + effect size + CI + business meaning"},
]

TAIL_RULES: dict[str, str] = {
    "default": "Use two-tailed by default (tests for any difference)",
    "one_tailed": "Use one-tailed only when direction is pre-specified with strong prior justification",
    "warning": "Never switch from two-tailed to one-tailed after seeing data — this is p-hacking",
}

ERROR_TYPES: dict[str, dict[str, str]] = {
    "type_i": {
        "name": "Type I Error (false positive)",
        "symbol": "α",
        "convention": "0.05 — accept 5% false positive rate",
        "description": "Rejecting H₀ when it is actually true",
    },
    "type_ii": {
        "name": "Type II Error (false negative)",
        "symbol": "β",
        "convention": "0.20 — power target of 80%",
        "description": "Failing to reject H₀ when it is actually false",
    },
    "tradeoff": "Reducing α increases β — there is always a tradeoff",
}


# ─── 3. Effect Size ──────────────────────────────────────────────────────────

class EffectSizeMetric(str, Enum):
    COHENS_D = "cohens_d"
    CORRELATION_R = "r"
    ETA_SQUARED = "eta_squared"
    ODDS_RATIO = "odds_ratio"


EFFECT_SIZE_THRESHOLDS: dict[str, list[dict[str, str]]] = {
    "cohens_d": [
        {"threshold": "0.2", "label": "small"},
        {"threshold": "0.5", "label": "medium"},
        {"threshold": "0.8", "label": "large"},
        {"threshold": "1.0", "label": "very large"},
    ],
    "r": [
        {"threshold": "0.1", "label": "small"},
        {"threshold": "0.3", "label": "medium"},
        {"threshold": "0.5", "label": "large"},
    ],
    "eta_squared": [
        {"threshold": "0.01", "label": "small"},
        {"threshold": "0.06", "label": "medium"},
        {"threshold": "0.14", "label": "large"},
    ],
    "odds_ratio": [
        {"threshold": "1.0", "label": "no effect (null)"},
        {"threshold": "<1.0", "label": "protective / negative association"},
        {"threshold": ">1.0", "label": "increased risk / positive association"},
    ],
}

EFFECT_SIZE_RULE = (
    "Always convert effect size to business language. "
    "'Cohen's d = 0.4' means nothing to a stakeholder. "
    "'The treated group converted 12% more often, worth approximately $340k/year' "
    "is what decisions are made on."
)


# ─── 4. Statistical Test Selection Guide ─────────────────────────────────────

@dataclass
class TestRecommendation:
    scenario: str
    parametric: str
    nonparametric: str
    category: str


MEAN_COMPARISON_TESTS: list[TestRecommendation] = [
    TestRecommendation("1 sample vs. known mean", "One-sample t-test", "Wilcoxon signed-rank", "means"),
    TestRecommendation("2 independent groups", "Independent t-test", "Mann-Whitney U", "means"),
    TestRecommendation("2 paired/repeated measures", "Paired t-test", "Wilcoxon signed-rank", "means"),
    TestRecommendation("3+ independent groups", "One-way ANOVA", "Kruskal-Wallis", "means"),
    TestRecommendation("3+ groups + post-hoc", "ANOVA + Tukey HSD", "Dunn's test", "means"),
]

PROPORTION_TESTS: list[TestRecommendation] = [
    TestRecommendation("2 proportions, large samples", "Z-test for proportions", "", "proportions"),
    TestRecommendation("2×2 contingency table", "Chi-squared test", "", "proportions"),
    TestRecommendation("Small expected frequencies (<5)", "Fisher's exact test", "", "proportions"),
    TestRecommendation("Paired categorical (before/after)", "McNemar's test", "", "proportions"),
    TestRecommendation("3+ categories", "Chi-squared goodness of fit", "", "proportions"),
]

RELATIONSHIP_TESTS: list[TestRecommendation] = [
    TestRecommendation("2 continuous, normal", "Pearson correlation", "Spearman correlation", "relationships"),
    TestRecommendation("Ordinal or non-normal", "Spearman correlation", "Kendall's tau", "relationships"),
    TestRecommendation("Predict continuous outcome", "Linear regression", "", "relationships"),
    TestRecommendation("Predict binary outcome", "Logistic regression", "", "relationships"),
]

NONPARAMETRIC_WHEN: list[str] = [
    "Sample size < 30 AND distribution is non-normal",
    "Ordinal data (Likert scales, rankings)",
    "Presence of extreme outliers that cannot be removed",
    "Distribution is heavily skewed and transformation doesn't help",
]


# ─── 5. Assumptions ──────────────────────────────────────────────────────────

ASSUMPTION_CHECKS: dict[str, dict[str, Any]] = {
    "normality": {
        "visual": ["Q-Q plot (points follow diagonal)", "Histogram (bell-shaped)"],
        "formal": {
            "small_sample": "Shapiro-Wilk (n < 50)",
            "large_sample": "Kolmogorov-Smirnov (n ≥ 50)",
        },
        "rule_of_thumb": "With n > 30, t-tests are robust to mild non-normality (CLT)",
        "if_violated": "Use non-parametric alternative or apply transformation",
    },
    "equal_variance": {
        "formal": "Levene's test (p > 0.05 = equal variances assumed)",
        "if_violated": "Use Welch's t-test (does not assume equal variance) — preferred by default",
    },
    "independence": {
        "check": "Were observations collected independently? No repeated measures, no clustering.",
        "if_violated": "Use paired tests, mixed models, or multilevel models",
    },
}

TRANSFORMATION_GUIDE: list[dict[str, str]] = [
    {"condition": "Right skew (positive)", "transformation": "Log, Square root, Box-Cox"},
    {"condition": "Left skew (negative)", "transformation": "Square, Cube"},
    {"condition": "Count data", "transformation": "Square root or log(x+1)"},
    {"condition": "Proportion data", "transformation": "Arcsine square root"},
]


# ─── 6. Confidence Intervals ─────────────────────────────────────────────────

CI_INTERPRETATION: dict[str, str] = {
    "definition": (
        "A 95% CI means: If you repeated this study 100 times, approximately 95 "
        "of those intervals would contain the true population parameter."
    ),
    "not_definition": (
        "It does NOT mean there's a 95% probability the true value is in this specific interval."
    ),
    "narrow": "Narrow CI → high precision, larger sample",
    "wide": "Wide CI → low precision, small sample or high variance",
    "crosses_zero": "CI crosses zero (or 1.0 for ratios) → not statistically significant at α = 0.05",
    "above_zero": "CI entirely above zero → significant positive effect",
    "below_zero": "CI entirely below zero → significant negative effect",
    "reporting": "Always report as: estimate (95% CI: lower, upper)",
}


# ─── 7. Power & Sample Size ──────────────────────────────────────────────────

POWER_RULES: dict[str, Any] = {
    "standard_target": "80% power (β = 0.20)",
    "high_stakes": "90% power (β = 0.10)",
    "four_factors": [
        "Effect size — larger effects are easier to detect",
        "Sample size — more data = more power",
        "Significance level (α) — higher α = more power but more false positives",
        "Variance — lower variance = more power",
    ],
    "sample_size_rules_of_thumb": {
        "large_d08": {"d": 0.8, "n_per_group": 26},
        "medium_d05": {"d": 0.5, "n_per_group": 64},
        "small_d02": {"d": 0.2, "n_per_group": 394},
    },
    "critical_rule": (
        "Always calculate required sample size BEFORE running an experiment. "
        "Post-hoc power calculations are misleading."
    ),
    "underpowered_danger": (
        "Underpowered studies produce noisy estimates, inflate effect sizes of "
        "significant findings, and fail to detect real effects."
    ),
}


# ─── 8. A/B Testing Standards ────────────────────────────────────────────────

AB_TEST_CHECKLIST: dict[str, list[str]] = {
    "pre_test": [
        "Define primary metric (one only — commit before running)",
        "Define minimum detectable effect (MDE) — smallest change worth acting on",
        "Calculate required sample size based on MDE + baseline conversion rate",
        "Set runtime — don't stop early based on results (peeking problem)",
        "Randomisation check — run AA test first to verify no pre-existing differences",
    ],
    "during_test": [
        "Do not peek at results and stop when significant — inflates Type I error",
        "Do not change the test while it's running",
        "Monitor for novelty effects (first-week performance spikes that fade)",
    ],
    "post_test": [
        "Report: uplift %, p-value, 95% CI, effect size, and projected business impact",
        "If significant: verify effect size is above MDE before shipping",
        "If not significant: check power — was the test adequately powered?",
        "Segment analysis is exploratory, not confirmatory",
    ],
}

AB_TEST_MISTAKES: list[dict[str, str]] = [
    {"mistake": "Peeking and stopping early", "problem": "Inflates Type I error", "fix": "Set runtime in advance, use sequential testing"},
    {"mistake": "Multiple primary metrics", "problem": "Multiple comparisons inflate false positives", "fix": "One primary metric; rest are secondary"},
    {"mistake": "Not checking SRM", "problem": "Randomisation is broken", "fix": "Check if control/treatment split matches expected ratio"},
    {"mistake": "Calling test at 50% sample", "problem": "Underpowered", "fix": "Run to full sample size"},
    {"mistake": "Ignoring practical significance", "problem": "Tiny effect gets shipped", "fix": "Check business impact even if significant"},
]


# ─── 9. Multiple Comparisons ─────────────────────────────────────────────────

CORRECTION_METHODS: list[dict[str, str]] = [
    {"method": "Bonferroni", "when": "Few comparisons, conservative needed", "how": "Divide α by number of tests"},
    {"method": "Holm-Bonferroni", "when": "Moderate number of tests", "how": "Sequential Bonferroni, less conservative"},
    {"method": "Benjamini-Hochberg (FDR)", "when": "Many tests (genomics, feature testing)", "how": "Controls false discovery rate, not FWER"},
    {"method": "Tukey HSD", "when": "Post-hoc ANOVA pairwise", "how": "Specifically designed for all pairwise comparisons"},
]

P_HACKING_PATTERNS: list[str] = [
    "Running tests, checking significance, then collecting more data until p < 0.05",
    "Testing multiple outcomes and only reporting the significant ones",
    "Trying multiple subgroup splits until one is significant",
    "Switching from two-tailed to one-tailed after seeing the direction",
    "Removing outliers selectively to push a borderline result to significance",
    "HARKing: Hypothesising After Results are Known",
]


# ─── 10. Regression Fundamentals ─────────────────────────────────────────────

REGRESSION_OUTPUTS: dict[str, dict[str, list[str]]] = {
    "linear": {
        "key_outputs": [
            "Coefficients: direction and magnitude of each predictor's effect",
            "R²: proportion of variance explained (0 = none, 1 = perfect)",
            "Adjusted R²: penalised for number of predictors — use for model comparison",
            "p-values per coefficient: is each predictor's effect significant?",
            "Residual plots: must be random scatter, patterns = assumption violated",
        ],
        "assumptions_LINE": [
            "Linearity — relationship between X and Y is linear",
            "Independence — observations are independent",
            "Normality — residuals are normally distributed",
            "Equal variance — residual variance is constant (homoscedasticity)",
        ],
    },
    "logistic": {
        "key_outputs": [
            "Log-odds coefficients — direction of effect",
            "Odds ratios (exp(β)) — multiply-interpretable effect size",
            "AUC / ROC curve — overall model discrimination (0.5=random, 1.0=perfect, >0.7=acceptable)",
            "Confusion matrix — TP/FP/TN/FN at chosen threshold",
        ],
        "assumptions": [
            "Binary dependent variable",
            "Independence of observations",
            "No multicollinearity (VIF < 5)",
            "Large sample size (rule of thumb: 10 events per predictor)",
        ],
    },
}

REGRESSION_ANTI_PATTERNS: list[str] = [
    "Including highly correlated predictors (multicollinearity — check VIF, flag if > 5)",
    "Extrapolating predictions beyond the range of training data",
    "Using R² to compare models with different numbers of predictors (use Adjusted R²)",
    "Ignoring residual plots and assuming assumptions are met",
    "Treating regression coefficients as causal without experimental design",
]


# ─── 11. Descriptive Statistics Standards ─────────────────────────────────────

DESCRIPTIVE_STANDARDS: list[dict[str, str]] = [
    {"data_type": "Normal continuous", "centre": "Mean", "spread": "Standard deviation", "format": "Mean (SD) = 42.3 (8.1)"},
    {"data_type": "Skewed continuous", "centre": "Median", "spread": "IQR (Q1–Q3)", "format": "Median [IQR] = 38 [29–51]"},
    {"data_type": "Ordinal", "centre": "Median", "spread": "IQR", "format": "Median [IQR]"},
    {"data_type": "Categorical", "centre": "Mode", "spread": "Frequencies, %", "format": "n = 142 (34.5%)"},
    {"data_type": "Binary", "centre": "Proportion", "spread": "95% CI for proportion", "format": "p = 0.34 (95% CI: 0.29, 0.39)"},
]

DESCRIPTIVE_RULE = (
    "Never report mean alone for skewed data. Revenue, session time, load time, "
    "order value — nearly always right-skewed. Report median + IQR or mean + CI "
    "clearly noting the distribution."
)


# ─── 12. Statistics Anti-Patterns ─────────────────────────────────────────────

STATS_ANTI_PATTERNS: list[dict[str, str]] = [
    {"pattern": "Reporting p-value without effect size", "why": "Significance ≠ importance", "fix": "Always report d, r, or η² alongside p"},
    {"pattern": "'p > 0.05 means no effect'", "why": "Absence of evidence ≠ evidence of absence", "fix": "Report CI; the true effect may be undetectable given sample size"},
    {"pattern": "Stopping A/B test early", "why": "Inflates false positive rate", "fix": "Pre-specify sample size; run to completion"},
    {"pattern": "Report 1 of 20 significant results", "why": "p-hacking; expected by chance", "fix": "Correct for multiple comparisons; pre-register"},
    {"pattern": "Using mean for skewed data", "why": "Misleads about typical value", "fix": "Use median + IQR"},
    {"pattern": "Correlation = causation", "why": "Association does not imply cause", "fix": "Require experimental design or causal inference"},
    {"pattern": "Ignoring assumption checks", "why": "Invalidates the entire test", "fix": "Always test normality, variance, independence first"},
    {"pattern": "Small sample + parametric test", "why": "CLT doesn't apply below n≈30", "fix": "Use non-parametric alternatives"},
    {"pattern": "R² for logistic regression", "why": "R² is not meaningful for logistic", "fix": "Use AUC, precision-recall, or Nagelkerke R²"},
    {"pattern": "Claiming proof from a single study", "why": "One study proves nothing", "fix": "Require independent replication before acting"},
]


# ─── 13. Communicating Statistics ─────────────────────────────────────────────

PLAIN_ENGLISH_MAP: dict[str, str] = {
    "p < 0.05": "We're 95% confident this isn't random chance",
    "95% CI": "The true effect is most likely somewhere between X and Y",
    "Cohen's d = 0.5": "About half a standard deviation improvement — moderate and meaningful",
    "Statistically significant": "Unlikely to be a fluke — but doesn't tell us how big the effect is",
    "Null hypothesis rejected": "The data support the alternative — something real is happening",
    "Type I error": "False alarm — we acted on a pattern that wasn't really there",
    "Type II error": "Missed signal — a real effect existed but we didn't detect it",
    "Power = 80%": "If the effect is real, we had an 80% chance of detecting it",
}

SUMMARY_STRUCTURE = [
    "What you tested and what you found (plain language)",
    "How confident you are and what the plausible range is",
    "What this means for the business decision",
]


# ─── Composite Knowledge Export ───────────────────────────────────────────────

STATS_KNOWLEDGE: dict[str, Any] = {
    "philosophy": STATS_PHILOSOPHY,
    "hypothesis_steps": HYPOTHESIS_STEPS,
    "tail_rules": TAIL_RULES,
    "error_types": ERROR_TYPES,
    "effect_size_thresholds": EFFECT_SIZE_THRESHOLDS,
    "effect_size_rule": EFFECT_SIZE_RULE,
    "mean_comparison_tests": [
        {"scenario": t.scenario, "parametric": t.parametric, "nonparametric": t.nonparametric}
        for t in MEAN_COMPARISON_TESTS
    ],
    "proportion_tests": [
        {"scenario": t.scenario, "test": t.parametric}
        for t in PROPORTION_TESTS
    ],
    "relationship_tests": [
        {"scenario": t.scenario, "parametric": t.parametric, "nonparametric": t.nonparametric}
        for t in RELATIONSHIP_TESTS
    ],
    "assumptions": ASSUMPTION_CHECKS,
    "transformation_guide": TRANSFORMATION_GUIDE,
    "ci_interpretation": CI_INTERPRETATION,
    "power_rules": POWER_RULES,
    "ab_test_checklist": AB_TEST_CHECKLIST,
    "ab_test_mistakes": AB_TEST_MISTAKES,
    "correction_methods": CORRECTION_METHODS,
    "p_hacking_patterns": P_HACKING_PATTERNS,
    "regression_outputs": REGRESSION_OUTPUTS,
    "regression_anti_patterns": REGRESSION_ANTI_PATTERNS,
    "descriptive_standards": DESCRIPTIVE_STANDARDS,
    "anti_patterns": STATS_ANTI_PATTERNS,
    "plain_english_map": PLAIN_ENGLISH_MAP,
    "summary_structure": SUMMARY_STRUCTURE,
}


# ─── Utility Functions ────────────────────────────────────────────────────────

def interpret_effect_size(metric: str, value: float) -> dict[str, str]:
    """Classify an effect size value into small/medium/large with interpretation.

    Args:
        metric: One of 'cohens_d', 'r', 'eta_squared'
        value: The effect size value (absolute)
    """
    abs_val = abs(value)
    thresholds = EFFECT_SIZE_THRESHOLDS.get(metric)
    if thresholds is None:
        return {"label": "unknown", "interpretation": f"Unknown metric: {metric}"}

    if metric == "odds_ratio":
        if abs_val == 1.0:
            return {"label": "no effect", "interpretation": "No association"}
        direction = "positive/risk" if value > 1.0 else "protective/negative"
        return {"label": direction, "interpretation": f"OR = {value:.2f} — {direction} association"}

    label = "small"
    for t in thresholds:
        threshold_val = float(t["threshold"])
        if abs_val >= threshold_val:
            label = t["label"]

    return {"label": label, "interpretation": f"{metric} = {value:.3f} → {label} effect"}


def interpret_p_value(p: float, alpha: float = 0.05) -> dict[str, Any]:
    """Interpret a p-value with proper caveats.

    Returns dict with: significant, p_value, alpha, interpretation, caveats.
    """
    significant = p < alpha

    if p < 0.001:
        strength = "very strong evidence against H₀"
    elif p < 0.01:
        strength = "strong evidence against H₀"
    elif p < 0.05:
        strength = "moderate evidence against H₀"
    elif p < 0.10:
        strength = "weak evidence against H₀ (trending)"
    else:
        strength = "insufficient evidence to reject H₀"

    return {
        "significant": significant,
        "p_value": round(p, 6),
        "alpha": alpha,
        "strength": strength,
        "interpretation": (
            f"p = {p:.4f} — {'statistically significant' if significant else 'not statistically significant'} "
            f"at α = {alpha}. {strength}."
        ),
        "caveats": [
            "p-value does NOT measure the probability that H₀ is true",
            "Statistical significance does not imply practical significance",
            "Always pair with effect size and confidence interval",
        ],
    }


def interpret_ci(
    estimate: float,
    ci_lower: float,
    ci_upper: float,
    null_value: float = 0.0,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Interpret a confidence interval.

    Args:
        estimate: Point estimate
        ci_lower: Lower bound of CI
        ci_upper: Upper bound of CI
        null_value: Value under H₀ (0 for differences, 1 for ratios)
        confidence: Confidence level (default 0.95)
    """
    width = ci_upper - ci_lower
    crosses_null = ci_lower <= null_value <= ci_upper
    direction = "positive" if estimate > null_value else "negative" if estimate < null_value else "none"
    significant = not crosses_null

    if width < abs(estimate) * 0.5:
        precision = "high"
    elif width < abs(estimate) * 2:
        precision = "moderate"
    else:
        precision = "low"

    pct = int(confidence * 100)
    return {
        "estimate": round(estimate, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "confidence_level": pct,
        "significant": significant,
        "direction": direction,
        "precision": precision,
        "crosses_null": crosses_null,
        "interpretation": (
            f"Estimate = {estimate:.4f} ({pct}% CI: {ci_lower:.4f}, {ci_upper:.4f}). "
            + (
                f"CI does not cross {null_value} — statistically significant {direction} effect."
                if significant
                else f"CI crosses {null_value} — not statistically significant at {pct}% level."
            )
            + f" Precision: {precision}."
        ),
    }


def select_test(
    data_type: str,
    n_groups: int = 2,
    paired: bool = False,
    normality_ok: bool = True,
    n_samples: int = 100,
) -> dict[str, str]:
    """Recommend the appropriate statistical test based on data characteristics.

    Args:
        data_type: 'continuous', 'categorical', 'ordinal', 'binary'
        n_groups: Number of groups to compare
        paired: Whether measurements are paired/repeated
        normality_ok: Whether normality assumption holds
        n_samples: Sample size per group
    """
    use_parametric = normality_ok and n_samples >= 30

    if data_type == "continuous":
        if n_groups == 1:
            if use_parametric:
                return {"test": "One-sample t-test", "type": "parametric", "reason": "Single sample vs known mean, normality OK"}
            return {"test": "Wilcoxon signed-rank", "type": "nonparametric", "reason": "Single sample, normality violated or n < 30"}
        elif n_groups == 2:
            if paired:
                if use_parametric:
                    return {"test": "Paired t-test", "type": "parametric", "reason": "Two paired groups, normality OK"}
                return {"test": "Wilcoxon signed-rank", "type": "nonparametric", "reason": "Two paired groups, normality violated"}
            else:
                if use_parametric:
                    return {"test": "Welch's t-test", "type": "parametric", "reason": "Two independent groups, Welch's preferred (no equal variance assumption)"}
                return {"test": "Mann-Whitney U", "type": "nonparametric", "reason": "Two independent groups, normality violated or n < 30"}
        else:
            if use_parametric:
                return {"test": "One-way ANOVA + Tukey HSD", "type": "parametric", "reason": f"{n_groups} groups, normality OK, post-hoc for pairwise"}
            return {"test": "Kruskal-Wallis + Dunn's test", "type": "nonparametric", "reason": f"{n_groups} groups, normality violated"}

    elif data_type in ("categorical", "binary"):
        if n_groups == 2 and paired:
            return {"test": "McNemar's test", "type": "exact", "reason": "Paired categorical (before/after)"}
        if n_samples < 5:
            return {"test": "Fisher's exact test", "type": "exact", "reason": "Expected frequencies < 5"}
        return {"test": "Chi-squared test", "type": "parametric", "reason": f"Categorical data, {n_groups} groups"}

    elif data_type == "ordinal":
        if n_groups == 2:
            return {"test": "Mann-Whitney U", "type": "nonparametric", "reason": "Ordinal data, 2 groups"}
        return {"test": "Kruskal-Wallis", "type": "nonparametric", "reason": "Ordinal data, 3+ groups"}

    return {"test": "Consult a statistician", "type": "unknown", "reason": f"Unrecognized combination: {data_type}, {n_groups} groups"}


def get_required_sample_size(
    effect_size: float = 0.5,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict[str, Any]:
    """Approximate required sample size per group for a two-sample t-test.

    Uses the formula: n = (z_α/2 + z_β)² × 2 / d²
    """
    from scipy import stats as sp_stats

    z_alpha = sp_stats.norm.ppf(1 - alpha / 2)
    z_beta = sp_stats.norm.ppf(power)

    n = math.ceil(((z_alpha + z_beta) ** 2 * 2) / (effect_size ** 2))

    return {
        "n_per_group": n,
        "total_n": n * 2,
        "effect_size": effect_size,
        "alpha": alpha,
        "power": power,
        "interpretation": (
            f"Need {n} per group ({n * 2} total) to detect d = {effect_size} "
            f"at α = {alpha} with {int(power * 100)}% power."
        ),
    }


def get_correction_recommendation(n_tests: int) -> dict[str, str]:
    """Recommend a multiple comparison correction method based on number of tests."""
    if n_tests <= 1:
        return {"method": "none", "reason": "Single test — no correction needed"}
    if n_tests <= 5:
        return {"method": "Bonferroni", "reason": f"{n_tests} tests — Bonferroni is appropriate (α/{n_tests} = {0.05/n_tests:.4f})"}
    if n_tests <= 20:
        return {"method": "Holm-Bonferroni", "reason": f"{n_tests} tests — Holm-Bonferroni is less conservative than Bonferroni"}
    return {"method": "Benjamini-Hochberg (FDR)", "reason": f"{n_tests} tests — FDR control is more appropriate for many tests"}


def get_descriptive_recommendation(is_normal: bool, data_type: str) -> dict[str, str]:
    """Recommend the right descriptive statistics for a data type and distribution."""
    if data_type == "categorical":
        return {"centre": "Mode", "spread": "Frequencies, %", "format": "n (%)"}
    if data_type == "binary":
        return {"centre": "Proportion", "spread": "95% CI", "format": "p (95% CI: lower, upper)"}
    if data_type == "ordinal":
        return {"centre": "Median", "spread": "IQR", "format": "Median [IQR]"}
    if is_normal:
        return {"centre": "Mean", "spread": "SD", "format": "Mean (SD)"}
    return {"centre": "Median", "spread": "IQR", "format": "Median [IQR]"}
