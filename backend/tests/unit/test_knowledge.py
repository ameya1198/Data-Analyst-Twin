"""Tests for the EDA and Visualization knowledge bases."""

import pytest

from app.agent.knowledge.eda_knowledge import (
    EDA_KNOWLEDGE,
    EDA_WORKFLOW,
    EDAPhase,
    TUKEY_PHILOSOPHY,
    MISSING_VALUE_TYPES,
    OUTLIER_FRAMEWORK,
    DISTRIBUTION_RULES,
    CORRELATION_GUIDE,
    ANTI_PATTERNS,
    EDA_CHART_SELECTION,
    EDA_DELIVERABLES,
    DATA_QUALITY_CHECKS,
    get_workflow_summary,
    get_decision_rules_for_tool,
    get_phase_spec,
    get_examples_for_phase,
    get_correlation_label,
    get_skewness_assessment,
    get_outlier_assessment,
    classify_missingness,
)
from app.agent.knowledge.viz_knowledge import (
    VIZ_KNOWLEDGE,
    TUFTE_PRINCIPLES,
    CHART_SELECTION_RULES,
    CHART_ANTI_PATTERNS,
    get_chart_recommendation,
    get_color_palette,
    get_audience_config,
    get_plotly_layout_defaults,
    get_viz_workflow_summary,
    ChartGoal,
    PaletteType,
    AudienceLevel,
)


# ─── EDA Knowledge Structure ──────────────────────────────────────────────────

class TestEDAKnowledgeStructure:
    def test_philosophy_has_required_fields(self):
        assert "origin" in TUKEY_PHILOSOPHY
        assert "core_principle" in TUKEY_PHILOSOPHY
        assert "mindset_rules" in TUKEY_PHILOSOPHY
        assert "two_master_questions" in TUKEY_PHILOSOPHY
        assert len(TUKEY_PHILOSOPHY["mindset_rules"]) == 4
        assert len(TUKEY_PHILOSOPHY["two_master_questions"]) == 2

    def test_workflow_has_5_phases(self):
        assert len(EDA_WORKFLOW) == 5
        phases = [s.phase for s in EDA_WORKFLOW]
        assert EDAPhase.DATASET_OVERVIEW in phases
        assert EDAPhase.UNIVARIATE in phases
        assert EDAPhase.BIVARIATE in phases
        assert EDAPhase.MULTIVARIATE in phases
        assert EDAPhase.TEMPORAL in phases

    def test_each_phase_has_required_fields(self):
        for spec in EDA_WORKFLOW:
            assert spec.name
            assert spec.objective
            assert len(spec.key_actions) >= 2
            assert len(spec.decision_rules) >= 3

    def test_missing_value_types_coverage(self):
        assert "MCAR" in MISSING_VALUE_TYPES
        assert "MAR" in MISSING_VALUE_TYPES
        assert "MNAR" in MISSING_VALUE_TYPES
        for t in MISSING_VALUE_TYPES.values():
            assert "treatment" in t
            assert "description" in t

    def test_outlier_framework_has_3_steps(self):
        assert "step_1_univariate" in OUTLIER_FRAMEWORK
        assert "step_2_multivariate" in OUTLIER_FRAMEWORK
        assert "step_3_decision" in OUTLIER_FRAMEWORK
        assert len(OUTLIER_FRAMEWORK["step_3_decision"]["rules"]) >= 4

    def test_distribution_rules_completeness(self):
        assert len(DISTRIBUTION_RULES["shape_diagnostics"]) >= 5
        assert DISTRIBUTION_RULES["normality_testing"]["golden_rule"]
        assert len(DISTRIBUTION_RULES["transformations"]) >= 5

    def test_anti_patterns_count(self):
        assert len(ANTI_PATTERNS) == 8
        names = [ap["name"] for ap in ANTI_PATTERNS]
        assert "P-hacking" in names
        assert "Data leakage" in names
        assert "Confirmation bias" in names

    def test_chart_selection_coverage(self):
        assert len(EDA_CHART_SELECTION) >= 10

    def test_deliverables_count(self):
        assert len(EDA_DELIVERABLES) == 8

    def test_eda_knowledge_aggregate(self):
        assert EDA_KNOWLEDGE["phase_count"] == 5
        assert EDA_KNOWLEDGE["total_decision_rules"] >= 25
        assert EDA_KNOWLEDGE["total_anti_patterns"] == 8


# ─── EDA Knowledge Utility Functions ──────────────────────────────────────────

class TestCorrelationLabel:
    @pytest.mark.parametrize("r,expected", [
        (0.05, "negligible"),
        (0.15, "negligible"),
        (0.25, "weak"),
        (0.35, "weak"),
        (0.45, "moderate"),
        (0.55, "moderate"),
        (0.65, "strong"),
        (0.75, "strong"),
        (0.85, "very strong"),
        (0.95, "very strong"),
        (-0.85, "very strong"),
        (-0.45, "moderate"),
        (0.0, "negligible"),
    ])
    def test_correlation_labels(self, r, expected):
        assert get_correlation_label(r) == expected


class TestSkewnessAssessment:
    def test_symmetric(self):
        result = get_skewness_assessment(0.3)
        assert "symmetric" in result["label"]

    def test_moderately_skewed(self):
        result = get_skewness_assessment(0.7)
        assert "moderate" in result["label"]

    def test_significantly_right_skewed(self):
        result = get_skewness_assessment(1.5)
        assert "significantly" in result["label"]
        assert "right" in result["label"]
        assert "log" in result["action"].lower()

    def test_significantly_left_skewed(self):
        result = get_skewness_assessment(-1.5)
        assert "significantly" in result["label"]
        assert "left" in result["label"]
        assert "square" in result["action"].lower() or "exponential" in result["action"].lower()


class TestOutlierAssessment:
    def test_no_outliers(self):
        result = get_outlier_assessment([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        assert result["mild_outliers"] == 0
        assert "No outliers" in result["assessment"]

    def test_with_outliers(self):
        result = get_outlier_assessment([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        assert result["mild_outliers"] >= 1
        assert "Investigate" in result["assessment"]

    def test_extreme_outliers(self):
        result = get_outlier_assessment([1, 2, 3, 4, 5, 6, 7, 8, 9, 1000])
        assert result["extreme_outliers"] >= 1

    def test_returns_fences(self):
        result = get_outlier_assessment(list(range(100)))
        assert "lower_fence" in result
        assert "upper_fence" in result
        assert "iqr" in result


class TestMissingnessClassification:
    def test_no_missing(self):
        result = classify_missingness(0, False)
        assert result["type"] == "none"

    def test_high_missing_consider_drop(self):
        result = classify_missingness(50, False)
        assert result["type"] == "consider_drop"
        assert "50" in result["treatment"]

    def test_concentrated_mar_mnar(self):
        result = classify_missingness(15, True)
        assert result["type"] == "MAR_or_MNAR"
        assert "NOT blindly drop" in result["treatment"]

    def test_random_mcar(self):
        result = classify_missingness(10, False)
        assert result["type"] == "likely_MCAR"
        assert "impute" in result["treatment"].lower()


class TestEDAWorkflowUtils:
    def test_get_phase_spec(self):
        spec = get_phase_spec(EDAPhase.DATASET_OVERVIEW)
        assert "Phase 1" in spec.name

    def test_get_phase_spec_invalid(self):
        with pytest.raises(ValueError):
            get_phase_spec("nonexistent_phase")

    def test_get_workflow_summary_content(self):
        summary = get_workflow_summary()
        assert "Tukey" in summary
        assert "Master Questions" in summary
        assert "Phase 1" in summary
        assert "Anti-patterns" in summary
        assert "Missingness" in summary
        assert len(summary) > 1000

    def test_decision_rules_for_profile(self):
        rules = get_decision_rules_for_tool("eda_profile")
        assert len(rules) >= 4

    def test_decision_rules_for_correlations(self):
        rules = get_decision_rules_for_tool("eda_correlations")
        assert any("0.8" in r or "multicollinearity" in r.lower() for r in rules)

    def test_decision_rules_for_nonexistent_tool(self):
        rules = get_decision_rules_for_tool("nonexistent")
        assert rules == []


# ─── Viz Knowledge Structure ──────────────────────────────────────────────────

class TestVizKnowledgeStructure:
    def test_tufte_principles_exist(self):
        assert "data_ink_ratio" in TUFTE_PRINCIPLES
        assert "five_rules" in TUFTE_PRINCIPLES
        assert len(TUFTE_PRINCIPLES["five_rules"]) == 5

    def test_chart_selection_rules_exist(self):
        assert len(CHART_SELECTION_RULES) >= 7

    def test_chart_anti_patterns_exist(self):
        assert len(CHART_ANTI_PATTERNS) >= 5

    def test_viz_knowledge_aggregate(self):
        assert "tufte_principles" in VIZ_KNOWLEDGE
        assert "chart_selection_rules" in VIZ_KNOWLEDGE
        assert "audience_configs" in VIZ_KNOWLEDGE

    def test_chart_recommendation(self):
        rec = get_chart_recommendation("compare_categories")
        assert rec is not None
        assert rec.primary_chart

    def test_chart_recommendation_unknown(self):
        rec = get_chart_recommendation("teleport_data")
        assert rec is None

    def test_color_palette(self):
        pal = get_color_palette("sequential")
        assert isinstance(pal, list)
        assert len(pal) >= 3

    def test_audience_config(self):
        cfg = get_audience_config("executive")
        assert cfg is not None
        assert cfg.key_question

    def test_plotly_layout_defaults(self):
        layout = get_plotly_layout_defaults()
        assert "template" in layout
        assert layout["template"] == "plotly_white"

    def test_viz_workflow_summary(self):
        summary = get_viz_workflow_summary()
        assert "Tufte" in summary
        assert len(summary) > 500
