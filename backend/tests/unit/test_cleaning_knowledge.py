"""Unit tests for the Data Cleaning & Transformation knowledge base (13 sections)."""

from __future__ import annotations

import pytest

from app.agent.knowledge.cleaning_knowledge import (
    CLEANING_ANTI_PATTERNS,
    CLEANING_KNOWLEDGE,
    CLEANING_PHILOSOPHY,
    COLUMN_NAMING_RULES,
    CleaningStage,
    DEDUP_STRATEGIES,
    DERIVED_FEATURE_PATTERNS,
    DISTRIBUTION_VALIDATIONS,
    DUPLICATE_TYPES,
    DuplicateType,
    MISSING_THRESHOLDS,
    MISSING_TREATMENTS,
    OUTLIER_ACTIONS,
    OUTLIER_QUESTIONS,
    PIPELINE_STAGES,
    PROFILING_RED_FLAGS,
    QUALITY_REPORT_TEMPLATE,
    SQL_CLEANING_PATTERNS,
    STANDARDISATION_RULES,
    STRUCTURAL_VALIDATIONS,
    TYPE_CASTING_PRIORITIES,
    VALIDATION_FAILURE_PROTOCOL,
    classify_column_issues,
    get_pipeline_next_step,
    normalise_column_name,
    recommend_dedup_strategy,
    recommend_missing_treatment,
    validate_column_name,
)


# ─── 1. Structure Completeness ────────────────────────────────────────────────

class TestCleaningKnowledgeStructure:
    """Verify all 13 sections are populated and contain expected keys."""

    def test_composite_dict_has_all_sections(self):
        assert len(CLEANING_KNOWLEDGE) >= 17

    def test_philosophy_has_three_laws(self):
        assert len(CLEANING_PHILOSOPHY["three_laws"]) == 3

    def test_philosophy_has_mindset(self):
        assert "Dirty data" in CLEANING_PHILOSOPHY["mindset"]

    def test_philosophy_cost(self):
        assert len(CLEANING_PHILOSOPHY["cost_of_skipping"]) == 3

    def test_pipeline_has_8_stages(self):
        assert len(PIPELINE_STAGES) == 8

    def test_pipeline_stages_ordered(self):
        nums = [s["stage"] for s in PIPELINE_STAGES]
        assert nums == ["1", "2", "3", "4", "5", "6", "7", "8"]

    def test_profiling_red_flags(self):
        assert len(PROFILING_RED_FLAGS) >= 7

    def test_column_naming_rules(self):
        assert len(COLUMN_NAMING_RULES) >= 5
        assert any("snake_case" in r for r in COLUMN_NAMING_RULES)

    def test_type_casting_priorities(self):
        assert len(TYPE_CASTING_PRIORITIES) >= 6

    def test_duplicate_types(self):
        assert len(DUPLICATE_TYPES) == 4

    def test_dedup_strategies(self):
        assert len(DEDUP_STRATEGIES) == 5

    def test_missing_treatments(self):
        assert len(MISSING_TREATMENTS) >= 9

    def test_missing_thresholds(self):
        assert len(MISSING_THRESHOLDS) == 4

    def test_outlier_questions(self):
        assert len(OUTLIER_QUESTIONS) == 3

    def test_outlier_actions(self):
        assert len(OUTLIER_ACTIONS) >= 5

    def test_standardisation_rules_domains(self):
        assert set(STANDARDISATION_RULES.keys()) >= {"dates", "numeric", "categorical", "text"}

    def test_derived_feature_patterns(self):
        assert set(DERIVED_FEATURE_PATTERNS.keys()) >= {"time_based", "behavioral", "financial", "encoding"}

    def test_structural_validations(self):
        assert len(STRUCTURAL_VALIDATIONS) >= 7

    def test_distribution_validations(self):
        assert len(DISTRIBUTION_VALIDATIONS) >= 5

    def test_validation_failure_protocol(self):
        assert len(VALIDATION_FAILURE_PROTOCOL) == 4

    def test_sql_cleaning_patterns(self):
        assert "null_replace" in SQL_CLEANING_PATTERNS
        assert "safe_cast" in SQL_CLEANING_PATTERNS

    def test_anti_patterns(self):
        assert len(CLEANING_ANTI_PATTERNS) == 10
        for ap in CLEANING_ANTI_PATTERNS:
            assert "pattern" in ap and "why" in ap and "fix" in ap

    def test_quality_report_template(self):
        assert len(QUALITY_REPORT_TEMPLATE) >= 10


# ─── 2. Enums ─────────────────────────────────────────────────────────────────

class TestCleaningEnums:

    def test_cleaning_stage_values(self):
        assert CleaningStage.PROFILE == "profile_and_audit"
        assert CleaningStage.VALIDATION == "validation"
        assert len(CleaningStage) == 8

    def test_duplicate_type_values(self):
        assert DuplicateType.EXACT == "exact"
        assert DuplicateType.FUZZY == "fuzzy"
        assert len(DuplicateType) == 4


# ─── 3. normalise_column_name ─────────────────────────────────────────────────

class TestNormaliseColumnName:

    def test_basic_snake_case(self):
        assert normalise_column_name("Customer Name") == "customer_name"

    def test_strips_whitespace(self):
        assert normalise_column_name("  Revenue  ") == "revenue"

    def test_removes_special_chars(self):
        assert normalise_column_name("Revenue (USD)") == "revenue_usd"

    def test_already_clean(self):
        assert normalise_column_name("order_date") == "order_date"

    def test_camel_case(self):
        result = normalise_column_name("firstName")
        assert result == "firstname"

    def test_multiple_spaces(self):
        assert normalise_column_name("  first   name  ") == "first_name"

    def test_leading_digit(self):
        result = normalise_column_name("1st_column")
        assert result.startswith("col_")

    def test_empty_string(self):
        result = normalise_column_name("")
        assert result.startswith("col_")

    def test_all_special_chars(self):
        result = normalise_column_name("@#$")
        assert result.startswith("col_")


# ─── 4. validate_column_name ──────────────────────────────────────────────────

class TestValidateColumnName:

    def test_clean_name(self):
        result = validate_column_name("order_date")
        assert result["is_clean"]
        assert result["issues"] == []

    def test_spaces(self):
        result = validate_column_name("Customer Name")
        assert not result["is_clean"]
        assert any("spaces" in i for i in result["issues"])

    def test_uppercase(self):
        result = validate_column_name("AGE")
        assert not result["is_clean"]
        assert any("uppercase" in i.lower() for i in result["issues"])

    def test_special_chars(self):
        result = validate_column_name("revenue($)")
        assert not result["is_clean"]
        assert any("special" in i.lower() for i in result["issues"])

    def test_whitespace(self):
        result = validate_column_name(" name ")
        assert not result["is_clean"]
        assert any("whitespace" in i.lower() for i in result["issues"])

    def test_unnamed(self):
        result = validate_column_name("Unnamed: 0")
        assert not result["is_clean"]
        assert any("meaningful" in i.lower() for i in result["issues"])


# ─── 5. recommend_missing_treatment ───────────────────────────────────────────

class TestRecommendMissingTreatment:

    def test_mnar_always_flag(self):
        rec = recommend_missing_treatment(15, "MNAR", "numeric")
        assert "indicator_flag" in rec["method"]

    def test_mnar_high_null(self):
        rec = recommend_missing_treatment(70, "MNAR", "numeric")
        assert "indicator_flag" in rec["method"]

    def test_mar_model_based(self):
        rec = recommend_missing_treatment(10, "MAR", "numeric")
        assert "model_based" in rec["method"]

    def test_mcar_low_null_numeric(self):
        rec = recommend_missing_treatment(3, "MCAR", "numeric", is_skewed=False)
        assert "mean" in rec["method"]

    def test_mcar_low_null_skewed(self):
        rec = recommend_missing_treatment(3, "MCAR", "numeric", is_skewed=True)
        assert "median" in rec["method"]

    def test_mcar_low_null_categorical(self):
        rec = recommend_missing_treatment(2, "MCAR", "categorical")
        assert "mode" in rec["method"]

    def test_mcar_low_null_datetime(self):
        rec = recommend_missing_treatment(1, "MCAR", "datetime")
        assert "drop" in rec["method"]

    def test_moderate_null(self):
        rec = recommend_missing_treatment(15, "MCAR", "numeric")
        assert "median" in rec["method"]

    def test_high_null_drop_column(self):
        rec = recommend_missing_treatment(60, "MCAR", "numeric")
        assert "drop_column" in rec["method"]

    def test_high_null_moderate(self):
        rec = recommend_missing_treatment(30, "MCAR", "numeric")
        assert rec["method"] is not None


# ─── 6. recommend_dedup_strategy ──────────────────────────────────────────────

class TestRecommendDedupStrategy:

    def test_unclear_logic(self):
        rec = recommend_dedup_strategy(business_logic_clear=False)
        assert rec["strategy"] == "flag_and_review"

    def test_transactional(self):
        rec = recommend_dedup_strategy(is_transactional=True)
        assert rec["strategy"] == "aggregate"

    def test_completeness_variation(self):
        rec = recommend_dedup_strategy(has_completeness_variation=True)
        assert rec["strategy"] == "keep_most_complete"

    def test_has_timestamps(self):
        rec = recommend_dedup_strategy(has_timestamps=True)
        assert rec["strategy"] == "keep_last"

    def test_default(self):
        rec = recommend_dedup_strategy()
        assert rec["strategy"] == "keep_first"


# ─── 7. classify_column_issues ────────────────────────────────────────────────

class TestClassifyColumnIssues:

    def test_high_nulls(self):
        issues = classify_column_issues("float64", 30, 50, 100)
        assert any(i["flag"] == "high_nulls" for i in issues)

    def test_very_high_nulls(self):
        issues = classify_column_issues("float64", 60, 50, 100)
        assert any(i["severity"] == "high" for i in issues)

    def test_zero_variance(self):
        issues = classify_column_issues("object", 0, 1, 100)
        assert any(i["flag"] == "zero_variance" for i in issues)

    def test_possible_id_column(self):
        issues = classify_column_issues("object", 0, 95, 100, avg_str_len=10)
        assert any(i["flag"] == "possible_id_column" for i in issues)

    def test_free_text(self):
        issues = classify_column_issues("object", 0, 20, 100, avg_str_len=80)
        assert any(i["flag"] == "free_text" for i in issues)

    def test_clean_column(self):
        issues = classify_column_issues("float64", 0, 50, 100)
        assert issues == []


# ─── 8. get_pipeline_next_step ────────────────────────────────────────────────

class TestGetPipelineNextStep:

    def test_first_step(self):
        result = get_pipeline_next_step([])
        assert result["next_stage"] == "Profile & Audit"

    def test_after_profile(self):
        result = get_pipeline_next_step(["Profile & Audit"])
        assert result["next_stage"] == "Structural Fixes"

    def test_midway(self):
        result = get_pipeline_next_step(["Profile & Audit", "Structural Fixes", "Deduplication"])
        assert result["next_stage"] == "Missing Values"

    def test_all_complete(self):
        stages = [s["name"] for s in PIPELINE_STAGES]
        result = get_pipeline_next_step(stages)
        assert result["next_stage"] == "complete"

    def test_skipped_stage(self):
        result = get_pipeline_next_step(["Structural Fixes"])
        assert result["next_stage"] == "Profile & Audit"
