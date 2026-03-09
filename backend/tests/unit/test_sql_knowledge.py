"""Unit tests for the SQL knowledge base (sql_knowledge.py)."""

from __future__ import annotations

import pytest

from app.agent.knowledge.sql_knowledge import (
    AGGREGATION_PATTERNS,
    ANALYTICAL_TEMPLATES,
    CTE_RULES,
    DIALECT_MAP,
    EXECUTION_ORDER,
    FORMATTING_RULES,
    JOIN_GUIDE,
    JOIN_RULES,
    NULL_RULES,
    PERFORMANCE_RULES,
    RANK_VS_DENSE_RANK,
    SQL_ANTI_PATTERNS,
    SQL_KNOWLEDGE,
    SQL_PHILOSOPHY,
    WINDOW_CATEGORIES,
    WINDOW_PATTERNS,
    SQLDialect,
    detect_anti_patterns,
    get_available_templates,
    get_dialect_equivalent,
    get_join_recommendation,
    get_template,
    pandas_dtype_to_sql,
    validate_sql_style,
)


class TestSQLKnowledgeStructure:
    """Verify knowledge base completeness."""

    def test_philosophy_has_priority_order(self):
        assert len(SQL_PHILOSOPHY["priority_order"]) == 3
        assert "Correctness" in SQL_PHILOSOPHY["priority_order"][0]
        assert "Readability" in SQL_PHILOSOPHY["priority_order"][1]
        assert "Performance" in SQL_PHILOSOPHY["priority_order"][2]

    def test_formatting_rules_completeness(self):
        assert "casing" in FORMATTING_RULES
        assert "naming" in FORMATTING_RULES
        assert "layout" in FORMATTING_RULES

    def test_execution_order_has_7_steps(self):
        assert len(EXECUTION_ORDER) == 7
        assert EXECUTION_ORDER[0]["clause"] == "FROM / JOIN"
        assert EXECUTION_ORDER[-1]["clause"] == "ORDER BY / LIMIT"

    def test_cte_rules_has_when_to_use(self):
        assert len(CTE_RULES["when_to_use"]) >= 4
        assert "pattern" in CTE_RULES

    def test_window_categories_cover_three_types(self):
        assert len(WINDOW_CATEGORIES) == 3
        cats = {wc.category for wc in WINDOW_CATEGORIES}
        assert cats == {"Ranking", "Value", "Aggregate"}

    def test_rank_comparison_three_functions(self):
        assert set(RANK_VS_DENSE_RANK.keys()) == {"ROW_NUMBER", "RANK", "DENSE_RANK"}

    def test_window_patterns_count(self):
        assert len(WINDOW_PATTERNS) >= 5

    def test_join_guide_count(self):
        assert len(JOIN_GUIDE) >= 6

    def test_join_rules_count(self):
        assert len(JOIN_RULES) >= 5

    def test_performance_rules_sections(self):
        assert "index_awareness" in PERFORMANCE_RULES
        assert "query_efficiency" in PERFORMANCE_RULES
        assert "explain_guide" in PERFORMANCE_RULES

    def test_aggregation_patterns_count(self):
        assert len(AGGREGATION_PATTERNS) >= 5

    def test_null_rules_count(self):
        assert len(NULL_RULES) >= 6

    def test_analytical_templates_count(self):
        assert len(ANALYTICAL_TEMPLATES) >= 8

    def test_anti_patterns_count(self):
        assert len(SQL_ANTI_PATTERNS) >= 11

    def test_dialect_map_covers_features(self):
        assert len(DIALECT_MAP) >= 5
        for feature, dialects in DIALECT_MAP.items():
            assert "postgresql" in dialects
            assert "bigquery" in dialects
            assert "duckdb" in dialects

    def test_sql_knowledge_composite_has_all_sections(self):
        expected_keys = [
            "philosophy", "formatting", "execution_order", "cte_rules",
            "window_categories", "join_guide", "performance_rules",
            "aggregation_patterns", "null_rules", "anti_patterns",
            "dialect_map", "analytical_templates",
        ]
        for key in expected_keys:
            assert key in SQL_KNOWLEDGE, f"Missing key: {key}"

    def test_sql_dialect_enum(self):
        assert SQLDialect.POSTGRESQL == "postgresql"
        assert SQLDialect.DUCKDB == "duckdb"
        assert len(SQLDialect) == 5


class TestDetectAntiPatterns:
    """Test anti-pattern detection on SQL strings."""

    def test_select_star(self):
        findings = detect_anti_patterns("SELECT * FROM orders")
        assert any(f["pattern"] == "SELECT * in production" for f in findings)

    def test_leading_wildcard(self):
        findings = detect_anti_patterns("SELECT name FROM users WHERE name LIKE '%john%'")
        assert any(f["pattern"] == "Leading wildcard LIKE" for f in findings)

    def test_not_in(self):
        findings = detect_anti_patterns("SELECT id FROM a WHERE id NOT IN (SELECT id FROM b)")
        assert any(f["pattern"] == "NOT IN with potential NULLs" for f in findings)

    def test_equals_null(self):
        findings = detect_anti_patterns("SELECT * FROM t WHERE col = NULL")
        patterns = [f["pattern"] for f in findings]
        assert "= NULL comparison" in patterns

    def test_right_join(self):
        findings = detect_anti_patterns("SELECT * FROM a RIGHT JOIN b ON a.id = b.id")
        patterns = [f["pattern"] for f in findings]
        assert "RIGHT JOIN" in patterns

    def test_correlated_subquery(self):
        findings = detect_anti_patterns(
            "SELECT * FROM orders WHERE amount > (SELECT AVG(amount) FROM orders)"
        )
        assert any(f["pattern"] == "Correlated subquery in WHERE" for f in findings)

    def test_clean_query_no_findings(self):
        clean_sql = """\
SELECT
    o.order_id,
    o.amount
FROM orders o
WHERE o.status = 'completed'
ORDER BY o.amount DESC
LIMIT 10"""
        findings = detect_anti_patterns(clean_sql)
        assert len(findings) == 0

    def test_nested_subqueries(self):
        sql = "SELECT * FROM (SELECT * FROM (SELECT id FROM t) a) b"
        findings = detect_anti_patterns(sql)
        assert any(f["pattern"] == "Deeply nested subqueries" for f in findings)


class TestValidateSQLStyle:

    def test_lowercase_keyword_flagged(self):
        issues = validate_sql_style("select name from users where id = 1")
        assert len(issues) > 0
        assert any("should be UPPERCASE" in i["issue"] for i in issues)

    def test_uppercase_keywords_pass(self):
        issues = validate_sql_style("SELECT name FROM users WHERE id = 1")
        keyword_issues = [i for i in issues if "keyword" in i["issue"].lower()]
        assert len(keyword_issues) == 0

    def test_right_join_flagged(self):
        issues = validate_sql_style("SELECT * FROM a RIGHT JOIN b ON a.id = b.id")
        assert any("RIGHT JOIN" in i["issue"] for i in issues)


class TestGetTemplate:

    def test_cohort_template_exists(self):
        result = get_template("cohort_analysis", table="orders")
        assert result is not None
        assert "cohort" in result["description"].lower()
        assert "orders" in result["sql"]

    def test_funnel_template_exists(self):
        result = get_template("funnel_analysis", table="events")
        assert result is not None
        assert "events" in result["sql"]

    def test_unknown_template_returns_none(self):
        result = get_template("nonexistent_pattern")
        assert result is None

    def test_top_n_per_group_placeholders(self):
        result = get_template(
            "top_n_per_group",
            table="products",
            group_col="category",
            rank_col="sales",
            n="3",
        )
        assert result is not None
        assert "products" in result["sql"]
        assert "category" in result["sql"]
        assert "sales" in result["sql"]
        assert "3" in result["sql"]

    def test_deduplication_template(self):
        result = get_template(
            "deduplication",
            table="events",
            entity_col="user_id",
            date_col="created_at",
        )
        assert result is not None
        assert "user_id" in result["sql"]
        assert "created_at" in result["sql"]


class TestGetAvailableTemplates:

    def test_returns_list_of_templates(self):
        templates = get_available_templates()
        assert isinstance(templates, list)
        assert len(templates) >= 8
        names = {t["name"] for t in templates}
        assert "cohort_analysis" in names
        assert "funnel_analysis" in names
        assert "period_over_period" in names


class TestGetJoinRecommendation:

    def test_not_in_scenario(self):
        result = get_join_recommendation("find records not in another table")
        assert "IS NULL" in result

    def test_matching_scenario(self):
        result = get_join_recommendation("only matching rows from both tables")
        assert "INNER" in result

    def test_cartesian_scenario(self):
        result = get_join_recommendation("every combination of rows (cartesian)")
        assert "CROSS" in result

    def test_default_is_left_join(self):
        result = get_join_recommendation("some vague scenario")
        assert "LEFT JOIN" in result


class TestGetDialectEquivalent:

    def test_postgresql_date_truncation(self):
        result = get_dialect_equivalent("date_truncation", "postgresql")
        assert result is not None
        assert "DATE_TRUNC" in result

    def test_bigquery_date_truncation(self):
        result = get_dialect_equivalent("date_truncation", "bigquery")
        assert result is not None
        assert "DATE_TRUNC" in result

    def test_duckdb_limit(self):
        result = get_dialect_equivalent("limit_rows", "duckdb")
        assert result == "LIMIT n"

    def test_unknown_feature_returns_none(self):
        result = get_dialect_equivalent("nonexistent_feature", "postgresql")
        assert result is None

    def test_unknown_dialect_returns_none(self):
        result = get_dialect_equivalent("date_truncation", "oracle")
        assert result is None


class TestPandasDtypeToSQL:

    @pytest.mark.parametrize("dtype,expected", [
        ("int64", "INTEGER"),
        ("float64", "DOUBLE"),
        ("bool", "BOOLEAN"),
        ("datetime64[ns]", "TIMESTAMP"),
        ("object", "VARCHAR"),
        ("category", "VARCHAR"),
    ])
    def test_type_mappings(self, dtype: str, expected: str):
        assert pandas_dtype_to_sql(dtype) == expected
