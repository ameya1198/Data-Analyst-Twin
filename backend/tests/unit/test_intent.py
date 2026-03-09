"""Unit tests for the Intent Classifier — routing user requests to execution modes."""

from __future__ import annotations

import pytest

from app.agent.intent import (
    ClassifiedIntent,
    ExecutionMode,
    IntentClassifier,
    UserIntent,
)


@pytest.fixture
def classifier() -> IntentClassifier:
    return IntentClassifier()


# ─── DIRECT Mode (0 LLM calls) ───────────────────────────────────────────────

class TestDirectMode:
    """Requests that map to a single known tool — skip Plan/Reflect/Synthesize."""

    def test_profile_data(self, classifier: IntentClassifier):
        r = classifier.classify("Profile my data")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.PROFILE_DATA
        assert r.direct_tool == "eda_profile"

    def test_profile_overview(self, classifier: IntentClassifier):
        r = classifier.classify("Give me an overview of the dataset")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.PROFILE_DATA

    def test_summarize_data(self, classifier: IntentClassifier):
        r = classifier.classify("Summarize the data")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.PROFILE_DATA

    def test_data_quality(self, classifier: IntentClassifier):
        r = classifier.classify("Check the data quality")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.DATA_QUALITY
        assert r.direct_tool == "eda_data_quality"

    def test_describe_columns(self, classifier: IntentClassifier):
        r = classifier.classify("Describe the columns in my dataset")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.DESCRIBE_COLUMNS
        assert r.direct_tool == "eda_describe"

    def test_summary_statistics(self, classifier: IntentClassifier):
        r = classifier.classify("Show me summary statistics")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.DESCRIBE_COLUMNS

    def test_correlations(self, classifier: IntentClassifier):
        r = classifier.classify("Show correlations between variables")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.CORRELATIONS
        assert r.direct_tool == "eda_correlations"

    def test_correlation_matrix(self, classifier: IntentClassifier):
        r = classifier.classify("What's the correlation matrix?")
        assert r.mode == ExecutionMode.DIRECT

    def test_value_counts(self, classifier: IntentClassifier):
        r = classifier.classify("Show me value counts for department")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.VALUE_COUNTS
        assert r.direct_tool == "eda_value_counts"

    def test_frequency_distribution(self, classifier: IntentClassifier):
        r = classifier.classify("What's the frequency distribution of status?")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.VALUE_COUNTS

    def test_how_many_per_category(self, classifier: IntentClassifier):
        r = classifier.classify("How many orders per product category?")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.VALUE_COUNTS

    def test_schema(self, classifier: IntentClassifier):
        r = classifier.classify("Show me the schema")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.SCHEMA
        assert r.direct_tool == "sql_schema"

    def test_show_tables(self, classifier: IntentClassifier):
        r = classifier.classify("Show tables")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.SCHEMA

    def test_column_names(self, classifier: IntentClassifier):
        r = classifier.classify("What are the column names?")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.SCHEMA

    def test_validate(self, classifier: IntentClassifier):
        r = classifier.classify("Validate the dataset")
        assert r.mode == ExecutionMode.DIRECT
        assert r.intent == UserIntent.VALIDATE
        assert r.direct_tool == "clean_validate"


# ─── FOCUSED Mode (2 LLM calls) ──────────────────────────────────────────────

class TestFocusedMode:
    """Requests that need planning but skip reflection."""

    def test_run_eda(self, classifier: IntentClassifier):
        r = classifier.classify("Run EDA on this dataset")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.RUN_EDA

    def test_exploratory_analysis(self, classifier: IntentClassifier):
        r = classifier.classify("Do exploratory data analysis")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.RUN_EDA

    def test_explore_data(self, classifier: IntentClassifier):
        r = classifier.classify("Explore the data for me")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.RUN_EDA

    def test_sql_query(self, classifier: IntentClassifier):
        r = classifier.classify("Write a SQL query to find the top 10 customers by revenue")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.SQL_QUERY

    def test_sql_select(self, classifier: IntentClassifier):
        r = classifier.classify("SELECT * FROM orders WHERE amount > 100")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.SQL_QUERY

    def test_sql_aggregation(self, classifier: IntentClassifier):
        r = classifier.classify("Aggregate revenue by month")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.SQL_QUERY

    def test_sql_cohort(self, classifier: IntentClassifier):
        r = classifier.classify("Build a cohort analysis")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.SQL_QUERY

    def test_sql_funnel(self, classifier: IntentClassifier):
        r = classifier.classify("Create a funnel analysis for user signups")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.SQL_QUERY

    def test_sql_retention(self, classifier: IntentClassifier):
        r = classifier.classify("Calculate user retention rates")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.SQL_QUERY

    def test_statistical_test(self, classifier: IntentClassifier):
        r = classifier.classify("Is there a significant difference between groups?")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.STATISTICAL_TEST

    def test_hypothesis_test(self, classifier: IntentClassifier):
        r = classifier.classify("Run a hypothesis test on conversion rates")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.STATISTICAL_TEST

    def test_t_test(self, classifier: IntentClassifier):
        r = classifier.classify("Run a t-test comparing control and treatment")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.STATISTICAL_TEST

    def test_anova(self, classifier: IntentClassifier):
        r = classifier.classify("Run ANOVA across the three departments")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.STATISTICAL_TEST

    def test_p_value(self, classifier: IntentClassifier):
        r = classifier.classify("What's the p-value for this difference?")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.STATISTICAL_TEST

    def test_ab_test(self, classifier: IntentClassifier):
        r = classifier.classify("Evaluate this A/B test")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.AB_TEST

    def test_ab_test_variant(self, classifier: IntentClassifier):
        r = classifier.classify("Run an a/b test analysis")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.AB_TEST

    def test_regression(self, classifier: IntentClassifier):
        r = classifier.classify("Run a regression to predict salary")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.REGRESSION

    def test_linear_model(self, classifier: IntentClassifier):
        r = classifier.classify("Build a linear model for revenue")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.REGRESSION

    def test_logistic_regression(self, classifier: IntentClassifier):
        r = classifier.classify("Run logistic regression on churn")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.REGRESSION

    def test_power_analysis(self, classifier: IntentClassifier):
        r = classifier.classify("How big should my sample size be?")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.STATISTICAL_TEST

    def test_effect_size(self, classifier: IntentClassifier):
        r = classifier.classify("What effect size can I detect with 500 samples?")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.STATISTICAL_TEST

    def test_visualization(self, classifier: IntentClassifier):
        r = classifier.classify("Make a bar chart of revenue by category")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.VISUALIZATION

    def test_scatter_plot(self, classifier: IntentClassifier):
        r = classifier.classify("Show me a scatter plot of age vs salary")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.VISUALIZATION

    def test_histogram(self, classifier: IntentClassifier):
        r = classifier.classify("Show the histogram for income distribution")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.VISUALIZATION

    def test_heatmap(self, classifier: IntentClassifier):
        r = classifier.classify("Create a heatmap of the data")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.VISUALIZATION

    def test_clean_data(self, classifier: IntentClassifier):
        r = classifier.classify("Clean this dataset")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.CLEAN_DATA

    def test_fix_missing_values(self, classifier: IntentClassifier):
        r = classifier.classify("Fix the missing values in this data")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.CLEAN_DATA

    def test_deduplicate(self, classifier: IntentClassifier):
        r = classifier.classify("Remove duplicates from the dataset")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.CLEAN_DATA

    def test_standardise(self, classifier: IntentClassifier):
        r = classifier.classify("Standardise the column formats")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.CLEAN_DATA

    def test_impute(self, classifier: IntentClassifier):
        r = classifier.classify("Impute the missing data")
        assert r.mode == ExecutionMode.FOCUSED
        assert r.intent == UserIntent.CLEAN_DATA


# ─── FULL Mode (3-5 LLM calls) ───────────────────────────────────────────────

class TestFullMode:
    """Open-ended exploration that needs the full Plan-Execute-Reflect-Synthesize loop."""

    def test_analyze_data(self, classifier: IntentClassifier):
        r = classifier.classify("Analyze this dataset")
        assert r.mode == ExecutionMode.FULL
        assert r.intent == UserIntent.OPEN_EXPLORATION

    def test_what_insights(self, classifier: IntentClassifier):
        r = classifier.classify("What insights can you find in this data?")
        assert r.mode == ExecutionMode.FULL
        assert r.intent == UserIntent.OPEN_EXPLORATION

    def test_what_can_you_tell(self, classifier: IntentClassifier):
        r = classifier.classify("What can you tell me about this dataset?")
        assert r.mode == ExecutionMode.FULL
        assert r.intent == UserIntent.OPEN_EXPLORATION

    def test_deep_dive(self, classifier: IntentClassifier):
        r = classifier.classify("Do a deep dive into our sales data")
        assert r.mode == ExecutionMode.FULL
        assert r.intent == UserIntent.OPEN_EXPLORATION

    def test_comprehensive_analysis(self, classifier: IntentClassifier):
        r = classifier.classify("I need a comprehensive analysis")
        assert r.mode == ExecutionMode.FULL
        assert r.intent == UserIntent.OPEN_EXPLORATION

    def test_whats_going_on(self, classifier: IntentClassifier):
        r = classifier.classify("What's going on with our revenue numbers?")
        assert r.mode == ExecutionMode.FULL
        assert r.intent == UserIntent.OPEN_EXPLORATION

    def test_full_report(self, classifier: IntentClassifier):
        r = classifier.classify("Generate a report on this data")
        assert r.mode == ExecutionMode.FULL
        assert r.intent == UserIntent.OPEN_EXPLORATION

    def test_investigate(self, classifier: IntentClassifier):
        r = classifier.classify("Investigate the drop in user engagement")
        assert r.mode == ExecutionMode.FULL
        assert r.intent == UserIntent.OPEN_EXPLORATION


# ─── CONVERSATIONAL Mode ──────────────────────────────────────────────────────

class TestConversationalMode:
    """Follow-ups and references to previous results."""

    def test_now_prefix(self, classifier: IntentClassifier):
        r = classifier.classify("Now show me a chart of that", has_conversation_history=True)
        assert r.mode == ExecutionMode.CONVERSATIONAL
        assert r.intent == UserIntent.FOLLOW_UP

    def test_also_prefix(self, classifier: IntentClassifier):
        r = classifier.classify("Also check for outliers", has_conversation_history=True)
        assert r.mode == ExecutionMode.CONVERSATIONAL
        assert r.intent == UserIntent.FOLLOW_UP

    def test_what_about(self, classifier: IntentClassifier):
        r = classifier.classify("What about the marketing department?", has_conversation_history=True)
        assert r.mode == ExecutionMode.CONVERSATIONAL
        assert r.intent == UserIntent.FOLLOW_UP

    def test_can_you_also(self, classifier: IntentClassifier):
        r = classifier.classify("Can you also run it for Q4?", has_conversation_history=True)
        assert r.mode == ExecutionMode.CONVERSATIONAL
        assert r.intent == UserIntent.FOLLOW_UP

    def test_that_result(self, classifier: IntentClassifier):
        r = classifier.classify("Filter that result by region", has_conversation_history=True)
        assert r.mode == ExecutionMode.CONVERSATIONAL
        assert r.intent == UserIntent.FOLLOW_UP

    def test_previous_analysis(self, classifier: IntentClassifier):
        r = classifier.classify("Redo the previous analysis with only 2024 data", has_conversation_history=True)
        assert r.mode == ExecutionMode.CONVERSATIONAL
        assert r.intent == UserIntent.FOLLOW_UP

    def test_no_history_no_followup(self, classifier: IntentClassifier):
        """Follow-up patterns without conversation history should not trigger CONVERSATIONAL."""
        r = classifier.classify("Now show me a chart", has_conversation_history=False)
        assert r.intent != UserIntent.FOLLOW_UP


# ─── No Data ──────────────────────────────────────────────────────────────────

class TestNoData:
    def test_no_data_conversational(self, classifier: IntentClassifier):
        r = classifier.classify("Analyze my data", has_data=False)
        assert r.mode == ExecutionMode.CONVERSATIONAL
        assert r.intent == UserIntent.GENERAL

    def test_no_data_any_message(self, classifier: IntentClassifier):
        r = classifier.classify("What is this tool?", has_data=False)
        assert r.mode == ExecutionMode.CONVERSATIONAL


# ─── Edge Cases & Confidence ──────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_message_has_result(self, classifier: IntentClassifier):
        r = classifier.classify("")
        assert isinstance(r, ClassifiedIntent)
        assert r.mode in ExecutionMode

    def test_short_message(self, classifier: IntentClassifier):
        r = classifier.classify("hi")
        assert isinstance(r, ClassifiedIntent)

    def test_confidence_above_zero(self, classifier: IntentClassifier):
        r = classifier.classify("Profile the dataset")
        assert r.confidence > 0

    def test_direct_has_tool(self, classifier: IntentClassifier):
        r = classifier.classify("Profile my data")
        assert r.direct_tool is not None

    def test_focused_has_no_direct_tool(self, classifier: IntentClassifier):
        r = classifier.classify("Write SQL to find top users")
        assert r.direct_tool is None

    def test_reasoning_populated(self, classifier: IntentClassifier):
        r = classifier.classify("Show me the correlations")
        assert len(r.reasoning) > 0

    def test_ambiguous_defaults_to_full(self, classifier: IntentClassifier):
        """When no pattern matches and no history, default to FULL."""
        r = classifier.classify("The revenue seems odd this quarter")
        assert r.mode == ExecutionMode.FULL

    def test_ambiguous_with_history_defaults_to_conversational(self, classifier: IntentClassifier):
        r = classifier.classify("The revenue seems odd this quarter", has_conversation_history=True)
        assert r.mode == ExecutionMode.CONVERSATIONAL

    def test_mixed_signals_highest_confidence_wins(self, classifier: IntentClassifier):
        """When message contains multiple signals, highest confidence should win."""
        r = classifier.classify("Profile the data and analyze everything")
        assert r.confidence >= 0.5

    def test_get_direct_params_with_datasets(self, classifier: IntentClassifier):
        intent = ClassifiedIntent(
            intent=UserIntent.PROFILE_DATA,
            mode=ExecutionMode.DIRECT,
            confidence=0.95,
            direct_tool="eda_profile",
        )
        params = classifier.get_direct_params(intent, ["sales", "customers"])
        assert params["dataset_id"] == "sales"

    def test_get_direct_params_no_datasets(self, classifier: IntentClassifier):
        intent = ClassifiedIntent(
            intent=UserIntent.PROFILE_DATA,
            mode=ExecutionMode.DIRECT,
            confidence=0.95,
            direct_tool="eda_profile",
        )
        params = classifier.get_direct_params(intent, [])
        assert params == {}


# ─── Mode-Specific LLM Cost Expectations ─────────────────────────────────────

class TestModeCosts:
    """Verify that common user requests map to the cost-appropriate mode."""

    @pytest.mark.parametrize("msg,expected_mode", [
        ("Profile my data", ExecutionMode.DIRECT),
        ("Show the schema", ExecutionMode.DIRECT),
        ("Describe the columns", ExecutionMode.DIRECT),
        ("Check data quality", ExecutionMode.DIRECT),
        ("Show correlations", ExecutionMode.DIRECT),
        ("Value counts for status", ExecutionMode.DIRECT),
        ("Validate the data", ExecutionMode.DIRECT),
        ("Write a SQL query for monthly revenue", ExecutionMode.FOCUSED),
        ("Run a t-test on the groups", ExecutionMode.FOCUSED),
        ("Make a bar chart", ExecutionMode.FOCUSED),
        ("Clean the data", ExecutionMode.FOCUSED),
        ("Run EDA", ExecutionMode.FOCUSED),
        ("Evaluate the A/B test", ExecutionMode.FOCUSED),
        ("What insights can you find?", ExecutionMode.FULL),
        ("Do a deep dive", ExecutionMode.FULL),
        ("Analyze everything", ExecutionMode.FULL),
    ])
    def test_mode_routing(self, classifier: IntentClassifier, msg: str, expected_mode: ExecutionMode):
        r = classifier.classify(msg)
        assert r.mode == expected_mode, f"'{msg}' → {r.mode.value} (expected {expected_mode.value})"
