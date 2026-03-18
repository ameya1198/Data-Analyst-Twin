"""
SQL Knowledge Base — 13 domains of SQL analytical mastery.

Grounded in the principle: SQL is not just a retrieval tool — it is an
analytical language. Master analysts use it to express business logic,
not just fetch rows.

Sections:
 1. Foundational Philosophy
 2. Formatting & Style Standards
 3. Query Execution Order
 4. CTE Hierarchy (Common Table Expressions)
 5. Window Functions Mastery
 6. JOIN Principles
 7. Performance Optimisation Rules
 8. Aggregation Patterns
 9. NULL Handling Rules
10. Analytical SQL Patterns (Cohort, Retention, Funnel, Period-over-Period)
11. SQL Anti-Patterns
12. Commenting Standard
13. Dialect Differences Cheat Sheet
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─── 1. Foundational Philosophy ──────────────────────────────────────────────

SQL_PHILOSOPHY: dict[str, Any] = {
    "core_principle": (
        "SQL is not just a retrieval tool — it is an analytical language. "
        "Master analysts use it to express business logic, not just fetch rows."
    ),
    "readability": (
        "Write SQL that a colleague can read and understand 6 months from now "
        "without explanation."
    ),
    "commenting": (
        "The most important thing to capture in comments is the 'why' — "
        "it's obvious what the code does, but the reason behind it is what matters."
    ),
    "priority_order": [
        "1. Correctness — the query returns the right data",
        "2. Readability — a colleague can understand it without explanation",
        "3. Performance — optimise only after correctness and readability are proven",
    ],
    "golden_rule": (
        "Avoid tuning your SQL query until you know it returns the data "
        "you're looking for."
    ),
}


# ─── 2. Formatting & Style Standards ─────────────────────────────────────────

FORMATTING_RULES: dict[str, Any] = {
    "casing": {
        "keywords": "UPPERCASE for SQL keywords: SELECT, FROM, WHERE, JOIN, GROUP BY",
        "functions": "UPPERCASE for SQL functions: COUNT(), SUM(), DATE_TRUNC(), COALESCE()",
        "identifiers": "lowercase for table names, column names, and aliases",
    },
    "naming": {
        "convention": "snake_case — underscores where you'd naturally include a space",
        "examples": {
            "good": ["first_name", "order_date", "total_amount"],
            "bad": ["firstName", "FirstName", "tbl_orders", "colRevenue"],
        },
        "tables": "Use collective or plural names: employees, orders, products",
        "aliases": "Meaningful aliases: o for orders, c for customers — not a, b, x",
    },
    "layout": {
        "clause_per_line": "Each major clause on its own line: SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY",
        "indent_columns": "Indent column names and WHERE conditions one level",
        "align_operators": "Align AND / OR operators at the start of lines, not the end",
        "one_col_per_line": "One column per line in SELECT for queries with more than 3 columns",
    },
}


# ─── 3. Query Execution Order ────────────────────────────────────────────────

class SQLClause(str, Enum):
    FROM = "FROM"
    WHERE = "WHERE"
    GROUP_BY = "GROUP BY"
    HAVING = "HAVING"
    SELECT = "SELECT"
    DISTINCT = "DISTINCT"
    ORDER_BY = "ORDER BY"
    LIMIT = "LIMIT"


EXECUTION_ORDER: list[dict[str, str]] = [
    {"position": "1", "clause": "FROM / JOIN", "note": "Identifies tables and combines rows"},
    {"position": "2", "clause": "WHERE", "note": "Filters rows before grouping"},
    {"position": "3", "clause": "GROUP BY", "note": "Groups rows for aggregation"},
    {"position": "4", "clause": "HAVING", "note": "Filters groups after aggregation"},
    {"position": "5", "clause": "SELECT", "note": "Evaluates expressions and aliases"},
    {"position": "6", "clause": "DISTINCT", "note": "Removes duplicate result rows"},
    {"position": "7", "clause": "ORDER BY / LIMIT", "note": "Sorts and limits final output"},
]

EXECUTION_ORDER_RULE = (
    "You cannot reference a SELECT alias in a WHERE clause — because WHERE "
    "runs before SELECT. Use a CTE or subquery instead."
)


# ─── 4. CTE Hierarchy ────────────────────────────────────────────────────────

CTE_RULES: dict[str, Any] = {
    "when_to_use": [
        "Query has more than 2 joins or subqueries",
        "Same subquery logic is referenced more than once",
        "You need to debug intermediate results",
        "Building multi-step transformations (filter → aggregate → rank)",
    ],
    "naming": "Name each CTE after what it contains, not what it does: active_customers not filter_step",
    "structure": "Don't nest CTEs unnecessarily — chain them sequentially instead",
    "performance": "Materialise intermediate results using CTEs or temporary tables for large transformations",
    "pattern": [
        "Step 1: Filter raw data → WITH base AS (...)",
        "Step 2: Aggregate → monthly_revenue AS (...)",
        "Step 3: Rank / transform → ranked AS (...)",
        "Step 4: Final SELECT from the last CTE",
    ],
}


# ─── 5. Window Functions ─────────────────────────────────────────────────────

@dataclass
class WindowFunctionCategory:
    category: str
    functions: list[str]
    use_cases: list[str]


WINDOW_CATEGORIES: list[WindowFunctionCategory] = [
    WindowFunctionCategory(
        category="Ranking",
        functions=["ROW_NUMBER()", "RANK()", "DENSE_RANK()", "NTILE()"],
        use_cases=["Top-N per group", "deduplication", "percentile buckets"],
    ),
    WindowFunctionCategory(
        category="Value",
        functions=["LAG()", "LEAD()", "FIRST_VALUE()", "LAST_VALUE()"],
        use_cases=["Period-over-period comparison", "next/previous event"],
    ),
    WindowFunctionCategory(
        category="Aggregate",
        functions=["SUM() OVER()", "AVG() OVER()", "COUNT() OVER()"],
        use_cases=["Running totals", "moving averages", "cumulative metrics"],
    ),
]

RANK_VS_DENSE_RANK = {
    "ROW_NUMBER": {"ties": "Unique always", "gaps": "No ties possible"},
    "RANK": {"ties": "Same rank for ties", "gaps": "Skips next rank (1,1,3)"},
    "DENSE_RANK": {"ties": "Same rank for ties", "gaps": "No gaps (1,1,2)"},
}

WINDOW_PATTERNS: dict[str, str] = {
    "running_total": "SUM(revenue) OVER (ORDER BY date) AS cumulative_revenue",
    "month_over_month": (
        "LAG(revenue, 1) OVER (PARTITION BY product_id ORDER BY month) "
        "AS prev_month_revenue"
    ),
    "rank_within_group": (
        "RANK() OVER (PARTITION BY category ORDER BY sales DESC) AS category_rank"
    ),
    "moving_average_7d": (
        "AVG(daily_sales) OVER (ORDER BY date "
        "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma_7d"
    ),
    "pct_of_total": "SUM(revenue) / SUM(SUM(revenue)) OVER () AS pct_of_total",
}


# ─── 6. JOIN Principles ──────────────────────────────────────────────────────

@dataclass
class JoinGuide:
    scenario: str
    join_type: str
    note: str = ""


JOIN_GUIDE: list[JoinGuide] = [
    JoinGuide("Only matching rows from both tables", "INNER JOIN"),
    JoinGuide("All rows from left, matching from right", "LEFT JOIN"),
    JoinGuide("All rows from right, matching from left", "LEFT JOIN (swap table order — avoid RIGHT JOIN)"),
    JoinGuide("All rows from both, NULL where no match", "FULL OUTER JOIN"),
    JoinGuide("Every combination of rows", "CROSS JOIN (use carefully)"),
    JoinGuide("Records NOT in another table", "LEFT JOIN ... WHERE right.id IS NULL"),
]

JOIN_RULES: list[str] = [
    "Use ANSI-92 JOIN syntax, not comma-separated WHERE clause syntax (ANSI-89)",
    "Always qualify columns with table alias when joining: o.customer_id not just customer_id",
    "Avoid RIGHT JOIN — rewrite as LEFT JOIN by swapping table order",
    "Join on indexed columns where possible",
    "Filter in WHERE after joining, not in ON clause (unless it's an outer join filter)",
]


# ─── 7. Performance Optimisation ─────────────────────────────────────────────

PERFORMANCE_RULES: dict[str, list[str]] = {
    "index_awareness": [
        "Wrapping a column in a function prevents index usage: WHERE created_at >= '2023-01-01' not WHERE YEAR(created_at) = 2023",
        "Leading wildcard LIKE '%john%' forces full table scan — LIKE 'john%' can use an index",
        "Index columns used in PARTITION BY and ORDER BY clauses of window functions",
    ],
    "query_efficiency": [
        "Correlated subqueries run once per row — rewrite as JOIN or CTE for large tables",
        "SELECT * only for exploration with LIMIT — never in production queries",
        "Filter data early (in WHERE or early CTEs) to reduce rows before joins and aggregations",
        "Use EXPLAIN / EXPLAIN ANALYZE to read the query execution plan before optimising",
    ],
    "explain_guide": [
        "Seq Scan: full table scan — bad on large tables",
        "Index Scan: good — using an index",
        "Hash Join: efficient for large sets vs Nested Loop: expensive for large sets",
        "High cost numbers signal expensive operations",
        "Rows estimate wildly off from actual → stale statistics, run ANALYZE",
    ],
}


# ─── 8. Aggregation Patterns ─────────────────────────────────────────────────

AGGREGATION_RULES: list[str] = [
    "Every column in SELECT not inside an aggregate must appear in GROUP BY",
    "Use HAVING to filter on aggregated results (not WHERE): HAVING COUNT(*) > 5",
    "GROUP BY 1, 2 (positional) is acceptable for ad-hoc queries, use column names in production",
]

AGGREGATION_PATTERNS: dict[str, str] = {
    "count_distinct": "COUNT(DISTINCT customer_id)",
    "conditional_aggregation": (
        "SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) AS paid_revenue"
    ),
    "percentage_breakdown": "COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct",
    "first_last_per_group": (
        "MIN(created_at) AS first_order_date, "
        "MAX(created_at) AS last_order_date"
    ),
    "safe_ratio": (
        "ROUND(SUM(revenue) / NULLIF(COUNT(orders), 0), 2) AS avg_order_value"
    ),
}


# ─── 9. NULL Handling ─────────────────────────────────────────────────────────

NULL_RULES: list[str] = [
    "NULL is not a value — it represents the absence of a value. NULL = NULL is false",
    "Use IS NULL / IS NOT NULL, never = NULL",
    "COUNT(*) counts all rows including NULLs. COUNT(column) skips NULLs — know the difference",
    "Use COALESCE(value, fallback) to replace NULLs: COALESCE(discount, 0)",
    "Use NULLIF(a, b) to avoid division by zero: revenue / NULLIF(units, 0)",
    "NULL in a JOIN key will never match — rows are silently dropped",
]


# ─── 10. Analytical SQL Patterns ─────────────────────────────────────────────

ANALYTICAL_TEMPLATES: dict[str, dict[str, str]] = {
    "cohort_analysis": {
        "description": "User cohort by first purchase month with retention tracking",
        "template": """\
WITH cohorts AS (
    SELECT
        user_id,
        DATE_TRUNC('month', MIN(order_date)) AS cohort_month
    FROM {table}
    GROUP BY user_id
)
SELECT
    cohort_month,
    DATE_TRUNC('month', o.order_date) AS order_month,
    COUNT(DISTINCT o.user_id)          AS active_users
FROM {table} o
JOIN cohorts c ON o.user_id = c.user_id
GROUP BY 1, 2
ORDER BY 1, 2""",
    },
    "retention_churn": {
        "description": "Users active last month but not this month (churned)",
        "template": """\
WITH active_last_month AS (
    SELECT DISTINCT user_id
    FROM {table}
    WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
      AND order_date <  DATE_TRUNC('month', CURRENT_DATE)
),
active_this_month AS (
    SELECT DISTINCT user_id
    FROM {table}
    WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE)
)
SELECT lm.user_id AS churned_user_id
FROM active_last_month lm
LEFT JOIN active_this_month tm
    ON lm.user_id = tm.user_id
WHERE tm.user_id IS NULL""",
    },
    "funnel_analysis": {
        "description": "Step-by-step conversion funnel",
        "template": """\
SELECT
    COUNT(DISTINCT CASE WHEN step >= 1 THEN user_id END) AS step_1_users,
    COUNT(DISTINCT CASE WHEN step >= 2 THEN user_id END) AS step_2_users,
    COUNT(DISTINCT CASE WHEN step >= 3 THEN user_id END) AS step_3_users,
    ROUND(
        COUNT(DISTINCT CASE WHEN step >= 2 THEN user_id END) * 100.0
        / NULLIF(COUNT(DISTINCT CASE WHEN step >= 1 THEN user_id END), 0),
        1
    ) AS step_1_to_2_pct,
    ROUND(
        COUNT(DISTINCT CASE WHEN step >= 3 THEN user_id END) * 100.0
        / NULLIF(COUNT(DISTINCT CASE WHEN step >= 2 THEN user_id END), 0),
        1
    ) AS step_2_to_3_pct
FROM {table}""",
    },
    "period_over_period": {
        "description": "Revenue comparison with growth rate vs prior period",
        "template": """\
WITH periods AS (
    SELECT
        DATE_TRUNC('month', order_date) AS period,
        SUM(amount)                      AS revenue
    FROM {table}
    GROUP BY 1
)
SELECT
    period,
    revenue,
    LAG(revenue, 1) OVER (ORDER BY period) AS prev_period_revenue,
    ROUND(
        revenue / NULLIF(LAG(revenue, 1) OVER (ORDER BY period), 0) - 1,
        4
    ) AS growth_rate
FROM periods
ORDER BY period""",
    },
    "running_total": {
        "description": "Cumulative sum over time",
        "template": """\
SELECT
    order_date,
    amount,
    SUM(amount) OVER (ORDER BY order_date) AS cumulative_amount
FROM {table}
ORDER BY order_date""",
    },
    "top_n_per_group": {
        "description": "Top N items within each category",
        "template": """\
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY {group_col}
            ORDER BY {rank_col} DESC
        ) AS rn
    FROM {table}
)
SELECT * FROM ranked WHERE rn <= {n}""",
    },
    "moving_average": {
        "description": "N-day moving average of a metric",
        "template": """\
SELECT
    date_col,
    metric,
    AVG(metric) OVER (
        ORDER BY date_col
        ROWS BETWEEN {window_size} PRECEDING AND CURRENT ROW
    ) AS moving_avg
FROM {table}
ORDER BY date_col""",
    },
    "deduplication": {
        "description": "Keep only the latest record per entity",
        "template": """\
WITH numbered AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY {entity_col}
            ORDER BY {date_col} DESC
        ) AS rn
    FROM {table}
)
SELECT * FROM numbered WHERE rn = 1""",
    },
}


# ─── 11. SQL Anti-Patterns ───────────────────────────────────────────────────

@dataclass
class SQLAntiPattern:
    pattern: str
    problem: str
    fix: str
    regex: str = ""


SQL_ANTI_PATTERNS: list[SQLAntiPattern] = [
    SQLAntiPattern(
        pattern="SELECT * in production",
        problem="Returns unnecessary columns, breaks on schema change",
        fix="Always name columns explicitly",
        regex=r"(?i)\bSELECT\s+\*\s+FROM\b",
    ),
    SQLAntiPattern(
        pattern="Correlated subquery in WHERE",
        problem="Runs once per row, extremely slow",
        fix="Rewrite as JOIN or CTE",
        regex=r"(?i)\bWHERE\s+.*\(\s*SELECT\b",
    ),
    SQLAntiPattern(
        pattern="Leading wildcard LIKE",
        problem="Full table scan, no index",
        fix="Add full-text index or restructure",
        regex=r"(?i)\bLIKE\s+['\"]%",
    ),
    SQLAntiPattern(
        pattern="Function on indexed column in WHERE",
        problem="Defeats the index",
        fix="Use range filter instead",
        regex=r"(?i)\bWHERE\s+\w+\([^)]*\)\s*[=<>!]",
    ),
    SQLAntiPattern(
        pattern="NOT IN with potential NULLs",
        problem="Returns no rows if subquery contains any NULL",
        fix="Use NOT EXISTS instead",
        regex=r"(?i)\bNOT\s+IN\s*\(",
    ),
    SQLAntiPattern(
        pattern="No LIMIT during exploration",
        problem="Returns millions of rows, crashes tools",
        fix="Always LIMIT during development",
        regex="",
    ),
    SQLAntiPattern(
        pattern="HAVING for non-aggregate filter",
        problem="Filters after grouping — slow",
        fix="Move non-aggregate filters to WHERE",
        regex="",
    ),
    SQLAntiPattern(
        pattern="Deeply nested subqueries",
        problem="Unreadable, hard to debug",
        fix="Refactor into CTEs",
        regex=r"(?i)\(\s*SELECT[^)]*\(\s*SELECT",
    ),
    SQLAntiPattern(
        pattern="ORDER BY in a CTE",
        problem="Meaningless and wasteful — only ORDER BY in final SELECT",
        fix="Remove ORDER BY from CTE definitions",
        regex=r"(?i)\)\s*,\s*\w+\s+AS\s*\([^)]*ORDER\s+BY",
    ),
    SQLAntiPattern(
        pattern="= NULL comparison",
        problem="NULL = NULL evaluates to false, rows silently dropped",
        fix="Use IS NULL / IS NOT NULL",
        regex=r"(?i)(?<![!<>])=\s*NULL\b",
    ),
    SQLAntiPattern(
        pattern="RIGHT JOIN",
        problem="Less readable than equivalent LEFT JOIN",
        fix="Rewrite as LEFT JOIN by swapping table order",
        regex=r"(?i)\bRIGHT\s+(OUTER\s+)?JOIN\b",
    ),
]


# ─── 12. Commenting Standard ─────────────────────────────────────────────────

COMMENT_TEMPLATE = """\
-- ============================================================
-- Query: {title}
-- Author: {author}
-- Date: {date}
-- Purpose: {purpose}
-- Dependencies: {dependencies}
-- Notes: {notes}
-- ============================================================"""


# ─── 13. Dialect Differences ─────────────────────────────────────────────────

class SQLDialect(str, Enum):
    POSTGRESQL = "postgresql"
    BIGQUERY = "bigquery"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"
    DUCKDB = "duckdb"


DIALECT_MAP: dict[str, dict[str, str]] = {
    "date_truncation": {
        "postgresql": "DATE_TRUNC('month', col)",
        "bigquery": "DATE_TRUNC(col, MONTH)",
        "mysql": "DATE_FORMAT(col, '%Y-%m')",
        "sqlserver": "DATETRUNC(month, col)",
        "duckdb": "DATE_TRUNC('month', col)",
    },
    "string_concat": {
        "postgresql": "|| or CONCAT()",
        "bigquery": "CONCAT()",
        "mysql": "CONCAT()",
        "sqlserver": "+ or CONCAT()",
        "duckdb": "|| or CONCAT()",
    },
    "limit_rows": {
        "postgresql": "LIMIT n",
        "bigquery": "LIMIT n",
        "mysql": "LIMIT n",
        "sqlserver": "TOP n",
        "duckdb": "LIMIT n",
    },
    "current_date": {
        "postgresql": "CURRENT_DATE",
        "bigquery": "CURRENT_DATE()",
        "mysql": "CURDATE()",
        "sqlserver": "GETDATE()",
        "duckdb": "CURRENT_DATE",
    },
    "regex_match": {
        "postgresql": "~ or SIMILAR TO",
        "bigquery": "REGEXP_CONTAINS()",
        "mysql": "REGEXP",
        "sqlserver": "LIKE only",
        "duckdb": "REGEXP_MATCHES()",
    },
}


# ─── Composite Knowledge Export ───────────────────────────────────────────────

SQL_KNOWLEDGE: dict[str, Any] = {
    "philosophy": SQL_PHILOSOPHY,
    "formatting": FORMATTING_RULES,
    "execution_order": EXECUTION_ORDER,
    "execution_order_rule": EXECUTION_ORDER_RULE,
    "cte_rules": CTE_RULES,
    "window_categories": [
        {
            "category": wc.category,
            "functions": wc.functions,
            "use_cases": wc.use_cases,
        }
        for wc in WINDOW_CATEGORIES
    ],
    "rank_comparison": RANK_VS_DENSE_RANK,
    "window_patterns": WINDOW_PATTERNS,
    "join_guide": [
        {"scenario": jg.scenario, "join_type": jg.join_type, "note": jg.note}
        for jg in JOIN_GUIDE
    ],
    "join_rules": JOIN_RULES,
    "performance_rules": PERFORMANCE_RULES,
    "aggregation_rules": AGGREGATION_RULES,
    "aggregation_patterns": AGGREGATION_PATTERNS,
    "null_rules": NULL_RULES,
    "analytical_templates": {
        k: {"description": v["description"]}
        for k, v in ANALYTICAL_TEMPLATES.items()
    },
    "anti_patterns": [
        {"pattern": ap.pattern, "problem": ap.problem, "fix": ap.fix}
        for ap in SQL_ANTI_PATTERNS
    ],
    "dialect_map": DIALECT_MAP,
}


# ─── Utility Functions ────────────────────────────────────────────────────────

def detect_anti_patterns(sql: str) -> list[dict[str, str]]:
    """Scan a SQL string for known anti-patterns using regex.

    Returns a list of dicts with keys: pattern, problem, fix.
    """
    findings: list[dict[str, str]] = []
    for ap in SQL_ANTI_PATTERNS:
        if not ap.regex:
            continue
        if re.search(ap.regex, sql):
            findings.append({
                "pattern": ap.pattern,
                "problem": ap.problem,
                "fix": ap.fix,
            })
    return findings


def validate_sql_style(sql: str) -> list[dict[str, str]]:
    """Check a SQL string for style issues against the formatting standards.

    Returns a list of dicts with keys: issue, recommendation.
    """
    issues: list[dict[str, str]] = []
    lines = sql.strip().split("\n")

    keywords = [
        "SELECT", "FROM", "WHERE", "GROUP BY", "HAVING",
        "ORDER BY", "LIMIT", "JOIN", "LEFT JOIN", "RIGHT JOIN",
        "INNER JOIN", "FULL OUTER JOIN", "CROSS JOIN", "WITH",
        "ON", "AND", "OR", "INSERT", "UPDATE", "DELETE", "CREATE",
        "ALTER", "DROP", "UNION", "EXCEPT", "INTERSECT",
    ]
    functions = [
        "COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "NULLIF",
        "DATE_TRUNC", "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG",
        "LEAD", "FIRST_VALUE", "LAST_VALUE", "NTILE", "CAST",
        "EXTRACT", "ROUND", "CONCAT",
    ]

    for kw in keywords:
        escaped = kw.replace(" ", r"\s+")
        pattern = rf"\b{escaped}\b"
        matches = re.finditer(pattern, sql, re.IGNORECASE)
        for m in matches:
            if m.group() != m.group().upper():
                issues.append({
                    "issue": f"Keyword '{m.group()}' should be UPPERCASE",
                    "recommendation": f"Use '{kw}' instead of '{m.group()}'",
                })
                break

    for fn in functions:
        pattern = rf"\b{fn}\s*\("
        matches = re.finditer(pattern, sql, re.IGNORECASE)
        for m in matches:
            fn_text = m.group().split("(")[0].strip()
            if fn_text != fn_text.upper():
                issues.append({
                    "issue": f"Function '{fn_text}' should be UPPERCASE",
                    "recommendation": f"Use '{fn.upper()}()' instead",
                })
                break

    if re.search(r"(?i)\bSELECT\b.+,.*,.*,", sql.split("\n")[0] if lines else ""):
        first_select_line = ""
        for line in lines:
            if re.search(r"(?i)^\s*SELECT\b", line):
                first_select_line = line
                break
        if first_select_line:
            cols_in_line = first_select_line.count(",")
            if cols_in_line > 2:
                issues.append({
                    "issue": "Multiple columns on same line as SELECT",
                    "recommendation": "Put each column on its own line for queries with >3 columns",
                })

    if re.search(r"(?i)\bRIGHT\s+(OUTER\s+)?JOIN\b", sql):
        issues.append({
            "issue": "RIGHT JOIN used",
            "recommendation": "Prefer LEFT JOIN by swapping table order for readability",
        })

    return issues


def get_template(pattern_name: str, **kwargs: str) -> dict[str, str] | None:
    """Get an analytical SQL template by name, with optional placeholder substitution.

    Valid pattern_name values:
        cohort_analysis, retention_churn, funnel_analysis,
        period_over_period, running_total, top_n_per_group,
        moving_average, deduplication

    Returns dict with 'description' and 'sql' keys, or None if not found.
    """
    template_entry = ANALYTICAL_TEMPLATES.get(pattern_name)
    if template_entry is None:
        return None

    sql = template_entry["template"]
    for key, value in kwargs.items():
        sql = sql.replace(f"{{{key}}}", value)

    return {
        "description": template_entry["description"],
        "sql": sql,
    }


def get_available_templates() -> list[dict[str, str]]:
    """List all available analytical SQL templates."""
    return [
        {"name": name, "description": entry["description"]}
        for name, entry in ANALYTICAL_TEMPLATES.items()
    ]


def get_join_recommendation(scenario: str) -> str:
    """Suggest a JOIN type based on a scenario description."""
    scenario_lower = scenario.lower()

    if "not in" in scenario_lower or "missing" in scenario_lower or "excluding" in scenario_lower:
        return "LEFT JOIN ... WHERE right.id IS NULL"
    if "all" in scenario_lower and "both" in scenario_lower:
        return "FULL OUTER JOIN"
    if "combination" in scenario_lower or "cross" in scenario_lower or "cartesian" in scenario_lower:
        return "CROSS JOIN (use carefully)"
    if "only matching" in scenario_lower or "both tables" in scenario_lower:
        return "INNER JOIN"
    return "LEFT JOIN (default — preserves all rows from the primary table)"


def get_dialect_equivalent(feature: str, dialect: str) -> str | None:
    """Get the dialect-specific syntax for a SQL feature.

    Args:
        feature: Key from DIALECT_MAP (e.g. 'date_truncation', 'limit_rows')
        dialect: One of 'postgresql', 'bigquery', 'mysql', 'sqlserver', 'duckdb'
    """
    feature_map = DIALECT_MAP.get(feature)
    if feature_map is None:
        return None
    return feature_map.get(dialect)


def pandas_dtype_to_sql(dtype_str: str) -> str:
    """Map a pandas dtype string to the closest SQL type (DuckDB/PostgreSQL flavour)."""
    dtype_lower = str(dtype_str).lower()
    if "int" in dtype_lower:
        return "INTEGER"
    if "float" in dtype_lower:
        return "DOUBLE"
    if "bool" in dtype_lower:
        return "BOOLEAN"
    if "datetime" in dtype_lower:
        return "TIMESTAMP"
    if "timedelta" in dtype_lower:
        return "INTERVAL"
    if "category" in dtype_lower:
        return "VARCHAR"
    return "VARCHAR"
