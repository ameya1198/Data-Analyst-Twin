"""
SQL Specialist — analytical SQL generation, execution, and validation in ToolMode.

Grounded in the principle: SQL is not just a retrieval tool — it is an
analytical language. Master analysts use it to express business logic,
not just fetch rows.

Knowledge framework covers 13 domains:
 1. Foundational Philosophy (correctness → readability → performance)
 2. Formatting & Style Standards (UPPERCASE keywords, snake_case, one-col-per-line)
 3. Query Execution Order (FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT)
 4. CTE Hierarchy (named steps, sequential chaining)
 5. Window Functions Mastery (ranking, value, aggregate)
 6. JOIN Principles (ANSI-92, avoid RIGHT JOIN, qualify columns)
 7. Performance Optimisation (index awareness, filter early, EXPLAIN reading)
 8. Aggregation Patterns (conditional agg, safe ratios, percentage breakdowns)
 9. NULL Handling (IS NULL, COALESCE, NULLIF, COUNT difference)
10. Analytical SQL Patterns (cohort, retention, funnel, period-over-period)
11. Anti-Patterns (SELECT *, correlated subqueries, leading wildcards, = NULL)
12. Commenting Standard (header block with purpose and dependencies)
13. Dialect Differences (PostgreSQL, BigQuery, MySQL, SQL Server, DuckDB)

Execution uses DuckDB in-process — every pandas DataFrame in the
AnalysisContext is registered as a queryable table.
"""

from __future__ import annotations

import re
import textwrap
import time
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import structlog

from app.agent.knowledge.sql_knowledge import (
    SQL_KNOWLEDGE,
    ANALYTICAL_TEMPLATES,
    AGGREGATION_PATTERNS,
    NULL_RULES,
    WINDOW_PATTERNS,
    detect_anti_patterns,
    get_available_templates,
    get_template,
    pandas_dtype_to_sql,
    validate_sql_style,
)
from app.agent.specialists.base import (
    BaseSpecialist,
    ResultType,
    SpecialistMode,
    SpecialistResult,
)
from app.agent.specialists.context import AnalysisContext

logger = structlog.get_logger(__name__)


class SQLSpecialist(BaseSpecialist):
    name = "sql"
    description = (
        "SQL specialist for analytical query generation, execution, and validation. "
        "Executes SQL queries against loaded datasets using DuckDB (full SQL support: "
        "CTEs, window functions, JOINs, aggregations). Validates queries against 11 "
        "known anti-patterns. Provides templates for common analytics patterns (cohort, "
        "retention, funnel, period-over-period, top-N, moving average, deduplication). "
        "Formats and style-checks SQL to ensure readability and correctness."
    )
    mode = SpecialistMode.TOOL
    timeout_seconds = 30
    system_prompt = (
        "You are the SQL specialist of a data analyst digital twin. "
        "SQL is an analytical language — use it to express business logic, not just fetch rows. "
        "Priority order: correctness → readability → performance. "
        "Use UPPERCASE keywords, snake_case identifiers, one column per line for >3 columns. "
        "Structure complex queries with CTEs (name after what they contain, chain sequentially). "
        "Master window functions for ranking, period comparisons, and running totals. "
        "Handle NULLs explicitly (COALESCE, NULLIF, IS NULL). "
        "Avoid anti-patterns: SELECT *, correlated subqueries, leading wildcards, = NULL, RIGHT JOIN. "
        "Execution engine is DuckDB — all loaded datasets are available as SQL tables."
    )

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "sql_schema",
                "description": (
                    "Show the SQL-friendly schema of all loaded datasets as CREATE TABLE "
                    "statements. Each pandas DataFrame in the session is registered as a "
                    "DuckDB table. Use this to understand available tables and columns "
                    "before writing queries. Returns table names, column names with SQL types, "
                    "row counts, and sample values."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "Optional: specific dataset to show schema for. If omitted, shows all datasets.",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "sql_execute",
                "description": (
                    "Execute a SQL query against the loaded datasets using DuckDB. "
                    "Each dataset is available as a table using its dataset_id as the table name. "
                    "Supports full SQL: CTEs, window functions, JOINs between datasets, "
                    "aggregations, subqueries. Returns query results as a table with up to "
                    "1000 rows. For large results, always use LIMIT. "
                    "Anti-pattern guard: automatically checks the query for known anti-patterns "
                    "and returns warnings alongside results."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The SQL query to execute. Use dataset_id values as table names.",
                        },
                        "save_as": {
                            "type": "string",
                            "description": "Optional: save the result as a new dataset with this ID for downstream analysis.",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "sql_validate",
                "description": (
                    "Validate a SQL query for anti-patterns and style issues without executing it. "
                    "Checks against 11 known SQL anti-patterns (SELECT *, correlated subqueries, "
                    "leading wildcards, function on indexed columns, NOT IN with NULLs, = NULL, "
                    "RIGHT JOIN, nested subqueries, ORDER BY in CTE). Also checks formatting "
                    "standards (keyword casing, column layout). Returns categorised findings with "
                    "severity and fix recommendations."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The SQL query to validate.",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "sql_template",
                "description": (
                    "Get a ready-to-use SQL template for common analytics patterns. "
                    "Available patterns: cohort_analysis, retention_churn, funnel_analysis, "
                    "period_over_period, running_total, top_n_per_group, moving_average, "
                    "deduplication. Templates use placeholders (e.g. {table}, {group_col}) "
                    "which are auto-filled from parameters. If no pattern specified, lists "
                    "all available templates."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Pattern name. One of: cohort_analysis, retention_churn, funnel_analysis, period_over_period, running_total, top_n_per_group, moving_average, deduplication. Omit to list all.",
                        },
                        "table": {
                            "type": "string",
                            "description": "Table name to substitute into the template.",
                        },
                        "group_col": {
                            "type": "string",
                            "description": "Grouping column (for top_n_per_group).",
                        },
                        "rank_col": {
                            "type": "string",
                            "description": "Ranking column (for top_n_per_group).",
                        },
                        "date_col": {
                            "type": "string",
                            "description": "Date column (for deduplication).",
                        },
                        "entity_col": {
                            "type": "string",
                            "description": "Entity column (for deduplication).",
                        },
                        "n": {
                            "type": "string",
                            "description": "N value (for top_n_per_group, default '5').",
                        },
                        "window_size": {
                            "type": "string",
                            "description": "Window size (for moving_average, default '6').",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "sql_format",
                "description": (
                    "Format a SQL query according to the SQL style standards. "
                    "Applies: UPPERCASE keywords, proper indentation, one clause per line, "
                    "aligned AND/OR operators. Also runs anti-pattern detection and style "
                    "checks, returning the formatted SQL alongside any warnings."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The SQL query to format.",
                        },
                    },
                    "required": ["query"],
                },
            },
        ]

    async def _execute_tool_mode(
        self, tool_name: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        dispatch = {
            "sql_schema": self._schema,
            "sql_execute": self._execute_query,
            "sql_validate": self._validate,
            "sql_template": self._template,
            "sql_format": self._format,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary=f"Unknown SQL tool: {tool_name}",
                error=f"Unknown tool: {tool_name}",
            )

        return await handler(params, context)

    # ─── Tool Implementations ─────────────────────────────────────────

    async def _schema(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """Generate SQL CREATE TABLE statements from loaded datasets."""
        if not context.has_data:
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary="No datasets loaded. Upload a file first.",
                error="No datasets available",
            )

        target_id = params.get("dataset_id")
        dataset_ids = [target_id] if target_id and target_id in context.datasets else list(context.datasets.keys())

        if target_id and target_id not in context.datasets:
            available = ", ".join(context.dataset_ids) or "none"
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary=f"Dataset '{target_id}' not found. Available: {available}",
                error=f"Dataset not found: {target_id}",
            )

        schemas: list[dict[str, Any]] = []
        create_statements: list[str] = []

        for did in dataset_ids:
            df = context.datasets[did]
            columns_info: list[dict[str, str]] = []
            col_defs: list[str] = []

            for col in df.columns:
                sql_type = pandas_dtype_to_sql(str(df[col].dtype))
                null_pct = round(df[col].isna().mean() * 100, 1)
                sample_vals = df[col].dropna().head(3).tolist()
                sample_strs = [str(v)[:50] for v in sample_vals]

                columns_info.append({
                    "name": str(col),
                    "pandas_dtype": str(df[col].dtype),
                    "sql_type": sql_type,
                    "null_pct": null_pct,
                    "sample_values": sample_strs,
                })
                nullable = "" if null_pct == 0 else "  -- {:.0f}% NULL".format(null_pct)
                col_defs.append(f"    {col} {sql_type}{nullable}")

            # Quote dataset_id in CREATE TABLE — required when id starts with digit (e.g. 0d8e0bf1)
            create_sql = f'CREATE TABLE "{did}" (\n' + ",\n".join(col_defs) + "\n);"
            create_statements.append(create_sql)

            schemas.append({
                "dataset_id": did,
                "table_name": did,
                "rows": len(df),
                "columns": columns_info,
                "create_statement": create_sql,
            })

        result_data = {
            "schemas": schemas,
            "table_count": len(schemas),
            "create_statements": "\n\n".join(create_statements),
            "usage_hint": (
                "Use dataset_id as table name in sql_execute. "
                "Quote it when it starts with a digit (e.g. FROM \"0d8e0bf1\")."
            ),
        }

        table_summary = "; ".join(
            f"{s['dataset_id']} ({s['rows']} rows, {len(s['columns'])} cols)"
            for s in schemas
        )

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.TABLE,
            data=result_data,
            summary=f"SQL schema for {len(schemas)} table(s): {table_summary}. Ready for sql_execute.",
            metadata={"tool": "sql_schema"},
        )

    async def _execute_query(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """Execute SQL against loaded datasets using DuckDB."""
        query = params.get("query", "").strip()
        save_as = params.get("save_as")

        if not query:
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary="Empty query. Provide a SQL query to execute.",
                error="Empty query",
            )

        if not context.has_data:
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary="No datasets loaded. Upload a file first.",
                error="No datasets available",
            )

        anti_pattern_warnings = detect_anti_patterns(query)

        conn = duckdb.connect(":memory:")
        try:
            for did, df in context.datasets.items():
                # SQL identifiers cannot start with digits (e.g. 0d8e0bf1). Use internal
                # name starting with letter, then create quoted view for dataset_id.
                safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", did)
                needs_quoted_view = safe_name[0].isdigit() or safe_name != did
                internal_name = f"tbl_{safe_name}" if safe_name[0].isdigit() else safe_name
                conn.register(internal_name, df)
                if needs_quoted_view:
                    conn.execute(f'CREATE VIEW "{did}" AS SELECT * FROM {internal_name}')

            start_time = time.perf_counter()
            result_rel = conn.execute(query)
            columns = [desc[0] for desc in result_rel.description]
            rows = result_rel.fetchmany(1000)
            execution_ms = (time.perf_counter() - start_time) * 1000

            result_df = pd.DataFrame(rows, columns=columns)
            total_rows = len(rows)

            has_more = False
            if total_rows == 1000:
                extra = result_rel.fetchone()
                if extra is not None:
                    has_more = True

            preview_rows = result_df.head(50).to_dict(orient="records")
            for row in preview_rows:
                for k, v in row.items():
                    if pd.isna(v):
                        row[k] = None
                    elif isinstance(v, (np.integer,)):
                        row[k] = int(v)
                    elif isinstance(v, (np.floating,)):
                        row[k] = float(v)

            if save_as:
                context.add_dataset(save_as, result_df, f"sql_result_{save_as}")

            result_data: dict[str, Any] = {
                "columns": columns,
                "column_count": len(columns),
                "row_count": total_rows,
                "has_more_rows": has_more,
                "preview": preview_rows,
                "execution_ms": round(execution_ms, 2),
                "query": query,
            }

            if anti_pattern_warnings:
                result_data["anti_pattern_warnings"] = anti_pattern_warnings

            if save_as:
                result_data["saved_as"] = save_as

            warning_str = ""
            if anti_pattern_warnings:
                warning_str = (
                    f" Warnings: {len(anti_pattern_warnings)} anti-pattern(s) detected "
                    f"({', '.join(w['pattern'] for w in anti_pattern_warnings[:3])})."
                )

            save_str = f" Saved as '{save_as}'." if save_as else ""

            summary = (
                f"SQL executed in {execution_ms:.0f}ms. "
                f"Result: {total_rows} rows x {len(columns)} columns"
                + (" (truncated to 1000)" if has_more else "")
                + f".{warning_str}{save_str}"
            )

            return SpecialistResult(
                success=True,
                specialist_name=self.name,
                result_type=ResultType.TABLE,
                data=result_data,
                summary=summary,
                metadata={"tool": "sql_execute", "execution_ms": execution_ms},
            )

        except duckdb.Error as e:
            error_msg = str(e)
            hint = self._get_error_hint(error_msg, context)
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data={"query": query, "error": error_msg, "hint": hint},
                summary=f"SQL error: {error_msg}. {hint}",
                error=error_msg,
            )
        finally:
            conn.close()

    async def _validate(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """Validate SQL for anti-patterns and style issues."""
        query = params.get("query", "").strip()

        if not query:
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary="Empty query. Provide a SQL query to validate.",
                error="Empty query",
            )

        anti_patterns = detect_anti_patterns(query)
        style_issues = validate_sql_style(query)

        all_findings: list[dict[str, str]] = []
        for ap in anti_patterns:
            all_findings.append({
                "type": "anti_pattern",
                "severity": "high",
                "issue": ap["pattern"],
                "detail": ap["problem"],
                "fix": ap["fix"],
            })
        for si in style_issues:
            all_findings.append({
                "type": "style",
                "severity": "low",
                "issue": si["issue"],
                "detail": "",
                "fix": si["recommendation"],
            })

        high_count = sum(1 for f in all_findings if f["severity"] == "high")
        low_count = sum(1 for f in all_findings if f["severity"] == "low")

        if not all_findings:
            verdict = "clean"
            verdict_text = "No anti-patterns or style issues detected."
        elif high_count > 0:
            verdict = "needs_fixes"
            verdict_text = f"{high_count} anti-pattern(s) found — fix before using in production."
        else:
            verdict = "minor_issues"
            verdict_text = f"{low_count} style suggestion(s) — query is functionally correct."

        result_data = {
            "query": query,
            "verdict": verdict,
            "findings": all_findings,
            "anti_pattern_count": len(anti_patterns),
            "style_issue_count": len(style_issues),
            "total_findings": len(all_findings),
        }

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.TEXT,
            data=result_data,
            summary=f"SQL validation: {verdict_text} ({len(anti_patterns)} anti-patterns, {len(style_issues)} style issues).",
            metadata={"tool": "sql_validate"},
        )

    async def _template(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """Get or list SQL analytics templates."""
        pattern = params.get("pattern")

        if not pattern:
            templates = get_available_templates()
            return SpecialistResult(
                success=True,
                specialist_name=self.name,
                result_type=ResultType.TEXT,
                data={
                    "templates": templates,
                    "count": len(templates),
                    "usage": "Call sql_template with pattern='<name>' and table='<your_table>' to get the SQL.",
                },
                summary=f"{len(templates)} SQL analytics templates available: {', '.join(t['name'] for t in templates)}.",
                metadata={"tool": "sql_template"},
            )

        substitutions: dict[str, str] = {}
        for key in ("table", "group_col", "rank_col", "date_col", "entity_col", "n", "window_size"):
            val = params.get(key)
            if val:
                substitutions[key] = val

        if "n" not in substitutions:
            substitutions["n"] = "5"
        if "window_size" not in substitutions:
            substitutions["window_size"] = "6"

        result = get_template(pattern, **substitutions)
        if result is None:
            available = [t["name"] for t in get_available_templates()]
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary=f"Unknown template: '{pattern}'. Available: {', '.join(available)}.",
                error=f"Unknown template: {pattern}",
            )

        has_unfilled = "{" in result["sql"]
        placeholders_remaining = re.findall(r"\{(\w+)\}", result["sql"])

        result_data: dict[str, Any] = {
            "pattern": pattern,
            "description": result["description"],
            "sql": result["sql"],
            "substitutions_applied": substitutions,
        }
        if has_unfilled:
            result_data["unfilled_placeholders"] = placeholders_remaining

        unfilled_str = ""
        if has_unfilled:
            unfilled_str = f" Note: {len(placeholders_remaining)} placeholder(s) still need values: {', '.join(placeholders_remaining)}."

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.CODE,
            data=result_data,
            summary=f"Template '{pattern}': {result['description']}.{unfilled_str}",
            metadata={"tool": "sql_template"},
        )

    async def _format(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """Format a SQL query to match the style standards."""
        query = params.get("query", "").strip()

        if not query:
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary="Empty query. Provide a SQL query to format.",
                error="Empty query",
            )

        formatted = self._apply_formatting(query)
        anti_patterns = detect_anti_patterns(query)
        style_issues_before = validate_sql_style(query)
        style_issues_after = validate_sql_style(formatted)

        result_data = {
            "original": query,
            "formatted": formatted,
            "anti_patterns": anti_patterns,
            "style_issues_before": len(style_issues_before),
            "style_issues_after": len(style_issues_after),
            "improvements": max(0, len(style_issues_before) - len(style_issues_after)),
        }

        warning_str = ""
        if anti_patterns:
            warning_str = f" {len(anti_patterns)} anti-pattern(s) detected — formatting cannot fix logic issues."

        return SpecialistResult(
            success=True,
            specialist_name=self.name,
            result_type=ResultType.CODE,
            data=result_data,
            summary=(
                f"SQL formatted. Style issues: {len(style_issues_before)} → {len(style_issues_after)}."
                f"{warning_str}"
            ),
            metadata={"tool": "sql_format"},
        )

    # ─── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _apply_formatting(sql: str) -> str:
        """Best-effort SQL formatting: uppercase keywords and basic clause alignment."""
        keywords = [
            "SELECT", "FROM", "WHERE", "GROUP BY", "HAVING",
            "ORDER BY", "LIMIT", "LEFT JOIN", "RIGHT JOIN",
            "INNER JOIN", "FULL OUTER JOIN", "CROSS JOIN", "JOIN",
            "ON", "WITH", "AS", "AND", "OR", "UNION ALL", "UNION",
            "EXCEPT", "INTERSECT", "INSERT INTO", "UPDATE", "DELETE FROM",
            "CREATE TABLE", "ALTER TABLE", "DROP TABLE", "SET",
            "CASE", "WHEN", "THEN", "ELSE", "END",
            "OVER", "PARTITION BY", "ROWS BETWEEN",
            "IN", "NOT IN", "EXISTS", "NOT EXISTS",
            "IS NULL", "IS NOT NULL", "BETWEEN", "LIKE",
            "ASC", "DESC", "DISTINCT", "ALL",
        ]

        functions = [
            "COUNT", "SUM", "AVG", "MIN", "MAX",
            "COALESCE", "NULLIF", "CAST", "ROUND",
            "DATE_TRUNC", "DATE_FORMAT", "EXTRACT",
            "ROW_NUMBER", "RANK", "DENSE_RANK", "NTILE",
            "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE",
            "CONCAT", "UPPER", "LOWER", "TRIM", "LENGTH",
            "ABS", "CEIL", "FLOOR", "GREATEST", "LEAST",
        ]

        result = sql

        for kw in sorted(keywords, key=len, reverse=True):
            pattern = r"\b" + kw.replace(" ", r"\s+") + r"\b"
            result = re.sub(pattern, kw, result, flags=re.IGNORECASE)

        for fn in functions:
            pattern = rf"\b{fn}\s*\("
            def _replace_fn(m: re.Match, fn_upper: str = fn) -> str:
                return fn_upper + "("
            result = re.sub(pattern, _replace_fn, result, flags=re.IGNORECASE)

        return result

    @staticmethod
    def _get_error_hint(error_msg: str, context: AnalysisContext) -> str:
        """Provide a helpful hint for common DuckDB SQL errors."""
        error_lower = error_msg.lower()

        if "not found" in error_lower and "table" in error_lower:
            tables = ", ".join(context.dataset_ids)
            return f"Available tables: {tables}. Use dataset_id as table name."
        if "not found" in error_lower and "column" in error_lower:
            return "Check column names with sql_schema. Column names are case-sensitive in DuckDB."
        if "syntax error" in error_lower:
            return "Check SQL syntax. DuckDB uses PostgreSQL-compatible syntax."
        if "type mismatch" in error_lower or "cast" in error_lower:
            return "Type mismatch — use CAST(col AS type) to convert."
        if "division by zero" in error_lower:
            return "Use NULLIF(denominator, 0) to avoid division by zero."
        if "ambiguous" in error_lower:
            return "Ambiguous column — qualify with table alias (e.g. t.column_name)."
        return "Check query syntax and table/column names with sql_schema."
