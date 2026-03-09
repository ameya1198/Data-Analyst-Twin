"""Shared fixtures for the test suite."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.base import SpecialistRegistry
from app.agent.specialists.cleaning import CleaningSpecialist
from app.agent.specialists.eda import EDASpecialist
from app.agent.specialists.sql import SQLSpecialist
from app.agent.specialists.stats import StatsSpecialist
from app.agent.specialists.viz import VizSpecialist
from app.agent.error_recovery import ErrorRecoveryMiddleware


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """A well-structured numeric + categorical dataset for most tests."""
    np.random.seed(42)
    n = 100
    return pd.DataFrame({
        "age": np.random.randint(20, 65, n),
        "salary": np.random.normal(75000, 15000, n).round(2),
        "department": np.random.choice(["Engineering", "Marketing", "Sales", "HR"], n),
        "performance": np.random.normal(4.0, 0.5, n).round(2),
        "tenure_years": np.random.randint(0, 20, n),
        "is_manager": np.random.choice([True, False], n),
    })


@pytest.fixture
def messy_df() -> pd.DataFrame:
    """A dataset with quality issues: nulls, mixed types, messy headers."""
    return pd.DataFrame({
        " Name ": ["Alice", "Bob", None, "Diana", "Eve"] * 10,
        "AGE": ["25", "30", "N/A", "35", "28"] * 10,
        "salary": [50000, None, 70000, "80k", 60000] * 10,
        "Notes": ["Senior engineer with Python"] * 50,
        "start_date": ["2020-01-15", "2019-06-01", "invalid", "2021-03-10", "2018-12-01"] * 10,
    })


@pytest.fixture
def empty_df() -> pd.DataFrame:
    return pd.DataFrame()


@pytest.fixture
def large_df() -> pd.DataFrame:
    np.random.seed(42)
    return pd.DataFrame({
        "x": np.random.normal(0, 1, 150_000),
        "y": np.random.normal(0, 1, 150_000),
    })


@pytest.fixture
def skewed_df() -> pd.DataFrame:
    """Right-skewed data for distribution analysis tests."""
    np.random.seed(42)
    return pd.DataFrame({
        "income": np.random.lognormal(10, 1, 200),
        "normal_col": np.random.normal(50, 10, 200),
    })


@pytest.fixture
def ctx(sample_df: pd.DataFrame) -> AnalysisContext:
    """Context with a sample dataset pre-loaded."""
    ctx = AnalysisContext()
    ctx.add_dataset("test", sample_df, "test_data.csv")
    return ctx


@pytest.fixture
def ctx_messy(messy_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("messy", messy_df, "messy_data.csv")
    return ctx


@pytest.fixture
def ctx_empty(empty_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("empty", empty_df, "empty.csv")
    return ctx


@pytest.fixture
def orders_df() -> pd.DataFrame:
    """E-commerce orders dataset for SQL specialist tests."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=180, freq="D")
    return pd.DataFrame({
        "order_id": range(1, n + 1),
        "user_id": np.random.randint(1, 51, n),
        "order_date": np.random.choice(dates, n),
        "amount": np.random.uniform(10, 500, n).round(2),
        "status": np.random.choice(["completed", "pending", "refund"], n, p=[0.7, 0.2, 0.1]),
        "product_category": np.random.choice(["Electronics", "Clothing", "Books", "Home"], n),
    })


@pytest.fixture
def ctx_orders(orders_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("orders", orders_df, "orders.csv")
    return ctx


@pytest.fixture
def ctx_multi(sample_df: pd.DataFrame, orders_df: pd.DataFrame) -> AnalysisContext:
    """Context with two datasets for cross-table SQL queries."""
    ctx = AnalysisContext()
    ctx.add_dataset("employees", sample_df, "employees.csv")
    ctx.add_dataset("orders", orders_df, "orders.csv")
    return ctx


@pytest.fixture
def eda() -> EDASpecialist:
    return EDASpecialist()


@pytest.fixture
def sql() -> SQLSpecialist:
    return SQLSpecialist()


@pytest.fixture
def stats() -> StatsSpecialist:
    return StatsSpecialist()


@pytest.fixture
def viz() -> VizSpecialist:
    return VizSpecialist()


@pytest.fixture
def ab_test_df() -> pd.DataFrame:
    """A/B test dataset with control and treatment groups."""
    np.random.seed(42)
    n = 500
    group = np.random.choice(["control", "treatment"], n)
    converted = np.where(
        group == "treatment",
        np.random.binomial(1, 0.15, n),
        np.random.binomial(1, 0.10, n),
    )
    revenue = np.where(converted, np.random.normal(50, 15, n), 0).round(2)
    return pd.DataFrame({"variant": group, "converted": converted, "revenue": revenue})


@pytest.fixture
def ctx_ab(ab_test_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("ab_data", ab_test_df, "ab_test.csv")
    return ctx


@pytest.fixture
def regression_df() -> pd.DataFrame:
    """Dataset for regression tests with known relationships."""
    np.random.seed(42)
    n = 200
    x1 = np.random.normal(50, 10, n)
    x2 = np.random.normal(30, 5, n)
    noise = np.random.normal(0, 5, n)
    y = 10 + 2 * x1 + 0.5 * x2 + noise
    binary_y = (y > np.median(y)).astype(int)
    return pd.DataFrame({"x1": x1, "x2": x2, "y": y.round(2), "binary_target": binary_y})


@pytest.fixture
def ctx_regression(regression_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("reg_data", regression_df, "regression.csv")
    return ctx


@pytest.fixture
def cleaning() -> CleaningSpecialist:
    return CleaningSpecialist()


@pytest.fixture
def dirty_df() -> pd.DataFrame:
    """Dataset with multiple cleaning issues: bad headers, dupes, missing, type problems."""
    return pd.DataFrame({
        " Customer Name ": ["Alice Smith", "Bob Jones", "Alice Smith", "Diana Lee", None, "bob jones", "  Charlie  "],
        "AGE": ["25", "30", "25", "35", "28", "30", "40"],
        "Revenue (USD)": [1000, 2000, 1000, 3000, None, 2000, 500],
        "signup_date": ["2020-01-15", "2019-06-01", "2020-01-15", "2021-03-10", "2018-12-01", "2019-06-01", "2022-07-01"],
        "Status": ["Active", "active", "Active", "INACTIVE", "Active", "active", "active"],
        "is_premium": ["Y", "N", "Y", "Y", "N", "N", "Y"],
    })


@pytest.fixture
def ctx_dirty(dirty_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("dirty", dirty_df, "dirty_data.csv")
    return ctx


@pytest.fixture
def ctx_clean_multi(sample_df: pd.DataFrame, dirty_df: pd.DataFrame) -> AnalysisContext:
    ctx = AnalysisContext()
    ctx.add_dataset("clean", sample_df, "clean.csv")
    ctx.add_dataset("dirty", dirty_df, "dirty.csv")
    return ctx


@pytest.fixture
def registry(eda: EDASpecialist, viz: VizSpecialist, sql: SQLSpecialist, stats: StatsSpecialist, cleaning: CleaningSpecialist) -> SpecialistRegistry:
    reg = SpecialistRegistry()
    reg.register(eda)
    reg.register(viz)
    reg.register(sql)
    reg.register(stats)
    reg.register(cleaning)
    return reg


@pytest.fixture
def middleware(registry: SpecialistRegistry) -> ErrorRecoveryMiddleware:
    return ErrorRecoveryMiddleware(registry, max_retries=1, base_delay=0.01)
