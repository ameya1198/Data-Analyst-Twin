"""Tests for the EDA specialist — all 6 tools + edge cases."""

import numpy as np
import pandas as pd
import pytest

from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.eda import EDASpecialist


@pytest.fixture
def eda():
    return EDASpecialist()


# ─── eda_profile ──────────────────────────────────────────────────────────────

class TestEDAProfile:
    async def test_basic_profile(self, eda, ctx):
        r = await eda.execute("eda_profile", {"dataset_id": "test"}, ctx)
        assert r.success
        assert r.data["rows"] == 100
        assert r.data["columns"] == 6
        assert 0 <= r.data["quality_score"] <= 100
        assert "Phase 1" in r.data["workflow_phase"]

    async def test_profile_empty_dataset(self, eda, ctx_empty):
        r = await eda.execute("eda_profile", {"dataset_id": "empty"}, ctx_empty)
        assert r.success
        assert r.data["rows"] == 0
        assert r.data["columns"] == 0

    async def test_profile_nonexistent_dataset(self, eda, ctx):
        r = await eda.execute("eda_profile", {"dataset_id": "nope"}, ctx)
        assert not r.success
        assert "not found" in r.error.lower() or "not found" in r.summary.lower()

    async def test_profile_large_dataset_sampling_note(self, eda, large_df):
        ctx = AnalysisContext()
        ctx.add_dataset("big", large_df, "big.csv")
        r = await eda.execute("eda_profile", {"dataset_id": "big"}, ctx)
        assert r.success
        assert "Large dataset" in r.data["sampling_note"]

    async def test_profile_has_duplicate_pct(self, eda, ctx):
        r = await eda.execute("eda_profile", {"dataset_id": "test"}, ctx)
        assert "duplicate_pct" in r.data

    async def test_profile_recommended_next(self, eda, ctx):
        r = await eda.execute("eda_profile", {"dataset_id": "test"}, ctx)
        assert "Phase 2" in r.data["recommended_next"] or "Preparation" in r.data["recommended_next"]

    async def test_profile_column_types(self, eda, ctx):
        r = await eda.execute("eda_profile", {"dataset_id": "test"}, ctx)
        types = [cp["inferred_type"] for cp in r.data["column_profiles"]]
        assert "numeric" in types
        assert "categorical" in types


# ─── eda_describe ─────────────────────────────────────────────────────────────

class TestEDADescribe:
    async def test_describe_numeric(self, eda, ctx):
        r = await eda.execute("eda_describe", {"dataset_id": "test", "columns": ["salary"]}, ctx)
        assert r.success
        desc = r.data["descriptions"]["salary"]
        assert "mean" in desc
        assert "median" in desc
        assert "skewness" in desc
        assert "skewness_label" in desc
        assert "skewness_action" in desc
        assert "kurtosis" in desc
        assert isinstance(desc["heavy_tailed"], bool)

    async def test_describe_has_outlier_info(self, eda, ctx):
        r = await eda.execute("eda_describe", {"dataset_id": "test", "columns": ["salary"]}, ctx)
        desc = r.data["descriptions"]["salary"]
        assert "outliers" in desc
        assert "mild" in desc["outliers"]
        assert "extreme" in desc["outliers"]
        assert "assessment" in desc["outliers"]

    async def test_describe_categorical(self, eda, ctx):
        r = await eda.execute("eda_describe", {"dataset_id": "test", "columns": ["department"]}, ctx)
        desc = r.data["descriptions"]["department"]
        assert desc["type"] == "categorical"
        assert "top_values" in desc

    async def test_describe_all_columns(self, eda, ctx):
        r = await eda.execute("eda_describe", {"dataset_id": "test"}, ctx)
        assert r.success
        assert len(r.data["descriptions"]) == 6

    async def test_describe_nonexistent_column(self, eda, ctx):
        r = await eda.execute("eda_describe", {"dataset_id": "test", "columns": ["nonexistent"]}, ctx)
        assert not r.success

    async def test_describe_skewed_data(self, eda, skewed_df):
        ctx = AnalysisContext()
        ctx.add_dataset("sk", skewed_df, "skewed.csv")
        r = await eda.execute("eda_describe", {"dataset_id": "sk", "columns": ["income"]}, ctx)
        desc = r.data["descriptions"]["income"]
        assert "significantly" in desc["skewness_label"]

    async def test_describe_workflow_phase(self, eda, ctx):
        r = await eda.execute("eda_describe", {"dataset_id": "test", "columns": ["salary"]}, ctx)
        assert "Phase 2" in r.data["workflow_phase"]


# ─── eda_correlations ─────────────────────────────────────────────────────────

class TestEDACorrelations:
    async def test_basic_correlations(self, eda, ctx):
        r = await eda.execute("eda_correlations", {"dataset_id": "test"}, ctx)
        assert r.success
        assert "matrix" in r.data
        assert "Phase 3" in r.data["workflow_phase"]

    async def test_correlation_strength_labels(self, eda):
        np.random.seed(42)
        x = np.arange(100).astype(float)
        df = pd.DataFrame({"x": x, "y": x * 2 + np.random.normal(0, 5, 100)})
        ctx = AnalysisContext()
        ctx.add_dataset("corr", df, "corr.csv")
        r = await eda.execute("eda_correlations", {"dataset_id": "corr"}, ctx)
        assert r.success
        pairs = r.data["all_notable_pairs"]
        assert len(pairs) >= 1
        assert pairs[0]["strength"] in ("strong", "very strong")

    async def test_multicollinearity_warning(self, eda):
        x = np.arange(100).astype(float)
        df = pd.DataFrame({"x": x, "y": x + np.random.normal(0, 0.1, 100)})
        ctx = AnalysisContext()
        ctx.add_dataset("mc", df, "mc.csv")
        r = await eda.execute("eda_correlations", {"dataset_id": "mc"}, ctx)
        assert any("ulticollinearity" in d for d in r.data["diagnostics"])

    async def test_spearman_method(self, eda, ctx):
        r = await eda.execute("eda_correlations", {"dataset_id": "test", "method": "spearman"}, ctx)
        assert r.success
        assert r.data["method"] == "spearman"

    async def test_single_numeric_column_fails(self, eda):
        df = pd.DataFrame({"x": [1, 2, 3], "cat": ["a", "b", "c"]})
        ctx = AnalysisContext()
        ctx.add_dataset("one", df, "one.csv")
        r = await eda.execute("eda_correlations", {"dataset_id": "one"}, ctx)
        assert not r.success

    async def test_causation_reminder(self, eda, ctx):
        r = await eda.execute("eda_correlations", {"dataset_id": "test"}, ctx)
        assert any("causation" in d.lower() for d in r.data["diagnostics"])


# ─── eda_value_counts ─────────────────────────────────────────────────────────

class TestEDAValueCounts:
    async def test_basic_value_counts(self, eda, ctx):
        r = await eda.execute("eda_value_counts", {"dataset_id": "test", "column": "department"}, ctx)
        assert r.success
        assert r.data["unique_count"] == 4
        assert "Phase 2" in r.data["workflow_phase"]

    async def test_imbalanced_detection(self, eda):
        df = pd.DataFrame({"status": ["active"] * 95 + ["inactive"] * 5})
        ctx = AnalysisContext()
        ctx.add_dataset("imb", df, "imb.csv")
        r = await eda.execute("eda_value_counts", {"dataset_id": "imb", "column": "status"}, ctx)
        assert any("imbalanced" in d.lower() for d in r.data["diagnostics"])

    async def test_binary_column_detection(self, eda):
        df = pd.DataFrame({"flag": ["yes", "no"] * 50})
        ctx = AnalysisContext()
        ctx.add_dataset("bin", df, "bin.csv")
        r = await eda.execute("eda_value_counts", {"dataset_id": "bin", "column": "flag"}, ctx)
        assert any("binary" in d.lower() for d in r.data["diagnostics"])

    async def test_nonexistent_column(self, eda, ctx):
        r = await eda.execute("eda_value_counts", {"dataset_id": "test", "column": "nope"}, ctx)
        assert not r.success

    async def test_rare_category_detection(self, eda):
        cats = ["common"] * 980 + ["rare_a"] * 5 + ["rare_b"] * 5 + ["medium"] * 10
        df = pd.DataFrame({"cat": cats})
        ctx = AnalysisContext()
        ctx.add_dataset("rare", df, "rare.csv")
        r = await eda.execute("eda_value_counts", {"dataset_id": "rare", "column": "cat"}, ctx)
        assert any("rare" in d.lower() for d in r.data["diagnostics"])


# ─── eda_data_quality ─────────────────────────────────────────────────────────

class TestEDADataQuality:
    async def test_clean_data_quality(self, eda, ctx):
        r = await eda.execute("eda_data_quality", {"dataset_id": "test"}, ctx)
        assert r.success
        assert r.data["quality_score"] >= 80
        assert "Phase 1" in r.data["workflow_phase"]

    async def test_messy_data_issues_detected(self, eda, ctx_messy):
        r = await eda.execute("eda_data_quality", {"dataset_id": "messy"}, ctx_messy)
        assert r.success
        assert r.data["total_issues"] > 0

    async def test_missingness_classification(self, eda, ctx_messy):
        r = await eda.execute("eda_data_quality", {"dataset_id": "messy"}, ctx_messy)
        assert "missingness_classifications" in r.data
        classifications = r.data["missingness_classifications"]
        assert len(classifications) > 0
        for col, info in classifications.items():
            assert "type" in info
            assert "treatment" in info

    async def test_all_null_column_classified(self, eda):
        df = pd.DataFrame({"good": [1, 2, 3], "bad": [None, None, None]})
        ctx = AnalysisContext()
        ctx.add_dataset("nulls", df, "nulls.csv")
        r = await eda.execute("eda_data_quality", {"dataset_id": "nulls"}, ctx)
        assert "bad" in r.data["missingness_classifications"]
        assert r.data["missingness_classifications"]["bad"]["type"] == "consider_drop"

    async def test_severity_counts(self, eda, ctx_messy):
        r = await eda.execute("eda_data_quality", {"dataset_id": "messy"}, ctx_messy)
        assert "severity_counts" in r.data
        for sev in ("high", "medium", "low"):
            assert sev in r.data["severity_counts"]


# ─── eda_smart_structure ──────────────────────────────────────────────────────

class TestEDASmartStructure:
    async def test_structures_messy_data(self, eda, ctx_messy):
        r = await eda.execute("eda_smart_structure", {"dataset_id": "messy"}, ctx_messy)
        assert r.success
        assert r.data["change_count"] > 0
        assert "Data Preparation" in r.data["workflow_phase"]
        assert "changes" in r.data

    async def test_quality_scores_present(self, eda, ctx_messy):
        r = await eda.execute("eda_smart_structure", {"dataset_id": "messy"}, ctx_messy)
        assert "quality_score_before" in r.data
        assert "quality_score_after" in r.data
        assert isinstance(r.data["quality_score_after"], int)

    async def test_clean_data_minimal_changes(self, eda, ctx):
        r = await eda.execute("eda_smart_structure", {"dataset_id": "test"}, ctx)
        assert r.success

    async def test_creates_new_dataset(self, eda, ctx_messy):
        r = await eda.execute("eda_smart_structure", {"dataset_id": "messy"}, ctx_messy)
        new_id = r.data["clean_dataset_id"]
        assert new_id in ctx_messy.datasets


# ─── Tool metadata ────────────────────────────────────────────────────────────

class TestEDAToolMetadata:
    def test_tool_count(self, eda):
        tools = eda.get_tools()
        assert len(tools) == 6

    def test_tool_names(self, eda):
        names = eda.get_tool_names()
        assert set(names) == {"eda_profile", "eda_describe", "eda_correlations",
                              "eda_value_counts", "eda_data_quality", "eda_smart_structure"}

    def test_tool_descriptions_have_phase_tags(self, eda):
        for tool in eda.get_tools():
            assert "[Phase" in tool["description"] or "[Data" in tool["description"]

    def test_system_prompt_references_tukey(self, eda):
        assert "Tukey" in eda.system_prompt or "tukey" in eda.system_prompt.lower()
