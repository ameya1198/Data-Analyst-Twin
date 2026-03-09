"""Unit tests for the SQL Specialist."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.agent.specialists.sql import SQLSpecialist
from app.agent.specialists.context import AnalysisContext


# ─── sql_schema ───────────────────────────────────────────────────────────────

class TestSQLSchema:

    @pytest.mark.asyncio
    async def test_schema_returns_all_tables(self, sql: SQLSpecialist, ctx_multi: AnalysisContext):
        r = await sql.execute("sql_schema", {}, ctx_multi)
        assert r.success
        assert r.data["table_count"] == 2
        table_ids = {s["dataset_id"] for s in r.data["schemas"]}
        assert "employees" in table_ids
        assert "orders" in table_ids

    @pytest.mark.asyncio
    async def test_schema_single_table(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_schema", {"dataset_id": "orders"}, ctx_orders)
        assert r.success
        assert r.data["table_count"] == 1
        assert r.data["schemas"][0]["dataset_id"] == "orders"

    @pytest.mark.asyncio
    async def test_schema_has_create_statement(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_schema", {}, ctx_orders)
        assert r.success
        create = r.data["create_statements"]
        assert "CREATE TABLE" in create
        assert "order_id" in create

    @pytest.mark.asyncio
    async def test_schema_columns_have_sql_types(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_schema", {}, ctx_orders)
        cols = r.data["schemas"][0]["columns"]
        type_names = {c["sql_type"] for c in cols}
        assert "INTEGER" in type_names or "DOUBLE" in type_names or "VARCHAR" in type_names

    @pytest.mark.asyncio
    async def test_schema_no_data_error(self, sql: SQLSpecialist):
        ctx = AnalysisContext()
        r = await sql.execute("sql_schema", {}, ctx)
        assert not r.success
        assert "No datasets" in r.summary

    @pytest.mark.asyncio
    async def test_schema_unknown_dataset_error(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_schema", {"dataset_id": "nonexistent"}, ctx_orders)
        assert not r.success
        assert "not found" in r.summary.lower()


# ─── sql_execute ──────────────────────────────────────────────────────────────

class TestSQLExecute:

    @pytest.mark.asyncio
    async def test_basic_select(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_execute", {"query": "SELECT * FROM orders LIMIT 5"}, ctx_orders)
        assert r.success
        assert r.data["row_count"] == 5
        assert "order_id" in r.data["columns"]

    @pytest.mark.asyncio
    async def test_aggregation_query(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        query = """\
SELECT
    status,
    COUNT(*) AS order_count,
    ROUND(SUM(amount), 2) AS total_amount
FROM orders
GROUP BY status
ORDER BY order_count DESC"""
        r = await sql.execute("sql_execute", {"query": query}, ctx_orders)
        assert r.success
        assert "status" in r.data["columns"]
        assert "order_count" in r.data["columns"]
        assert r.data["row_count"] >= 1

    @pytest.mark.asyncio
    async def test_cte_query(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        query = """\
WITH completed AS (
    SELECT * FROM orders WHERE status = 'completed'
)
SELECT COUNT(*) AS cnt FROM completed"""
        r = await sql.execute("sql_execute", {"query": query}, ctx_orders)
        assert r.success
        assert r.data["row_count"] == 1
        assert r.data["preview"][0]["cnt"] > 0

    @pytest.mark.asyncio
    async def test_window_function(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        query = """\
SELECT
    order_id,
    amount,
    RANK() OVER (ORDER BY amount DESC) AS amount_rank
FROM orders
LIMIT 10"""
        r = await sql.execute("sql_execute", {"query": query}, ctx_orders)
        assert r.success
        assert "amount_rank" in r.data["columns"]
        assert r.data["preview"][0]["amount_rank"] == 1

    @pytest.mark.asyncio
    async def test_save_result_as_new_dataset(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        query = "SELECT order_id, amount FROM orders WHERE amount > 200"
        r = await sql.execute("sql_execute", {"query": query, "save_as": "high_value"}, ctx_orders)
        assert r.success
        assert r.data["saved_as"] == "high_value"
        assert "high_value" in ctx_orders.datasets

    @pytest.mark.asyncio
    async def test_anti_pattern_warnings(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_execute", {"query": "SELECT * FROM orders"}, ctx_orders)
        assert r.success
        assert "anti_pattern_warnings" in r.data
        assert any(w["pattern"] == "SELECT * in production" for w in r.data["anti_pattern_warnings"])

    @pytest.mark.asyncio
    async def test_syntax_error_returns_error(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_execute", {"query": "SELEC bad syntax"}, ctx_orders)
        assert not r.success
        assert r.error is not None

    @pytest.mark.asyncio
    async def test_unknown_table_error(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_execute", {"query": "SELECT * FROM nonexistent"}, ctx_orders)
        assert not r.success
        assert "hint" in r.data

    @pytest.mark.asyncio
    async def test_empty_query_error(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_execute", {"query": ""}, ctx_orders)
        assert not r.success

    @pytest.mark.asyncio
    async def test_no_data_error(self, sql: SQLSpecialist):
        ctx = AnalysisContext()
        r = await sql.execute("sql_execute", {"query": "SELECT 1"}, ctx)
        assert not r.success

    @pytest.mark.asyncio
    async def test_cross_table_join(self, sql: SQLSpecialist, ctx_multi: AnalysisContext):
        query = """\
SELECT COUNT(*) AS cnt
FROM employees e
CROSS JOIN orders o
LIMIT 1"""
        r = await sql.execute("sql_execute", {"query": query}, ctx_multi)
        assert r.success
        assert r.data["row_count"] == 1

    @pytest.mark.asyncio
    async def test_null_handling_in_results(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        query = "SELECT NULL AS empty_col, 42 AS value LIMIT 1"
        r = await sql.execute("sql_execute", {"query": query}, ctx_orders)
        assert r.success
        assert r.data["preview"][0]["empty_col"] is None
        assert r.data["preview"][0]["value"] == 42

    @pytest.mark.asyncio
    async def test_execution_ms_reported(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        r = await sql.execute("sql_execute", {"query": "SELECT 1 AS x"}, ctx_orders)
        assert r.success
        assert r.data["execution_ms"] >= 0


# ─── sql_validate ─────────────────────────────────────────────────────────────

class TestSQLValidate:

    @pytest.mark.asyncio
    async def test_clean_query_passes(self, sql: SQLSpecialist, ctx: AnalysisContext):
        query = "SELECT order_id, amount FROM orders WHERE status = 'completed' LIMIT 10"
        r = await sql.execute("sql_validate", {"query": query}, ctx)
        assert r.success
        assert r.data["verdict"] == "clean"

    @pytest.mark.asyncio
    async def test_anti_pattern_flagged(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_validate", {"query": "SELECT * FROM orders WHERE col = NULL"}, ctx)
        assert r.success
        assert r.data["verdict"] == "needs_fixes"
        assert r.data["anti_pattern_count"] >= 2

    @pytest.mark.asyncio
    async def test_style_issues_flagged(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_validate", {"query": "select name from users"}, ctx)
        assert r.success
        assert r.data["style_issue_count"] > 0

    @pytest.mark.asyncio
    async def test_empty_query_error(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_validate", {"query": ""}, ctx)
        assert not r.success


# ─── sql_template ─────────────────────────────────────────────────────────────

class TestSQLTemplate:

    @pytest.mark.asyncio
    async def test_list_all_templates(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_template", {}, ctx)
        assert r.success
        assert r.data["count"] >= 8

    @pytest.mark.asyncio
    async def test_get_cohort_template(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_template", {"pattern": "cohort_analysis", "table": "orders"}, ctx)
        assert r.success
        assert "orders" in r.data["sql"]
        assert r.data["pattern"] == "cohort_analysis"

    @pytest.mark.asyncio
    async def test_template_with_unfilled_placeholders(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_template", {"pattern": "top_n_per_group"}, ctx)
        assert r.success
        assert "unfilled_placeholders" in r.data
        assert "table" in r.data["unfilled_placeholders"]

    @pytest.mark.asyncio
    async def test_unknown_template_error(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_template", {"pattern": "nonexistent"}, ctx)
        assert not r.success

    @pytest.mark.asyncio
    async def test_period_over_period_template(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_template", {"pattern": "period_over_period", "table": "sales"}, ctx)
        assert r.success
        assert "LAG" in r.data["sql"]


# ─── sql_format ───────────────────────────────────────────────────────────────

class TestSQLFormat:

    @pytest.mark.asyncio
    async def test_basic_formatting(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_format", {"query": "select name from users where id = 1"}, ctx)
        assert r.success
        formatted = r.data["formatted"]
        assert "SELECT" in formatted
        assert "FROM" in formatted
        assert "WHERE" in formatted

    @pytest.mark.asyncio
    async def test_formatting_improves_style(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_format", {"query": "select count(*) from orders group by status"}, ctx)
        assert r.success
        assert r.data["style_issues_after"] <= r.data["style_issues_before"]

    @pytest.mark.asyncio
    async def test_anti_patterns_still_reported(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_format", {"query": "select * from orders"}, ctx)
        assert r.success
        assert len(r.data["anti_patterns"]) > 0

    @pytest.mark.asyncio
    async def test_empty_query_error(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_format", {"query": ""}, ctx)
        assert not r.success


# ─── Edge Cases & Integration ─────────────────────────────────────────────────

class TestSQLEdgeCases:

    @pytest.mark.asyncio
    async def test_unknown_tool_name(self, sql: SQLSpecialist, ctx: AnalysisContext):
        r = await sql.execute("sql_nonexistent", {}, ctx)
        assert not r.success
        assert "Unknown" in r.summary

    @pytest.mark.asyncio
    async def test_specialist_metadata(self, sql: SQLSpecialist):
        assert sql.name == "sql"
        assert sql.mode.value == "tool"
        assert len(sql.get_tools()) == 5
        tool_names = sql.get_tool_names()
        assert "sql_schema" in tool_names
        assert "sql_execute" in tool_names
        assert "sql_validate" in tool_names
        assert "sql_template" in tool_names
        assert "sql_format" in tool_names

    @pytest.mark.asyncio
    async def test_execute_with_special_chars_in_dataset_id(self, sql: SQLSpecialist):
        ctx = AnalysisContext()
        df = pd.DataFrame({"x": [1, 2, 3]})
        ctx.add_dataset("my-data-set", df, "data.csv")
        r = await sql.execute("sql_execute", {"query": 'SELECT * FROM "my-data-set" LIMIT 1'}, ctx)
        assert r.success
        assert r.data["row_count"] == 1

    @pytest.mark.asyncio
    async def test_large_result_truncation(self, sql: SQLSpecialist):
        ctx = AnalysisContext()
        df = pd.DataFrame({"x": range(5000)})
        ctx.add_dataset("big", df, "big.csv")
        r = await sql.execute("sql_execute", {"query": "SELECT * FROM big"}, ctx)
        assert r.success
        assert r.data["row_count"] == 1000
        assert r.data["has_more_rows"] is True

    @pytest.mark.asyncio
    async def test_execute_analytical_pattern_cohort(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        """Execute a cohort-style query end-to-end."""
        query = """\
WITH cohorts AS (
    SELECT
        user_id,
        MIN(order_date) AS first_order
    FROM orders
    GROUP BY user_id
)
SELECT
    DATE_TRUNC('month', first_order) AS cohort_month,
    COUNT(*) AS cohort_size
FROM cohorts
GROUP BY 1
ORDER BY 1"""
        r = await sql.execute("sql_execute", {"query": query}, ctx_orders)
        assert r.success
        assert "cohort_month" in r.data["columns"]
        assert "cohort_size" in r.data["columns"]

    @pytest.mark.asyncio
    async def test_execute_period_over_period(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        """Execute a period-over-period query end-to-end."""
        query = """\
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', order_date) AS month,
        SUM(amount) AS revenue
    FROM orders
    GROUP BY 1
)
SELECT
    month,
    revenue,
    LAG(revenue, 1) OVER (ORDER BY month) AS prev_revenue
FROM monthly
ORDER BY month"""
        r = await sql.execute("sql_execute", {"query": query}, ctx_orders)
        assert r.success
        assert "prev_revenue" in r.data["columns"]

    @pytest.mark.asyncio
    async def test_conditional_aggregation(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        query = """\
SELECT
    product_category,
    SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END) AS completed_revenue,
    SUM(CASE WHEN status = 'refund' THEN amount ELSE 0 END) AS refunded_amount
FROM orders
GROUP BY product_category"""
        r = await sql.execute("sql_execute", {"query": query}, ctx_orders)
        assert r.success
        assert "completed_revenue" in r.data["columns"]
        assert "refunded_amount" in r.data["columns"]

    @pytest.mark.asyncio
    async def test_division_by_zero_returns_inf(self, sql: SQLSpecialist, ctx_orders: AnalysisContext):
        """DuckDB returns inf for integer division by zero instead of erroring."""
        query = "SELECT 1/0 AS bad_calc"
        r = await sql.execute("sql_execute", {"query": query}, ctx_orders)
        assert r.success
        assert r.data["preview"][0]["bad_calc"] == float("inf")
