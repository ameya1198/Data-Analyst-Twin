"""Unit tests for the Statistical Analysis Specialist."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.agent.specialists.stats import StatsSpecialist
from app.agent.specialists.context import AnalysisContext


# ─── stats_test ───────────────────────────────────────────────────────────────

class TestStatsTest:

    @pytest.mark.asyncio
    async def test_two_group_ttest(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_test", {
            "dataset_id": "test",
            "column": "salary",
            "group_column": "is_manager",
        }, ctx)
        assert r.success
        assert r.data["test_name"] in ("Welch's t-test", "Mann-Whitney U")
        assert "p_value" in r.data
        assert "effect_size" in r.data
        assert r.data["alpha"] == 0.05

    @pytest.mark.asyncio
    async def test_one_sample_ttest(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_test", {
            "dataset_id": "test",
            "column": "salary",
            "population_mean": 70000,
        }, ctx)
        assert r.success
        assert "t-test" in r.data["test_name"].lower()
        assert r.data["ci_lower"] is not None
        assert r.data["ci_upper"] is not None

    @pytest.mark.asyncio
    async def test_anova_multiple_groups(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_test", {
            "dataset_id": "test",
            "column": "salary",
            "group_column": "department",
        }, ctx)
        assert r.success
        assert "ANOVA" in r.data["test_name"] or "Kruskal" in r.data["test_name"]
        assert r.data["effect_metric"] == "eta_squared"

    @pytest.mark.asyncio
    async def test_returns_all_three(self, stats: StatsSpecialist, ctx: AnalysisContext):
        """Verify the three required outputs: p-value, effect size, CI."""
        r = await stats.execute("stats_test", {
            "dataset_id": "test",
            "column": "salary",
            "group_column": "is_manager",
        }, ctx)
        assert r.success
        assert r.data["p_value"] is not None
        assert r.data["effect_size"] is not None
        assert r.data["effect_label"] is not None

    @pytest.mark.asyncio
    async def test_assumptions_included(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_test", {
            "dataset_id": "test",
            "column": "salary",
            "group_column": "is_manager",
        }, ctx)
        assert r.success
        assert "assumptions" in r.data
        assert "normality" in r.data["assumptions"]

    @pytest.mark.asyncio
    async def test_custom_alpha(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_test", {
            "dataset_id": "test",
            "column": "salary",
            "population_mean": 75000,
            "alpha": 0.01,
        }, ctx)
        assert r.success
        assert r.data["alpha"] == 0.01

    @pytest.mark.asyncio
    async def test_caveats_included(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_test", {
            "dataset_id": "test",
            "column": "salary",
            "population_mean": 75000,
        }, ctx)
        assert r.success
        assert len(r.data["caveats"]) >= 3

    @pytest.mark.asyncio
    async def test_dataset_not_found(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_test", {
            "dataset_id": "nonexistent",
            "column": "salary",
        }, ctx)
        assert not r.success

    @pytest.mark.asyncio
    async def test_column_not_found(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_test", {
            "dataset_id": "test",
            "column": "nonexistent",
        }, ctx)
        assert not r.success


# ─── stats_regression ─────────────────────────────────────────────────────────

class TestStatsRegression:

    @pytest.mark.asyncio
    async def test_linear_regression(self, stats: StatsSpecialist, ctx_regression: AnalysisContext):
        r = await stats.execute("stats_regression", {
            "dataset_id": "reg_data",
            "target": "y",
            "predictors": ["x1", "x2"],
        }, ctx_regression)
        assert r.success
        assert r.data["regression_type"] == "linear"
        assert r.data["r_squared"] > 0.5
        assert len(r.data["coefficients"]) == 3  # const + x1 + x2

    @pytest.mark.asyncio
    async def test_linear_regression_has_vif(self, stats: StatsSpecialist, ctx_regression: AnalysisContext):
        r = await stats.execute("stats_regression", {
            "dataset_id": "reg_data",
            "target": "y",
            "predictors": ["x1", "x2"],
        }, ctx_regression)
        assert r.success
        assert "vif" in r.data
        assert len(r.data["vif"]) == 2

    @pytest.mark.asyncio
    async def test_linear_residual_normality(self, stats: StatsSpecialist, ctx_regression: AnalysisContext):
        r = await stats.execute("stats_regression", {
            "dataset_id": "reg_data",
            "target": "y",
            "predictors": ["x1", "x2"],
        }, ctx_regression)
        assert r.success
        assert "residual_normality" in r.data

    @pytest.mark.asyncio
    async def test_logistic_regression(self, stats: StatsSpecialist, ctx_regression: AnalysisContext):
        r = await stats.execute("stats_regression", {
            "dataset_id": "reg_data",
            "target": "binary_target",
            "predictors": ["x1", "x2"],
        }, ctx_regression)
        assert r.success
        assert r.data["regression_type"] == "logistic"
        assert "auc" in r.data
        assert "confusion_matrix" in r.data
        assert r.data["auc"] > 0.5

    @pytest.mark.asyncio
    async def test_logistic_has_odds_ratios(self, stats: StatsSpecialist, ctx_regression: AnalysisContext):
        r = await stats.execute("stats_regression", {
            "dataset_id": "reg_data",
            "target": "binary_target",
            "predictors": ["x1", "x2"],
        }, ctx_regression)
        assert r.success
        for coef in r.data["coefficients"]:
            assert "odds_ratio" in coef

    @pytest.mark.asyncio
    async def test_auto_detect_predictors(self, stats: StatsSpecialist, ctx_regression: AnalysisContext):
        r = await stats.execute("stats_regression", {
            "dataset_id": "reg_data",
            "target": "y",
        }, ctx_regression)
        assert r.success
        assert r.data["n_predictors"] >= 2

    @pytest.mark.asyncio
    async def test_column_not_found(self, stats: StatsSpecialist, ctx_regression: AnalysisContext):
        r = await stats.execute("stats_regression", {
            "dataset_id": "reg_data",
            "target": "nonexistent",
        }, ctx_regression)
        assert not r.success


# ─── stats_ab_test ────────────────────────────────────────────────────────────

class TestStatsABTest:

    @pytest.mark.asyncio
    async def test_basic_ab_test(self, stats: StatsSpecialist, ctx_ab: AnalysisContext):
        r = await stats.execute("stats_ab_test", {
            "dataset_id": "ab_data",
            "group_column": "variant",
            "metric_column": "converted",
        }, ctx_ab)
        assert r.success
        assert "p_value" in r.data
        assert "cohens_d" in r.data
        assert "ci_lower" in r.data
        assert "ci_upper" in r.data
        assert "relative_uplift_pct" in r.data

    @pytest.mark.asyncio
    async def test_ab_test_srm_check(self, stats: StatsSpecialist, ctx_ab: AnalysisContext):
        r = await stats.execute("stats_ab_test", {
            "dataset_id": "ab_data",
            "group_column": "variant",
            "metric_column": "converted",
        }, ctx_ab)
        assert r.success
        assert "srm_check" in r.data
        assert "ok" in r.data["srm_check"]

    @pytest.mark.asyncio
    async def test_ab_test_with_mde(self, stats: StatsSpecialist, ctx_ab: AnalysisContext):
        r = await stats.execute("stats_ab_test", {
            "dataset_id": "ab_data",
            "group_column": "variant",
            "metric_column": "converted",
            "mde": 0.5,
        }, ctx_ab)
        assert r.success
        assert "practical_significance" in r.data

    @pytest.mark.asyncio
    async def test_ab_test_explicit_labels(self, stats: StatsSpecialist, ctx_ab: AnalysisContext):
        r = await stats.execute("stats_ab_test", {
            "dataset_id": "ab_data",
            "group_column": "variant",
            "metric_column": "revenue",
            "control_label": "control",
            "treatment_label": "treatment",
        }, ctx_ab)
        assert r.success
        assert r.data["control"]["label"] == "control"
        assert r.data["treatment"]["label"] == "treatment"

    @pytest.mark.asyncio
    async def test_ab_test_insufficient_groups(self, stats: StatsSpecialist):
        ctx = AnalysisContext()
        df = pd.DataFrame({"variant": ["A"] * 10, "metric": [1] * 10})
        ctx.add_dataset("bad_ab", df, "bad.csv")
        r = await stats.execute("stats_ab_test", {
            "dataset_id": "bad_ab",
            "group_column": "variant",
            "metric_column": "metric",
        }, ctx)
        assert not r.success

    @pytest.mark.asyncio
    async def test_ab_test_group_stats(self, stats: StatsSpecialist, ctx_ab: AnalysisContext):
        r = await stats.execute("stats_ab_test", {
            "dataset_id": "ab_data",
            "group_column": "variant",
            "metric_column": "converted",
        }, ctx_ab)
        assert r.success
        for key in ("n", "mean", "std"):
            assert key in r.data["control"]
            assert key in r.data["treatment"]


# ─── stats_power ──────────────────────────────────────────────────────────────

class TestStatsPower:

    @pytest.mark.asyncio
    async def test_sample_size_calculation(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_power", {
            "effect_size": 0.5,
            "alpha": 0.05,
            "power": 0.80,
        }, ctx)
        assert r.success
        assert r.data["mode"] == "calculate_sample_size"
        assert r.data["n_per_group"] > 50

    @pytest.mark.asyncio
    async def test_power_calculation(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_power", {
            "effect_size": 0.5,
            "n_per_group": 64,
        }, ctx)
        assert r.success
        assert r.data["mode"] == "calculate_power"
        assert r.data["achieved_power"] > 0.5

    @pytest.mark.asyncio
    async def test_small_effect_needs_more(self, stats: StatsSpecialist, ctx: AnalysisContext):
        small = await stats.execute("stats_power", {"effect_size": 0.2}, ctx)
        medium = await stats.execute("stats_power", {"effect_size": 0.5}, ctx)
        assert small.success and medium.success
        assert small.data["n_per_group"] > medium.data["n_per_group"]

    @pytest.mark.asyncio
    async def test_baseline_rate_proportions(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_power", {
            "effect_size": 0.02,
            "baseline_rate": 0.10,
        }, ctx)
        assert r.success
        assert r.data["test_type"] == "proportions"
        assert "baseline_rate" in r.data

    @pytest.mark.asyncio
    async def test_invalid_effect_size(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_power", {"effect_size": 0}, ctx)
        assert not r.success

    @pytest.mark.asyncio
    async def test_defaults(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_power", {}, ctx)
        assert r.success
        assert r.data["effect_size"] == 0.5
        assert r.data["alpha"] == 0.05


# ─── stats_assumptions ────────────────────────────────────────────────────────

class TestStatsAssumptions:

    @pytest.mark.asyncio
    async def test_normality_check(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_assumptions", {
            "dataset_id": "test",
            "columns": ["salary"],
        }, ctx)
        assert r.success
        assert "salary" in r.data["results"]
        norm = r.data["results"]["salary"]["normality"]
        assert "is_normal" in norm
        assert "test" in norm

    @pytest.mark.asyncio
    async def test_all_numeric_columns_default(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_assumptions", {"dataset_id": "test"}, ctx)
        assert r.success
        assert len(r.data["columns_checked"]) >= 3

    @pytest.mark.asyncio
    async def test_equal_variance_with_group(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_assumptions", {
            "dataset_id": "test",
            "columns": ["salary"],
            "group_column": "is_manager",
        }, ctx)
        assert r.success
        sal_result = r.data["results"]["salary"]
        assert "equal_variance" in sal_result
        assert "levene_statistic" in sal_result["equal_variance"]

    @pytest.mark.asyncio
    async def test_transformation_suggested_for_skewed(self, stats: StatsSpecialist):
        np.random.seed(42)
        ctx = AnalysisContext()
        df = pd.DataFrame({"skewed": np.random.lognormal(10, 2, 200)})
        ctx.add_dataset("sk", df, "skewed.csv")
        r = await stats.execute("stats_assumptions", {
            "dataset_id": "sk",
            "columns": ["skewed"],
        }, ctx)
        assert r.success
        sk_result = r.data["results"]["skewed"]
        assert not sk_result["normality"]["is_normal"]
        assert "suggested_transformation" in sk_result

    @pytest.mark.asyncio
    async def test_recommended_test_included(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_assumptions", {
            "dataset_id": "test",
            "columns": ["salary"],
        }, ctx)
        assert r.success
        assert "recommended_test" in r.data["results"]["salary"]

    @pytest.mark.asyncio
    async def test_column_not_found(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_assumptions", {
            "dataset_id": "test",
            "columns": ["nonexistent"],
        }, ctx)
        assert not r.success


# ─── Edge Cases & Integration ─────────────────────────────────────────────────

class TestStatsEdgeCases:

    @pytest.mark.asyncio
    async def test_unknown_tool_name(self, stats: StatsSpecialist, ctx: AnalysisContext):
        r = await stats.execute("stats_nonexistent", {}, ctx)
        assert not r.success

    @pytest.mark.asyncio
    async def test_specialist_metadata(self, stats: StatsSpecialist):
        assert stats.name == "stats"
        assert stats.mode.value == "tool"
        assert len(stats.get_tools()) == 5
        tool_names = stats.get_tool_names()
        assert "stats_test" in tool_names
        assert "stats_regression" in tool_names
        assert "stats_ab_test" in tool_names
        assert "stats_power" in tool_names
        assert "stats_assumptions" in tool_names

    @pytest.mark.asyncio
    async def test_small_sample_uses_nonparametric(self, stats: StatsSpecialist):
        np.random.seed(42)
        ctx = AnalysisContext()
        df = pd.DataFrame({
            "value": np.random.exponential(10, 20),
            "group": ["A"] * 10 + ["B"] * 10,
        })
        ctx.add_dataset("small", df, "small.csv")
        r = await stats.execute("stats_test", {
            "dataset_id": "small",
            "column": "value",
            "group_column": "group",
        }, ctx)
        assert r.success

    @pytest.mark.asyncio
    async def test_regression_insufficient_data(self, stats: StatsSpecialist):
        ctx = AnalysisContext()
        df = pd.DataFrame({"x": [1.0], "y": [2.0]})
        ctx.add_dataset("tiny", df, "tiny.csv")
        r = await stats.execute("stats_regression", {
            "dataset_id": "tiny",
            "target": "y",
            "predictors": ["x"],
        }, ctx)
        assert not r.success

    @pytest.mark.asyncio
    async def test_ab_test_column_not_found(self, stats: StatsSpecialist, ctx_ab: AnalysisContext):
        r = await stats.execute("stats_ab_test", {
            "dataset_id": "ab_data",
            "group_column": "nonexistent",
            "metric_column": "converted",
        }, ctx_ab)
        assert not r.success
