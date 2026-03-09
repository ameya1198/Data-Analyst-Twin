"""Unit tests for the Statistical Analysis knowledge base (stats_knowledge.py)."""

from __future__ import annotations

import pytest

from app.agent.knowledge.stats_knowledge import (
    AB_TEST_CHECKLIST,
    AB_TEST_MISTAKES,
    ASSUMPTION_CHECKS,
    CORRECTION_METHODS,
    DESCRIPTIVE_STANDARDS,
    EFFECT_SIZE_THRESHOLDS,
    ERROR_TYPES,
    HYPOTHESIS_STEPS,
    MEAN_COMPARISON_TESTS,
    P_HACKING_PATTERNS,
    PLAIN_ENGLISH_MAP,
    POWER_RULES,
    PROPORTION_TESTS,
    REGRESSION_ANTI_PATTERNS,
    REGRESSION_OUTPUTS,
    RELATIONSHIP_TESTS,
    STATS_ANTI_PATTERNS,
    STATS_KNOWLEDGE,
    STATS_PHILOSOPHY,
    SUMMARY_STRUCTURE,
    TRANSFORMATION_GUIDE,
    EffectSizeMetric,
    get_correction_recommendation,
    get_descriptive_recommendation,
    get_required_sample_size,
    interpret_ci,
    interpret_effect_size,
    interpret_p_value,
    select_test,
)


class TestStatsKnowledgeStructure:
    """Verify knowledge base completeness across all 13 sections."""

    def test_philosophy_three_questions(self):
        assert len(STATS_PHILOSOPHY["three_questions"]) == 3

    def test_philosophy_p_value_misinterpretations(self):
        assert len(STATS_PHILOSOPHY["p_value_is_not"]) == 4

    def test_hypothesis_steps_count(self):
        assert len(HYPOTHESIS_STEPS) == 5
        assert HYPOTHESIS_STEPS[0]["action"] == "State hypotheses"
        assert HYPOTHESIS_STEPS[-1]["action"] == "Interpret with context"

    def test_error_types(self):
        assert "type_i" in ERROR_TYPES
        assert "type_ii" in ERROR_TYPES
        assert "tradeoff" in ERROR_TYPES

    def test_effect_size_thresholds_all_metrics(self):
        assert "cohens_d" in EFFECT_SIZE_THRESHOLDS
        assert "r" in EFFECT_SIZE_THRESHOLDS
        assert "eta_squared" in EFFECT_SIZE_THRESHOLDS
        assert "odds_ratio" in EFFECT_SIZE_THRESHOLDS

    def test_effect_size_metric_enum(self):
        assert EffectSizeMetric.COHENS_D == "cohens_d"
        assert EffectSizeMetric.ODDS_RATIO == "odds_ratio"
        assert len(EffectSizeMetric) == 4

    def test_mean_comparison_tests_count(self):
        assert len(MEAN_COMPARISON_TESTS) >= 5

    def test_proportion_tests_count(self):
        assert len(PROPORTION_TESTS) >= 5

    def test_relationship_tests_count(self):
        assert len(RELATIONSHIP_TESTS) >= 4

    def test_assumptions_checks(self):
        assert "normality" in ASSUMPTION_CHECKS
        assert "equal_variance" in ASSUMPTION_CHECKS
        assert "independence" in ASSUMPTION_CHECKS

    def test_transformation_guide_count(self):
        assert len(TRANSFORMATION_GUIDE) >= 4

    def test_ci_interpretation_keys(self):
        from app.agent.knowledge.stats_knowledge import CI_INTERPRETATION
        assert "definition" in CI_INTERPRETATION
        assert "crosses_zero" in CI_INTERPRETATION

    def test_power_rules(self):
        assert len(POWER_RULES["four_factors"]) == 4
        assert "sample_size_rules_of_thumb" in POWER_RULES

    def test_ab_test_checklist_sections(self):
        assert "pre_test" in AB_TEST_CHECKLIST
        assert "during_test" in AB_TEST_CHECKLIST
        assert "post_test" in AB_TEST_CHECKLIST
        assert len(AB_TEST_CHECKLIST["pre_test"]) >= 5

    def test_ab_test_mistakes_count(self):
        assert len(AB_TEST_MISTAKES) >= 5

    def test_correction_methods_count(self):
        assert len(CORRECTION_METHODS) >= 4

    def test_p_hacking_patterns_count(self):
        assert len(P_HACKING_PATTERNS) >= 6

    def test_regression_outputs(self):
        assert "linear" in REGRESSION_OUTPUTS
        assert "logistic" in REGRESSION_OUTPUTS
        assert len(REGRESSION_OUTPUTS["linear"]["assumptions_LINE"]) == 4

    def test_regression_anti_patterns_count(self):
        assert len(REGRESSION_ANTI_PATTERNS) >= 5

    def test_descriptive_standards_count(self):
        assert len(DESCRIPTIVE_STANDARDS) >= 5

    def test_stats_anti_patterns_count(self):
        assert len(STATS_ANTI_PATTERNS) >= 10

    def test_plain_english_map(self):
        assert len(PLAIN_ENGLISH_MAP) >= 8
        assert "p < 0.05" in PLAIN_ENGLISH_MAP

    def test_summary_structure(self):
        assert len(SUMMARY_STRUCTURE) == 3

    def test_composite_knowledge_has_all_sections(self):
        expected = [
            "philosophy", "hypothesis_steps", "error_types",
            "effect_size_thresholds", "assumptions", "ci_interpretation",
            "power_rules", "ab_test_checklist", "correction_methods",
            "regression_outputs", "descriptive_standards", "anti_patterns",
            "plain_english_map",
        ]
        for key in expected:
            assert key in STATS_KNOWLEDGE, f"Missing key: {key}"


class TestInterpretEffectSize:

    @pytest.mark.parametrize("d,expected", [
        (0.15, "small"),
        (0.5, "medium"),
        (0.85, "large"),
        (1.2, "very large"),
    ])
    def test_cohens_d(self, d: float, expected: str):
        result = interpret_effect_size("cohens_d", d)
        assert result["label"] == expected

    @pytest.mark.parametrize("r,expected", [
        (0.08, "small"),
        (0.3, "medium"),
        (0.55, "large"),
    ])
    def test_correlation_r(self, r: float, expected: str):
        result = interpret_effect_size("r", r)
        assert result["label"] == expected

    @pytest.mark.parametrize("eta,expected", [
        (0.005, "small"),
        (0.08, "medium"),
        (0.20, "large"),
    ])
    def test_eta_squared(self, eta: float, expected: str):
        result = interpret_effect_size("eta_squared", eta)
        assert result["label"] == expected

    def test_unknown_metric(self):
        result = interpret_effect_size("unknown_metric", 0.5)
        assert result["label"] == "unknown"

    def test_odds_ratio_positive(self):
        result = interpret_effect_size("odds_ratio", 2.5)
        assert "positive" in result["label"] or "risk" in result["label"]

    def test_odds_ratio_null(self):
        result = interpret_effect_size("odds_ratio", 1.0)
        assert result["label"] == "no effect"


class TestInterpretPValue:

    def test_significant(self):
        result = interpret_p_value(0.03)
        assert result["significant"] is True
        assert "moderate evidence" in result["strength"]

    def test_not_significant(self):
        result = interpret_p_value(0.15)
        assert result["significant"] is False

    def test_very_significant(self):
        result = interpret_p_value(0.0005)
        assert result["significant"] is True
        assert "very strong" in result["strength"]

    def test_trending(self):
        result = interpret_p_value(0.07)
        assert result["significant"] is False
        assert "trending" in result["strength"]

    def test_caveats_present(self):
        result = interpret_p_value(0.01)
        assert len(result["caveats"]) >= 3

    def test_custom_alpha(self):
        result = interpret_p_value(0.03, alpha=0.01)
        assert result["significant"] is False


class TestInterpretCI:

    def test_significant_positive(self):
        result = interpret_ci(2.5, 1.0, 4.0, null_value=0.0)
        assert result["significant"] is True
        assert result["direction"] == "positive"

    def test_not_significant_crosses_zero(self):
        result = interpret_ci(0.5, -1.0, 2.0, null_value=0.0)
        assert result["significant"] is False
        assert result["crosses_null"] is True

    def test_significant_negative(self):
        result = interpret_ci(-3.0, -5.0, -1.0, null_value=0.0)
        assert result["significant"] is True
        assert result["direction"] == "negative"

    def test_ratio_null_value(self):
        result = interpret_ci(1.5, 1.1, 2.0, null_value=1.0)
        assert result["significant"] is True

    def test_precision_assessment(self):
        narrow = interpret_ci(10.0, 9.5, 10.5)
        wide = interpret_ci(10.0, -50.0, 70.0)
        assert narrow["precision"] == "high"
        assert wide["precision"] == "low"


class TestSelectTest:

    def test_two_groups_normal(self):
        result = select_test("continuous", n_groups=2, normality_ok=True, n_samples=100)
        assert "Welch" in result["test"] or "t-test" in result["test"].lower()

    def test_two_groups_not_normal(self):
        result = select_test("continuous", n_groups=2, normality_ok=False, n_samples=20)
        assert "Mann-Whitney" in result["test"]

    def test_three_groups_normal(self):
        result = select_test("continuous", n_groups=3, normality_ok=True, n_samples=50)
        assert "ANOVA" in result["test"]

    def test_three_groups_not_normal(self):
        result = select_test("continuous", n_groups=3, normality_ok=False, n_samples=20)
        assert "Kruskal" in result["test"]

    def test_categorical(self):
        result = select_test("categorical", n_groups=2, n_samples=100)
        assert "Chi" in result["test"]

    def test_small_categorical_fisher(self):
        result = select_test("categorical", n_groups=2, n_samples=3)
        assert "Fisher" in result["test"]

    def test_one_sample(self):
        result = select_test("continuous", n_groups=1, normality_ok=True, n_samples=50)
        assert "t-test" in result["test"].lower()

    def test_paired(self):
        result = select_test("continuous", n_groups=2, paired=True, normality_ok=True, n_samples=50)
        assert "Paired" in result["test"]

    def test_ordinal(self):
        result = select_test("ordinal", n_groups=2)
        assert "Mann-Whitney" in result["test"]


class TestGetRequiredSampleSize:

    def test_medium_effect(self):
        result = get_required_sample_size(0.5, 0.05, 0.80)
        assert result["n_per_group"] > 50
        assert result["n_per_group"] < 80
        assert result["total_n"] == result["n_per_group"] * 2

    def test_small_effect_needs_more(self):
        small = get_required_sample_size(0.2)
        medium = get_required_sample_size(0.5)
        assert small["n_per_group"] > medium["n_per_group"]

    def test_higher_power_needs_more(self):
        p80 = get_required_sample_size(0.5, power=0.80)
        p90 = get_required_sample_size(0.5, power=0.90)
        assert p90["n_per_group"] > p80["n_per_group"]


class TestGetCorrectionRecommendation:

    def test_single_test(self):
        result = get_correction_recommendation(1)
        assert result["method"] == "none"

    def test_few_tests(self):
        result = get_correction_recommendation(3)
        assert "Bonferroni" in result["method"]

    def test_moderate_tests(self):
        result = get_correction_recommendation(10)
        assert "Holm" in result["method"]

    def test_many_tests(self):
        result = get_correction_recommendation(50)
        assert "FDR" in result["method"] or "Benjamini" in result["method"]


class TestGetDescriptiveRecommendation:

    def test_normal_continuous(self):
        result = get_descriptive_recommendation(is_normal=True, data_type="continuous")
        assert result["centre"] == "Mean"
        assert result["spread"] == "SD"

    def test_skewed_continuous(self):
        result = get_descriptive_recommendation(is_normal=False, data_type="continuous")
        assert result["centre"] == "Median"
        assert result["spread"] == "IQR"

    def test_categorical(self):
        result = get_descriptive_recommendation(is_normal=False, data_type="categorical")
        assert result["centre"] == "Mode"

    def test_binary(self):
        result = get_descriptive_recommendation(is_normal=False, data_type="binary")
        assert result["centre"] == "Proportion"
