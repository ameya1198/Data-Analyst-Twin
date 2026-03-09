"""Unit tests for the CleaningSpecialist — 6 tools covering the 8-step pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.agent.specialists.cleaning import CleaningSpecialist
from app.agent.specialists.context import AnalysisContext


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def spec() -> CleaningSpecialist:
    return CleaningSpecialist()


@pytest.fixture
def dup_df() -> pd.DataFrame:
    """DataFrame with exact and key-based duplicates."""
    return pd.DataFrame({
        "id": [1, 2, 3, 2, 4, 1],
        "name": ["Alice", "Bob", "Charlie", "Bob", "Diana", "Alice"],
        "value": [100, 200, 300, 200, 400, 100],
    })


@pytest.fixture
def ctx_dup(dup_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("dupes", dup_df, "dupes.csv")
    return ctx


@pytest.fixture
def null_df() -> pd.DataFrame:
    """DataFrame with various missing patterns."""
    np.random.seed(42)
    return pd.DataFrame({
        "fully_null": [None] * 20,
        "low_null": [1, 2, None, 4, 5] * 4,
        "moderate_null": [1, None, None, 4, 5] * 4,
        "category_null": ["A", "B", None, "A", "C"] * 4,
        "complete": list(range(20)),
    })


@pytest.fixture
def ctx_null(null_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("nulls", null_df, "nulls.csv")
    return ctx


@pytest.fixture
def derive_df() -> pd.DataFrame:
    return pd.DataFrame({
        "order_date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "amount": [100, 200, 300, 50, 400, 150, 250, 350, 75, 500],
        "description": ["Small order", "Big purchase with extras", "Regular", "Tiny", "Large order for office supplies and equipment", "Normal", "Mid", "Big", "Small", "Huge order"],
    })


@pytest.fixture
def ctx_derive(derive_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("orders", derive_df, "orders.csv")
    return ctx


# ─── clean_structural ─────────────────────────────────────────────────────────

class TestCleanStructural:

    @pytest.mark.asyncio
    async def test_column_rename(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r = await spec.execute("clean_structural", {"dataset_id": "dirty"}, ctx_dirty)
        assert r.success
        clean_df = ctx_dirty.datasets[r.data["clean_id"]]
        for col in clean_df.columns:
            assert col == col.lower()
            assert " " not in col.strip()

    @pytest.mark.asyncio
    async def test_creates_new_dataset(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r = await spec.execute("clean_structural", {"dataset_id": "dirty"}, ctx_dirty)
        assert r.success
        assert "dirty" in ctx_dirty.datasets
        assert r.data["clean_id"] in ctx_dirty.datasets

    @pytest.mark.asyncio
    async def test_preserves_row_count(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r = await spec.execute("clean_structural", {"dataset_id": "dirty"}, ctx_dirty)
        assert r.data["rows_before"] == r.data["rows_after"]

    @pytest.mark.asyncio
    async def test_changes_logged(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r = await spec.execute("clean_structural", {"dataset_id": "dirty"}, ctx_dirty)
        assert r.data["change_count"] > 0
        assert len(r.data["changes"]) > 0

    @pytest.mark.asyncio
    async def test_type_override_datetime(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r = await spec.execute("clean_structural", {
            "dataset_id": "dirty",
            "type_overrides": {"signup_date": "datetime"},
        }, ctx_dirty)
        assert r.success
        clean_df = ctx_dirty.datasets[r.data["clean_id"]]
        assert pd.api.types.is_datetime64_any_dtype(clean_df["signup_date"])

    @pytest.mark.asyncio
    async def test_type_override_bool(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r = await spec.execute("clean_structural", {
            "dataset_id": "dirty",
            "type_overrides": {"is_premium": "bool"},
        }, ctx_dirty)
        assert r.success

    @pytest.mark.asyncio
    async def test_unknown_dataset(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r = await spec.execute("clean_structural", {"dataset_id": "nope"}, ctx_dirty)
        assert not r.success
        assert "not found" in r.summary.lower()

    @pytest.mark.asyncio
    async def test_auto_date_detection(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"date_col": ["2024-01-01", "2024-02-01", "2024-03-01"] * 10, "val": range(30)})
        ctx = AnalysisContext()
        ctx.add_dataset("dates", df, "dates.csv")
        r = await spec.execute("clean_structural", {"dataset_id": "dates"}, ctx)
        assert r.success
        clean_df = ctx.datasets[r.data["clean_id"]]
        assert pd.api.types.is_datetime64_any_dtype(clean_df["date_col"])

    @pytest.mark.asyncio
    async def test_auto_numeric_detection(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"num_col": ["100", "200", "300", "400", "500"]})
        ctx = AnalysisContext()
        ctx.add_dataset("nums", df, "nums.csv")
        r = await spec.execute("clean_structural", {"dataset_id": "nums"}, ctx)
        assert r.success
        clean_df = ctx.datasets[r.data["clean_id"]]
        assert pd.api.types.is_numeric_dtype(clean_df["num_col"])


# ─── clean_deduplicate ────────────────────────────────────────────────────────

class TestCleanDeduplicate:

    @pytest.mark.asyncio
    async def test_exact_dedup_keep_first(self, spec: CleaningSpecialist, ctx_dup: AnalysisContext):
        r = await spec.execute("clean_deduplicate", {"dataset_id": "dupes"}, ctx_dup)
        assert r.success
        assert r.data["duplicates_found"] > 0
        assert r.data["duplicates_removed"] > 0
        assert r.data["rows_after"] < r.data["rows_before"]

    @pytest.mark.asyncio
    async def test_key_dedup(self, spec: CleaningSpecialist, ctx_dup: AnalysisContext):
        r = await spec.execute("clean_deduplicate", {
            "dataset_id": "dupes", "subset": ["id"],
        }, ctx_dup)
        assert r.success
        clean_df = ctx_dup.datasets[r.data["clean_id"]]
        assert clean_df["id"].is_unique

    @pytest.mark.asyncio
    async def test_keep_last(self, spec: CleaningSpecialist, ctx_dup: AnalysisContext):
        r = await spec.execute("clean_deduplicate", {
            "dataset_id": "dupes", "strategy": "keep_last",
        }, ctx_dup)
        assert r.success
        assert r.data["strategy"] == "keep_last"

    @pytest.mark.asyncio
    async def test_flag_only(self, spec: CleaningSpecialist, ctx_dup: AnalysisContext):
        r = await spec.execute("clean_deduplicate", {
            "dataset_id": "dupes", "strategy": "flag_only",
        }, ctx_dup)
        assert r.success
        clean_df = ctx_dup.datasets[r.data["clean_id"]]
        assert "is_duplicate" in clean_df.columns
        assert r.data["duplicates_removed"] == 0
        assert r.data["rows_before"] == r.data["rows_after"]

    @pytest.mark.asyncio
    async def test_keep_most_complete(self, spec: CleaningSpecialist):
        df = pd.DataFrame({
            "id": [1, 1, 2, 2],
            "name": ["Alice", None, "Bob", "Bob"],
            "value": [100, 200, None, 300],
        })
        ctx = AnalysisContext()
        ctx.add_dataset("mixed", df, "mixed.csv")
        r = await spec.execute("clean_deduplicate", {
            "dataset_id": "mixed", "subset": ["id"], "strategy": "keep_most_complete",
        }, ctx)
        assert r.success
        assert r.data["rows_after"] == 2

    @pytest.mark.asyncio
    async def test_no_duplicates(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"id": [1, 2, 3], "val": [10, 20, 30]})
        ctx = AnalysisContext()
        ctx.add_dataset("unique", df, "unique.csv")
        r = await spec.execute("clean_deduplicate", {"dataset_id": "unique"}, ctx)
        assert r.success
        assert r.data["duplicates_found"] == 0
        assert r.data["rows_before"] == r.data["rows_after"]

    @pytest.mark.asyncio
    async def test_missing_column(self, spec: CleaningSpecialist, ctx_dup: AnalysisContext):
        r = await spec.execute("clean_deduplicate", {
            "dataset_id": "dupes", "subset": ["nonexistent"],
        }, ctx_dup)
        assert not r.success


# ─── clean_missing ─────────────────────────────────────────────────────────────

class TestCleanMissing:

    @pytest.mark.asyncio
    async def test_auto_strategy(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_missing", {"dataset_id": "nulls"}, ctx_null)
        assert r.success
        assert r.data["action_count"] > 0

    @pytest.mark.asyncio
    async def test_high_null_column_dropped(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_missing", {"dataset_id": "nulls", "threshold_pct": 50}, ctx_null)
        assert r.success
        clean_df = ctx_null.datasets[r.data["clean_id"]]
        assert "fully_null" not in clean_df.columns

    @pytest.mark.asyncio
    async def test_impute_mean(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_missing", {
            "dataset_id": "nulls", "strategy": "impute_mean", "columns": ["low_null"],
        }, ctx_null)
        assert r.success
        clean_df = ctx_null.datasets[r.data["clean_id"]]
        assert clean_df["low_null"].isna().sum() == 0

    @pytest.mark.asyncio
    async def test_impute_median(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_missing", {
            "dataset_id": "nulls", "strategy": "impute_median", "columns": ["moderate_null"],
        }, ctx_null)
        assert r.success
        clean_df = ctx_null.datasets[r.data["clean_id"]]
        assert clean_df["moderate_null"].isna().sum() == 0

    @pytest.mark.asyncio
    async def test_impute_mode(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_missing", {
            "dataset_id": "nulls", "strategy": "impute_mode", "columns": ["category_null"],
        }, ctx_null)
        assert r.success
        clean_df = ctx_null.datasets[r.data["clean_id"]]
        assert clean_df["category_null"].isna().sum() == 0

    @pytest.mark.asyncio
    async def test_drop_rows(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_missing", {
            "dataset_id": "nulls", "strategy": "drop_rows", "columns": ["low_null"],
        }, ctx_null)
        assert r.success
        assert r.data["rows_after"] < r.data["rows_before"]

    @pytest.mark.asyncio
    async def test_flag_only(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_missing", {
            "dataset_id": "nulls", "strategy": "flag_only", "columns": ["low_null"],
        }, ctx_null)
        assert r.success
        clean_df = ctx_null.datasets[r.data["clean_id"]]
        assert "is_low_null_missing" in clean_df.columns

    @pytest.mark.asyncio
    async def test_forward_fill(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_missing", {
            "dataset_id": "nulls", "strategy": "forward_fill", "columns": ["low_null"],
        }, ctx_null)
        assert r.success

    @pytest.mark.asyncio
    async def test_no_nulls(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        ctx = AnalysisContext()
        ctx.add_dataset("clean", df, "clean.csv")
        r = await spec.execute("clean_missing", {"dataset_id": "clean"}, ctx)
        assert r.success
        assert r.data["action_count"] == 0

    @pytest.mark.asyncio
    async def test_actions_documented(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_missing", {"dataset_id": "nulls"}, ctx_null)
        for action in r.data["actions"]:
            assert "column" in action
            assert "null_count" in action
            assert "method" in action
            assert "result" in action


# ─── clean_standardise ────────────────────────────────────────────────────────

class TestCleanStandardise:

    @pytest.mark.asyncio
    async def test_lowercase(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r = await spec.execute("clean_standardise", {
            "dataset_id": "dirty", "operations": ["lowercase"],
        }, ctx_dirty)
        assert r.success
        clean_df = ctx_dirty.datasets[r.data["clean_id"]]
        str_cols = [c for c in clean_df.columns if pd.api.types.is_string_dtype(clean_df[c]) or clean_df[c].dtype == "object"]
        for col in str_cols:
            vals = clean_df[col].dropna().astype(str)
            assert all(v == v.lower() for v in vals), f"Column {col} not lowercased"

    @pytest.mark.asyncio
    async def test_trim_whitespace(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"name": ["  Alice  ", " Bob ", "  Charlie  "]})
        ctx = AnalysisContext()
        ctx.add_dataset("ws", df, "ws.csv")
        r = await spec.execute("clean_standardise", {
            "dataset_id": "ws", "operations": ["trim_whitespace"],
        }, ctx)
        assert r.success
        clean_df = ctx.datasets[r.data["clean_id"]]
        assert all(v == v.strip() for v in clean_df["name"].dropna())

    @pytest.mark.asyncio
    async def test_parse_dates(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"dt": ["2024-01-01", "2024-02-15", "2024-03-20"] * 5, "v": range(15)})
        ctx = AnalysisContext()
        ctx.add_dataset("dates", df, "dates.csv")
        r = await spec.execute("clean_standardise", {
            "dataset_id": "dates", "operations": ["parse_dates"],
        }, ctx)
        assert r.success
        clean_df = ctx.datasets[r.data["clean_id"]]
        assert pd.api.types.is_datetime64_any_dtype(clean_df["dt"])

    @pytest.mark.asyncio
    async def test_normalise_booleans(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"flag": ["yes", "no", "Y", "N", "true", "false"]})
        ctx = AnalysisContext()
        ctx.add_dataset("bools", df, "bools.csv")
        r = await spec.execute("clean_standardise", {
            "dataset_id": "bools", "operations": ["normalise_booleans"],
        }, ctx)
        assert r.success
        clean_df = ctx.datasets[r.data["clean_id"]]
        assert clean_df["flag"].dtype == bool

    @pytest.mark.asyncio
    async def test_strip_numeric_commas(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"revenue": ["1,000", "2,500", "10,000"]})
        ctx = AnalysisContext()
        ctx.add_dataset("commas", df, "commas.csv")
        r = await spec.execute("clean_standardise", {
            "dataset_id": "commas", "operations": ["strip_numeric_commas"],
        }, ctx)
        assert r.success
        clean_df = ctx.datasets[r.data["clean_id"]]
        assert pd.api.types.is_numeric_dtype(clean_df["revenue"])
        assert clean_df["revenue"].tolist() == [1000, 2500, 10000]

    @pytest.mark.asyncio
    async def test_category_mapping(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"country": ["UK", "U.K.", "GB", "United Kingdom", "USA"]})
        ctx = AnalysisContext()
        ctx.add_dataset("cats", df, "cats.csv")
        r = await spec.execute("clean_standardise", {
            "dataset_id": "cats",
            "operations": [],
            "category_mappings": {"country": {"UK": "United Kingdom", "U.K.": "United Kingdom", "GB": "United Kingdom"}},
        }, ctx)
        assert r.success
        clean_df = ctx.datasets[r.data["clean_id"]]
        assert clean_df["country"].value_counts()["United Kingdom"] == 4

    @pytest.mark.asyncio
    async def test_all_operations_default(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r = await spec.execute("clean_standardise", {"dataset_id": "dirty"}, ctx_dirty)
        assert r.success
        assert "lowercase" in r.data["operations_applied"]
        assert "trim_whitespace" in r.data["operations_applied"]


# ─── clean_derive ──────────────────────────────────────────────────────────────

class TestCleanDerive:

    @pytest.mark.asyncio
    async def test_date_parts(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders",
            "derivations": [{"type": "date_parts", "column": "order_date"}],
        }, ctx_derive)
        assert r.success
        clean_df = ctx_derive.datasets[r.data["clean_id"]]
        assert "order_date_year" in clean_df.columns
        assert "order_date_month" in clean_df.columns
        assert "order_date_day_of_week" in clean_df.columns
        assert "order_date_is_weekend" in clean_df.columns

    @pytest.mark.asyncio
    async def test_days_since(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders",
            "derivations": [{"type": "days_since", "column": "order_date", "params": {"reference_date": "2024-02-01"}}],
        }, ctx_derive)
        assert r.success
        clean_df = ctx_derive.datasets[r.data["clean_id"]]
        assert "days_since_order_date" in clean_df.columns
        assert clean_df["days_since_order_date"].max() > 0

    @pytest.mark.asyncio
    async def test_bin(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders",
            "derivations": [{"type": "bin", "column": "amount", "params": {"bins": 3, "labels": ["low", "mid", "high"]}}],
        }, ctx_derive)
        assert r.success
        clean_df = ctx_derive.datasets[r.data["clean_id"]]
        assert "amount_bin" in clean_df.columns

    @pytest.mark.asyncio
    async def test_flag(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders",
            "derivations": [{"type": "flag", "column": "amount", "params": {"threshold": 200, "operator": ">", "name": "is_high_value"}}],
        }, ctx_derive)
        assert r.success
        clean_df = ctx_derive.datasets[r.data["clean_id"]]
        assert "is_high_value" in clean_df.columns
        assert set(clean_df["is_high_value"].unique()).issubset({0, 1})

    @pytest.mark.asyncio
    async def test_text_features(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders",
            "derivations": [{"type": "text_features", "column": "description"}],
        }, ctx_derive)
        assert r.success
        clean_df = ctx_derive.datasets[r.data["clean_id"]]
        assert "description_word_count" in clean_df.columns
        assert "description_char_count" in clean_df.columns

    @pytest.mark.asyncio
    async def test_multiple_derivations(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders",
            "derivations": [
                {"type": "date_parts", "column": "order_date"},
                {"type": "flag", "column": "amount", "params": {"threshold": 250, "name": "is_big"}},
            ],
        }, ctx_derive)
        assert r.success
        assert r.data["new_columns"] >= 5

    @pytest.mark.asyncio
    async def test_missing_column(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders",
            "derivations": [{"type": "date_parts", "column": "nonexistent"}],
        }, ctx_derive)
        assert r.success
        assert "not found" in r.data["derivations"][0]["result"].lower()

    @pytest.mark.asyncio
    async def test_empty_derivations(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders", "derivations": [],
        }, ctx_derive)
        assert not r.success

    @pytest.mark.asyncio
    async def test_unknown_type(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders",
            "derivations": [{"type": "magic", "column": "amount"}],
        }, ctx_derive)
        assert r.success
        assert "unknown" in r.data["derivations"][0]["result"].lower()


# ─── clean_validate ────────────────────────────────────────────────────────────

class TestCleanValidate:

    @pytest.mark.asyncio
    async def test_basic_validation(self, spec: CleaningSpecialist, ctx: AnalysisContext):
        r = await spec.execute("clean_validate", {"dataset_id": "test"}, ctx)
        assert r.success
        assert r.data["total"] > 0
        assert "passed" in r.data
        assert "failed" in r.data

    @pytest.mark.asyncio
    async def test_pk_unique(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"id": [1, 2, 3], "val": [10, 20, 30]})
        ctx = AnalysisContext()
        ctx.add_dataset("pk", df, "pk.csv")
        r = await spec.execute("clean_validate", {
            "dataset_id": "pk", "primary_key": "id",
        }, ctx)
        assert r.success
        pk_check = next(c for c in r.data["checks"] if c["check"] == "pk_unique")
        assert pk_check["passed"]

    @pytest.mark.asyncio
    async def test_pk_not_unique(self, spec: CleaningSpecialist, ctx_dup: AnalysisContext):
        r = await spec.execute("clean_validate", {
            "dataset_id": "dupes", "primary_key": "id",
        }, ctx_dup)
        assert r.success
        pk_check = next(c for c in r.data["checks"] if c["check"] == "pk_unique")
        assert not pk_check["passed"]

    @pytest.mark.asyncio
    async def test_expected_row_count_pass(self, spec: CleaningSpecialist, ctx: AnalysisContext):
        r = await spec.execute("clean_validate", {
            "dataset_id": "test", "expected_row_count": 100,
        }, ctx)
        row_check = next(c for c in r.data["checks"] if c["check"] == "row_count")
        assert row_check["passed"]

    @pytest.mark.asyncio
    async def test_expected_row_count_fail(self, spec: CleaningSpecialist, ctx: AnalysisContext):
        r = await spec.execute("clean_validate", {
            "dataset_id": "test", "expected_row_count": 999,
        }, ctx)
        row_check = next(c for c in r.data["checks"] if c["check"] == "row_count")
        assert not row_check["passed"]

    @pytest.mark.asyncio
    async def test_custom_not_null(self, spec: CleaningSpecialist, ctx: AnalysisContext):
        r = await spec.execute("clean_validate", {
            "dataset_id": "test",
            "rules": [{"column": "age", "check": "not_null"}],
        }, ctx)
        custom = next(c for c in r.data["checks"] if c["check"] == "not_null")
        assert custom["passed"]

    @pytest.mark.asyncio
    async def test_custom_min_max(self, spec: CleaningSpecialist, ctx: AnalysisContext):
        r = await spec.execute("clean_validate", {
            "dataset_id": "test",
            "rules": [
                {"column": "age", "check": "min", "value": 0},
                {"column": "age", "check": "max", "value": 120},
            ],
        }, ctx)
        min_check = next(c for c in r.data["checks"] if c["check"] == "min")
        max_check = next(c for c in r.data["checks"] if c["check"] == "max")
        assert min_check["passed"]
        assert max_check["passed"]

    @pytest.mark.asyncio
    async def test_custom_in_set(self, spec: CleaningSpecialist, ctx: AnalysisContext):
        r = await spec.execute("clean_validate", {
            "dataset_id": "test",
            "rules": [{"column": "department", "check": "in_set", "value": ["Engineering", "Marketing", "Sales", "HR"]}],
        }, ctx)
        in_set_check = next(c for c in r.data["checks"] if c["check"] == "in_set")
        assert in_set_check["passed"]

    @pytest.mark.asyncio
    async def test_custom_in_set_fail(self, spec: CleaningSpecialist, ctx: AnalysisContext):
        r = await spec.execute("clean_validate", {
            "dataset_id": "test",
            "rules": [{"column": "department", "check": "in_set", "value": ["Engineering", "Marketing"]}],
        }, ctx)
        in_set_check = next(c for c in r.data["checks"] if c["check"] == "in_set")
        assert not in_set_check["passed"]

    @pytest.mark.asyncio
    async def test_null_rate_flagged(self, spec: CleaningSpecialist, ctx_null: AnalysisContext):
        r = await spec.execute("clean_validate", {"dataset_id": "nulls"}, ctx_null)
        assert r.success
        null_checks = [c for c in r.data["checks"] if c["check"] == "null_rate"]
        assert len(null_checks) > 0
        high_null = next((c for c in null_checks if "HIGH" in c.get("detail", "")), None)
        assert high_null is not None

    @pytest.mark.asyncio
    async def test_verdict_pass(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"id": [1, 2, 3], "val": [10, 20, 30]})
        ctx = AnalysisContext()
        ctx.add_dataset("ok", df, "ok.csv")
        r = await spec.execute("clean_validate", {"dataset_id": "ok", "primary_key": "id"}, ctx)
        assert r.data["verdict"] == "PASS"

    @pytest.mark.asyncio
    async def test_column_not_found_rule(self, spec: CleaningSpecialist, ctx: AnalysisContext):
        r = await spec.execute("clean_validate", {
            "dataset_id": "test",
            "rules": [{"column": "nonexistent", "check": "not_null"}],
        }, ctx)
        custom = next(c for c in r.data["checks"] if c["column"] == "nonexistent")
        assert not custom["passed"]

    @pytest.mark.asyncio
    async def test_no_future_dates(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"dt": pd.to_datetime(["2024-01-01", "2024-06-01", "2024-12-01"]), "val": [1, 2, 3]})
        ctx = AnalysisContext()
        ctx.add_dataset("d", df, "d.csv")
        r = await spec.execute("clean_validate", {
            "dataset_id": "d",
            "rules": [{"column": "dt", "check": "no_future_dates"}],
        }, ctx)
        assert r.success
        check = next(c for c in r.data["checks"] if c["check"] == "no_future_dates")
        assert check["passed"]


# ─── Edge Cases ────────────────────────────────────────────────────────────────

class TestCleaningEdgeCases:

    @pytest.mark.asyncio
    async def test_unknown_tool(self, spec: CleaningSpecialist, ctx: AnalysisContext):
        r = await spec.execute("clean_magic", {}, ctx)
        assert not r.success
        assert "unknown" in r.summary.lower()

    @pytest.mark.asyncio
    async def test_pipeline_stage_labels(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        r1 = await spec.execute("clean_structural", {"dataset_id": "dirty"}, ctx_dirty)
        assert "Stage 2" in r1.summary

    @pytest.mark.asyncio
    async def test_full_pipeline(self, spec: CleaningSpecialist, ctx_dirty: AnalysisContext):
        """Run the full 6-tool pipeline in order."""
        # Stage 2: Structural
        r1 = await spec.execute("clean_structural", {"dataset_id": "dirty"}, ctx_dirty)
        assert r1.success
        sid = r1.data["clean_id"]

        # Stage 3: Dedup
        r2 = await spec.execute("clean_deduplicate", {"dataset_id": sid}, ctx_dirty)
        assert r2.success
        sid = r2.data["clean_id"]

        # Stage 4: Missing
        r3 = await spec.execute("clean_missing", {"dataset_id": sid}, ctx_dirty)
        assert r3.success
        sid = r3.data["clean_id"]

        # Stage 6: Standardise
        r4 = await spec.execute("clean_standardise", {"dataset_id": sid}, ctx_dirty)
        assert r4.success
        sid = r4.data["clean_id"]

        # Stage 8: Validate
        r5 = await spec.execute("clean_validate", {"dataset_id": sid}, ctx_dirty)
        assert r5.success
        assert r5.data["total"] > 0

    @pytest.mark.asyncio
    async def test_empty_dataset_structural(self, spec: CleaningSpecialist, ctx_empty: AnalysisContext):
        r = await spec.execute("clean_structural", {"dataset_id": "empty"}, ctx_empty)
        assert r.success
        assert r.data["rows_before"] == 0

    @pytest.mark.asyncio
    async def test_single_row_dedup(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"id": [1], "val": [42]})
        ctx = AnalysisContext()
        ctx.add_dataset("one", df, "one.csv")
        r = await spec.execute("clean_deduplicate", {"dataset_id": "one"}, ctx)
        assert r.success
        assert r.data["duplicates_found"] == 0

    @pytest.mark.asyncio
    async def test_all_null_column_missing(self, spec: CleaningSpecialist):
        df = pd.DataFrame({"a": [None, None, None], "b": [1, 2, 3]})
        ctx = AnalysisContext()
        ctx.add_dataset("allnull", df, "allnull.csv")
        r = await spec.execute("clean_missing", {"dataset_id": "allnull", "threshold_pct": 50}, ctx)
        assert r.success
        clean_df = ctx.datasets[r.data["clean_id"]]
        assert "a" not in clean_df.columns

    @pytest.mark.asyncio
    async def test_derive_creates_new_dataset(self, spec: CleaningSpecialist, ctx_derive: AnalysisContext):
        r = await spec.execute("clean_derive", {
            "dataset_id": "orders",
            "derivations": [{"type": "flag", "column": "amount", "params": {"threshold": 100}}],
        }, ctx_derive)
        assert "orders" in ctx_derive.datasets
        assert r.data["clean_id"] in ctx_derive.datasets
        assert r.data["clean_id"] != "orders"
