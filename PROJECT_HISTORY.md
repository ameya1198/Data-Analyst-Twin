# Data Analyst Digital Twin — Project History

> This file is the single source of truth for the project's history, architecture decisions,
> current state, and pending work. Refer to this whenever you need context on what has been
> built, why, and what comes next.

---

## 1. Project Vision

An AI-powered agent that mimics the reasoning, workflow, and outputs of a real data analyst.
The user uploads data (CSV/Excel/JSON/Parquet), asks questions in natural language, and the
twin plans, executes, and synthesizes analysis just like a human analyst would.

**Tech stack decided by user:**
- **Backend**: Python / FastAPI
- **Frontend**: Next.js / React (deferred — backend-first approach confirmed)
- **LLM**: Anthropic Claude (`claude-sonnet-4-20250514`)
- **Data processing**: pandas, numpy, scipy, statsmodels
- **Visualization**: Plotly
- **Observability**: structlog
- **Sandbox**: RestrictedPython

---

## 2. Architecture

### 2.1 Intent-Based Routing + Plan-Execute-Reflect

The Supervisor first classifies the user's intent (rule-based, zero LLM cost), then routes
to the appropriate execution mode:

| Mode | LLM Calls | When | Flow |
|---|---|---|---|
| **DIRECT** | 0 | Known single tool ("profile my data", "show schema") | Execute tool → Return result |
| **FOCUSED** | 2 | Scoped multi-step ("write SQL query", "run t-test", "clean data") | Plan → Execute → Lightweight Synthesize |
| **FULL** | 3-5 | Open exploration ("what insights can you find?", "deep dive") | Plan → Execute → Reflect (up to 2 cycles) → Full Synthesize |
| **CONVERSATIONAL** | 1+ | Follow-ups ("now show me a chart of that") | Dynamic tool-use loop (Claude decides) |

**Intent Classifier** (`intent.py`): Rule-based pattern matching with 16 user intents across
4 execution modes. Follow-up signals are boosted when conversation history exists. No LLM
call needed for classification — zero latency, zero cost.

**Why this matters**: "Profile my data" uses 0 LLM calls instead of 4. "Write a SQL query"
uses 2 instead of 4. Only open-ended exploration triggers the full loop.

**Components** (unchanged, but conditionally invoked):
1. **Planner** (`planner.py`) — creates structured analysis plan (JSON). Skipped in DIRECT mode.
2. **Executor** (`executor.py`) — runs plan steps via ErrorRecoveryMiddleware
3. **Reflector** (`reflector.py`) — evaluates results. Only used in FULL mode.
4. **Synthesizer** (prompts in `prompts.py`) — full narrative (FULL) or lightweight summary (FOCUSED). Skipped in DIRECT mode.

### 2.2 Hybrid Multi-Agent Architecture

Started as a single Supervisor with specialists operating as **local tools** (ToolMode).
Designed with a `BaseSpecialist` abstraction so any specialist can be upgraded to a full
sub-agent with its own LLM instance (`AgentMode`) without changing the Supervisor.

Key abstractions:
- `BaseSpecialist` / `SpecialistMode` / `SpecialistResult` — in `specialists/base.py`
- `AnalysisContext` — shared mutable state for datasets, schemas, results — in `specialists/context.py`
- `SpecialistRegistry` — registration and lookup — in `specialists/base.py`
- `create_supervisor()` factory — in `agent/__init__.py`

### 2.3 Guardrails Layer

- `validator.py` — input validation (size, type, content)
- `sanitizer.py` — output sanitization (PII detection, SQL injection)
- `rate_limiter.py` — per-session LLM call limits
- `confirmation.py` — human-in-the-loop for destructive actions

### 2.4 Observability

- `logger.py` — structlog configuration with JSON output
- `metrics.py` — latency, token usage, tool call tracking
- `events.py` — typed event definitions for streaming

### 2.5 Data Connectors

- `file_connector.py` — CSV, Excel, JSON, Parquet upload and parsing

### 2.6 API Layer

- `main.py` — FastAPI app with CORS, middleware
- `api/routes/data.py` — file upload endpoint
- `api/routes/chat.py` — chat/analysis endpoint
- `api/routes/sessions.py` — session management
- `api/middleware.py` — request logging, error handling

---

## 3. Specialists — Current State

### 3.1 EDA Specialist (`specialists/eda.py`)

**Status**: Built, tested, all edge cases passing.

**Knowledge base**: `knowledge/eda_knowledge.py` — 10-section framework grounded in
John Tukey's EDA philosophy (1977).

| Section | Content |
|---|---|
| 1. Foundational Philosophy | Tukey's mindset rules, two master questions (variation + covariation) |
| 2. EDA Process | 5 sequential phases: Dataset Overview → Univariate → Bivariate → Multivariate → Temporal |
| 3. Data Quality Assessment | MCAR/MAR/MNAR missingness classification, imputation rules, consistency checks |
| 4. Outlier Detection | Z-score (>3), IQR (1.5x mild, 3x extreme), multivariate (Mahalanobis), decision framework |
| 5. Distribution Analysis | Skewness thresholds (>1 significant), kurtosis (>3 heavy-tailed), normality tests, transformation toolbox |
| 6. Correlation & Relationships | Pearson/Spearman/Kendall guidance, 5-level strength labels (negligible→very strong), multicollinearity (|r|>0.8) |
| 7. Anti-patterns | 8 anti-patterns: p-hacking, MNAR dropping, data leakage, confirmation bias, over-cleaning, ignoring data generation, treating missingness equally, stopping at univariate |
| 8. Chart Selection | 10 analysis-type → chart mappings |
| 9. Output Deliverables | 8-item EDA brief template |
| 10. Two Master Questions | What variation within variables? What covariation between? |

**Tools** (6 total):
| Tool | Phase | What it does |
|---|---|---|
| `eda_profile` | Phase 1: Dataset Overview | Row/col counts, types, nulls, duplicates, quality score (0-100) |
| `eda_describe` | Phase 2: Univariate | Stats per column: mean, median, std, quartiles, skewness (with label + action), kurtosis (heavy-tail flag), IQR outlier detection |
| `eda_correlations` | Phase 3: Bivariate | Correlation matrix with strength labels (negligible/weak/moderate/strong/very strong), multicollinearity flags (|r|>0.8) |
| `eda_value_counts` | Phase 2: Univariate | Frequency distributions, imbalance detection (>80%), binary flag, rare category detection (<1%) |
| `eda_data_quality` | Phase 1: Dataset Overview | Mixed types, duplicates, MCAR/MAR/MNAR classification per column, severity-ranked issues |
| `eda_smart_structure` | Data Preparation | Auto-fix: normalize headers, coerce types, flatten JSON, extract text features, convert dates. Logs every change. |

**Utility functions in knowledge base**:
- `get_correlation_label(r)` → "negligible" / "weak" / "moderate" / "strong" / "very strong"
- `get_skewness_assessment(skew)` → label + recommended action
- `get_outlier_assessment(values)` → IQR-based detection with mild/extreme counts
- `classify_missingness(null_pct, is_concentrated)` → MCAR/MAR/MNAR type + treatment

**Edge cases tested and passing**:
- Empty dataset (0 rows)
- Large dataset (150K rows → sampling note)
- All-null columns → classified as "consider_drop"
- Imbalanced categorical (>80% single value) → detected with oversampling recommendation
- Binary column → detected as segmentation candidate
- Skewed distributions → correctly labeled with transformation suggestions
- Outlier detection → IQR fences, mild/extreme counts, "investigate before removing" guidance

### 3.2 Visualization Specialist (`specialists/viz.py`)

**Status**: Built, tested, all edge cases passing.

**Knowledge base**: `knowledge/viz_knowledge.py` — comprehensive framework based on
Edward Tufte's principles.

| Domain | Content |
|---|---|
| Tufte's Core Principles | Data-ink ratio, 5 Tufte rules, graphical integrity, Lie Factor, small multiples |
| Chart Selection Rules | 11 goal-to-chart mappings + 5 anti-patterns (3D charts, pie >5, dual Y-axis, donut, truncated Y) |
| Clarity & Simplicity | One chart one message, 5-second rule, remove before adding, no legend if avoidable, minimal color |
| Color Principles | Sequential/diverging/categorical palettes, max 7 colors, colorblind-safe (Plotly safe palette), never color as only differentiator |
| Audience-First Design | 4 tiers: Executive (KPIs, sparklines), Manager (trends, benchmarks), Analyst (dense, interactive), Public (familiar charts, annotated) |
| Exploratory vs Explanatory | Purpose, style, tools differ. Rule: never show exploratory to executives |
| Labeling & Annotation | Units on axes, insight-driven titles, annotate outliers, cite sources, round numbers |
| Scale & Proportion | Bar Y-axis must start at zero, line can start non-zero, consistent scales, log scales labeled |
| Analytics Viz Ladder | Descriptive→bar/line/KPI, Diagnostic→scatter/waterfall, Predictive→forecast/confidence, Prescriptive→scenario/decision |

**Tools** (8 total):
| Tool | What it does |
|---|---|
| `viz_bar_chart` | Y-axis at zero enforced, direct labels, sorting |
| `viz_line_chart` | Time trends, multiple series, markers |
| `viz_scatter_plot` | Correlations, optional color/size, trend lines |
| `viz_histogram` | Auto-bins, consistent bin sizes |
| `viz_box_plot` | Distribution comparison across categories, outlier display |
| `viz_heatmap` | Correlation matrices (diverging) or pivot tables (sequential) |
| `viz_pie_chart` | Part-to-whole, guardrail: max 5 segments (groups rest into "Other") |
| `viz_recommend` | Meta-tool: suggests best chart, tool, and palette based on goal + column types |

**Edge cases tested and passing**:
- Bar chart Y-axis always starts at zero
- Pie chart >5 segments → auto-groups into "Other"
- Scatter plot handles null values gracefully
- Single-value histogram doesn't crash
- Recommend tool returns valid suggestions
- Line chart with dates
- Correlation heatmap
- Box plot with grouping
- Column-not-found → clear error message

### 3.3 SQL Specialist (`specialists/sql.py`)

**Status**: Built, tested, all edge cases passing.

**Knowledge base**: `knowledge/sql_knowledge.py` — 13-section SQL analytical mastery framework.

| Section | Content |
|---|---|
| 1. Foundational Philosophy | SQL as analytical language, priority: correctness → readability → performance |
| 2. Formatting & Style | UPPERCASE keywords, snake_case identifiers, one column per line, meaningful aliases |
| 3. Query Execution Order | FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT |
| 4. CTE Hierarchy | When to use CTEs, naming after contents, sequential chaining, materialisation |
| 5. Window Functions | 3 categories (Ranking, Value, Aggregate), ROW_NUMBER vs RANK vs DENSE_RANK, 5 common patterns |
| 6. JOIN Principles | ANSI-92 syntax, 6 scenario→JOIN mappings, avoid RIGHT JOIN, qualify columns |
| 7. Performance Optimisation | Index awareness (no functions on indexed cols), filter early, EXPLAIN reading guide |
| 8. Aggregation Patterns | GROUP BY rules, conditional aggregation (CASE WHEN), safe ratios (NULLIF), percentage breakdown |
| 9. NULL Handling | IS NULL not = NULL, COUNT(*) vs COUNT(col), COALESCE, NULLIF for division |
| 10. Analytical SQL Patterns | 8 templates: cohort, retention/churn, funnel, period-over-period, running total, top-N, moving average, deduplication |
| 11. Anti-Patterns | 11 anti-patterns with regex detection: SELECT *, correlated subqueries, leading wildcards, = NULL, RIGHT JOIN, nested subqueries, ORDER BY in CTE |
| 12. Commenting Standard | Header block template (purpose, dependencies, notes) |
| 13. Dialect Differences | PostgreSQL, BigQuery, MySQL, SQL Server, DuckDB — 5 feature comparisons |

**Tools** (5 total):
| Tool | What it does |
|---|---|
| `sql_schema` | Shows loaded datasets as SQL CREATE TABLE statements (column names, SQL types, null rates, samples) |
| `sql_execute` | Executes SQL against loaded datasets via DuckDB (full SQL: CTEs, window functions, JOINs). Auto-checks for anti-patterns. Supports save_as for downstream analysis. |
| `sql_validate` | Validates SQL against 11 anti-patterns + style standards without executing. Returns categorised findings with severity and fix recommendations. |
| `sql_template` | Lists or returns ready-to-use SQL templates for 8 common analytics patterns with placeholder substitution. |
| `sql_format` | Formats SQL: UPPERCASE keywords, proper indentation. Also runs anti-pattern and style checks. |

**Execution engine**: DuckDB in-process — every pandas DataFrame in AnalysisContext is registered as a queryable table.

**Utility functions in knowledge base**:
- `detect_anti_patterns(sql)` → regex-based scan against 11 anti-patterns
- `validate_sql_style(sql)` → checks keyword casing, column layout, RIGHT JOIN usage
- `get_template(pattern_name, **kwargs)` → returns SQL template with placeholder substitution
- `get_available_templates()` → list of all 8 analytics templates
- `get_join_recommendation(scenario)` → suggests JOIN type
- `get_dialect_equivalent(feature, dialect)` → cross-dialect syntax lookup
- `pandas_dtype_to_sql(dtype)` → maps pandas dtype to SQL type

**Edge cases tested and passing**:
- No datasets loaded → clear error
- Unknown dataset → "not found" with available table list
- Syntax errors → DuckDB error with helpful hint
- Unknown table → hint to check sql_schema
- Special characters in dataset_id → quoted identifier support
- Large results (5000 rows) → truncated to 1000 with `has_more_rows` flag
- Cross-table JOINs between multiple loaded datasets
- NULL handling in results (NULL → None)
- Anti-pattern warnings alongside successful execution
- Window functions (RANK, LAG) execute correctly
- CTE queries execute correctly
- Conditional aggregation (CASE WHEN) works
- Division by zero → DuckDB returns inf (not error)
- Template placeholder substitution + unfilled placeholder detection
- Formatted SQL improves style issue count

### 3.4 Statistical Analysis Specialist (`specialists/stats.py`)

**Status**: Built, tested, all edge cases passing.

**Knowledge base**: `knowledge/stats_knowledge.py` — 13-section statistical analysis framework.

| Section | Content |
|---|---|
| 1. Foundational Philosophy | 3 questions (real? big? certain?), p-value definition + 4 misinterpretations, "absence of evidence ≠ evidence of absence" |
| 2. Hypothesis Testing | 5-step process (H₀ → α → assumptions → test → interpret), one/two-tailed rules, Type I/II errors + tradeoff |
| 3. Effect Size | Cohen's d (0.2/0.5/0.8/1.0), r (0.1/0.3/0.5), η² (0.01/0.06/0.14), OR interpretation, business translation rule |
| 4. Test Selection Guide | Decision tree: data type → groups → parametric/nonparametric. Covers t-test, ANOVA, Mann-Whitney, Kruskal-Wallis, Chi-squared, Fisher's, McNemar's |
| 5. Assumptions | Normality (Shapiro-Wilk/KS), equal variance (Levene's), independence. Transformation guide (log, sqrt, Box-Cox) |
| 6. Confidence Intervals | Correct interpretation, direction/precision/significance, reporting standard |
| 7. Power & Sample Size | 4 factors, rules of thumb (d=0.2→394/group, d=0.5→64/group, d=0.8→26/group), pre-experiment only |
| 8. A/B Testing | Pre/during/post checklists, SRM check, MDE, 5 common mistakes |
| 9. Multiple Comparisons | Bonferroni, Holm, FDR, Tukey HSD selection guide. 6 p-hacking patterns to flag |
| 10. Regression | Linear (LINE assumptions, R², VIF) + Logistic (AUC, odds ratios, confusion matrix). 5 anti-patterns |
| 11. Descriptive Standards | Mean(SD) for normal, Median[IQR] for skewed, n(%) for categorical, p(CI) for binary |
| 12. Anti-Patterns | 10 patterns: p without effect size, "no effect" from non-sig, early stopping, correlation=causation, etc. |
| 13. Communicating Statistics | Plain English translation table (8 terms), 3-sentence summary structure |

**Tools** (5 total):
| Tool | What it does |
|---|---|
| `stats_test` | Auto-selects and runs hypothesis test (t-test, Welch's, ANOVA, Mann-Whitney, Kruskal-Wallis). Checks assumptions first. Returns p-value + effect size + CI + interpretation. |
| `stats_regression` | Linear or logistic regression with full diagnostics: coefficients, R²/AUC, VIF multicollinearity check, residual normality, confidence intervals. |
| `stats_ab_test` | A/B test evaluation: uplift %, p-value, 95% CI, Cohen's d, SRM check, practical significance vs MDE. |
| `stats_power` | Sample size calculation or power calculation. Supports means (Cohen's d) and proportions (baseline rate). |
| `stats_assumptions` | Normality (Shapiro-Wilk/KS), equal variance (Levene's), transformation suggestions, test recommendation. |

**Utility functions in knowledge base**:
- `interpret_p_value(p, alpha)` → significance, strength label, interpretation, caveats
- `interpret_effect_size(metric, value)` → small/medium/large/very large label
- `interpret_ci(estimate, lower, upper)` → direction, significance, precision
- `select_test(data_type, n_groups, paired, normality_ok, n_samples)` → recommended test
- `get_required_sample_size(effect_size, alpha, power)` → n per group
- `get_correction_recommendation(n_tests)` → Bonferroni/Holm/FDR recommendation
- `get_descriptive_recommendation(is_normal, data_type)` → Mean(SD) vs Median[IQR]

**Edge cases tested and passing**:
- Two-group comparison (Welch's t-test with assumptions)
- One-sample t-test vs known population mean
- Multi-group ANOVA (3+ groups with η² effect size)
- Custom alpha levels
- Small sample auto-selects nonparametric
- A/B test with SRM check + MDE + group stats
- A/B test with insufficient groups → clear error
- Linear regression with VIF + residual normality
- Logistic regression with AUC + odds ratios + confusion matrix
- Auto-detect regression type from binary target
- Power calculation: sample size mode and power mode
- Proportions test with baseline rate
- Invalid effect size → error
- Skewed data → transformation suggestion
- Levene's test for grouped equal variance
- All 3 required outputs: p-value + effect size + CI

### 3.5 Data Cleaning & Transformation Specialist (`specialists/cleaning.py`)

**Status**: Built, tested, all edge cases passing.

**Knowledge base**: `knowledge/cleaning_knowledge.py` — 13-section data cleaning framework grounded in the three laws of data cleaning.

| Section | Content |
|---|---|
| 1. Foundational Philosophy | 3 laws (never modify source, document everything, validate before/after), mindset, cost of skipping |
| 2. Pipeline Sequence | 8-step standard order: Profile → Structural → Dedup → Missing → Outliers → Standardise → Derive → Validate |
| 3. Data Profiling | Shape, column-level metrics (nulls, distinct, min/max, most frequent), 7 red flags |
| 4. Structural Fixes | snake_case naming, type casting priorities (6 common mismatches), encoding/character issues |
| 5. Deduplication | 4 duplicate types (exact, key, fuzzy, cross-source), 5 resolution strategies, fuzzy matching guidance |
| 6. Missing Values | MCAR/MAR/MNAR classification, 9 treatment options, null % thresholds (5/20/50), indicator flags for MNAR |
| 7. Outlier Handling | 3 questions before acting, 5 decision types, capping/winsorisation, "never delete without documenting" |
| 8. Standardisation | Date (ISO 8601/UTC), numeric (separators, units, scaling), categorical (canonical mapping), text (whitespace, case) |
| 9. Derived Features | Time-based (tenure, recency, day-of-week), behavioral (RFM), financial (margins, running totals), encoding (one-hot, ordinal, target) |
| 10. Validation | 7 structural checks, business logic checks, distribution checks, failure protocol (log, quarantine, escalate) |
| 11. SQL Transformation Patterns | NULL handling, date/string/type transformations, conditional CASE, capping |
| 12. Anti-Patterns | 10 patterns: modifying source, silent drops, imputing without classifying, over-cleaning, no validation, etc. |
| 13. Quality Reporting | Data quality report template: initial profile, issues found, actions taken, post-cleaning profile, known limitations |

**Tools** (6 total):
| Tool | Pipeline Stage | What it does |
|---|---|---|
| `clean_structural` | Stage 2 | Normalise column names (snake_case), auto-detect/cast dates and numerics, apply manual type overrides, strip whitespace. Creates new dataset, never modifies original. |
| `clean_deduplicate` | Stage 3 | Detect exact or key-based duplicates. Strategies: keep_first, keep_last, keep_most_complete, flag_only. Always logs before/after row counts. |
| `clean_missing` | Stage 4 | Classify and handle missing values. Auto mode selects treatment per column based on null %, type, skewness. Supports: mean/median/mode imputation, drop, forward fill, indicator flag. Threshold-based column dropping (>50%). |
| `clean_standardise` | Stage 6 | Lowercase, trim whitespace, parse dates, strip numeric commas, normalise booleans, apply category mappings. Handles Pandas 3.x `str` dtype. |
| `clean_derive` | Stage 7 | Create derived features: date parts (year/month/day_of_week/is_weekend), days_since, numeric binning, threshold flags, text features (word/char count). |
| `clean_validate` | Stage 8 | Run structural + custom validation checks: row count, PK uniqueness, null rates, numeric ranges, date plausibility, in_set, not_null, min/max. Returns pass/fail per check with PASS/FAIL verdict. |

**Utility functions in knowledge base**:
- `normalise_column_name(name)` → converts to snake_case, strips special chars, handles edge cases
- `validate_column_name(name)` → checks naming standards, returns issues and suggested clean name
- `recommend_missing_treatment(null_pct, missingness_type, data_type, is_skewed)` → method + reason
- `recommend_dedup_strategy(has_timestamps, has_completeness_variation, is_transactional, business_logic_clear)` → strategy + reason
- `classify_column_issues(dtype, null_pct, unique_count, row_count, ...)` → list of red flags with severity
- `get_pipeline_next_step(completed_stages)` → what to do next in the 8-step pipeline

**Edge cases tested and passing**:
- Bad column headers → normalised to snake_case
- Auto date detection from string columns
- Auto numeric detection from string columns
- Manual type override (datetime, bool)
- Exact and key-based deduplication
- Flag-only mode (no removal, just tagging)
- Keep-most-complete strategy (fewest NULLs wins)
- No duplicates → no changes
- Missing column in subset → clear error
- All-null column → auto-dropped when above threshold
- Imputation: mean, median, mode, forward fill, flag only
- No nulls in data → no actions
- Standardisation: lowercase, trim, parse dates, strip numeric commas, normalise booleans
- Category mapping with Pandas 3.x str dtype
- Date parts extraction (year, month, day_of_week, is_weekend)
- Days-since calculation with reference date
- Numeric binning with labels
- Threshold-based flags
- Text feature extraction (word count, char count)
- Multiple derivations in single call
- Unknown derivation type → graceful skip
- PK uniqueness validation (pass and fail)
- Expected row count validation (pass and fail)
- Custom rules: not_null, unique, min, max, in_set, no_future_dates
- Null rate flagging (>20% = HIGH)
- Full 6-tool pipeline run in sequence
- Empty dataset structural fix
- Single-row deduplication

### 3.6 Additional Frameworks (`knowledge/frameworks.py`)

Contains CRISP-DM, SEMMA, Analytics Maturity Ladder, and Insight Communication Standard
as structured dictionaries. Originally used as EDA backbone — now retained for reference
and cross-specialist use (the Analytics Maturity Ladder is still referenced in the planner).

---

## 4. Prompts (`prompts.py`)

| Prompt | Purpose | Key references |
|---|---|---|
| `SUPERVISOR_SYSTEM_PROMPT` | Main analyst persona | Tukey's philosophy, 5-phase EDA, SQL analytics, statistical rigour, data cleaning pipeline, MCAR/MAR/MNAR, anti-patterns |
| `PLANNER_PROMPT` | Creates analysis plan (JSON) | Analytics maturity ladder, 5-phase EDA, data cleaning (step 6), SQL/stats/viz tool selection |
| `REFLECTOR_PROMPT` | Evaluates results | EDA process completeness (5 phases), anti-pattern check, Insight Communication Standard (6 criteria) |
| `SYNTHESIZER_PROMPT` | Final narrative for user | Lead with answer, precise numbers with context, acknowledge limitations, suggest next steps |

---

## 5. Key Design Decisions (Chronological)

| # | Decision | Rationale |
|---|---|---|
| 1 | Python/FastAPI + Next.js/React | User choice. FastAPI for async, Next.js for modern frontend. |
| 2 | Anthropic Claude as LLM | User choice. Claude for structured output, long context. |
| 3 | Hybrid multi-agent (single agent, designed for multi) | Start simple (ToolMode specialists), but `BaseSpecialist` abstraction allows upgrading to AgentMode without refactoring. |
| 4 | Plan-Execute-Reflect loop | Industry-standard agentic pattern. Planner creates structured JSON plan, Executor dispatches, Reflector evaluates. |
| 5 | Embedded knowledge bases (not vector DB) | Knowledge is domain-specific and finite. Injected directly into prompts and tool logic — no retrieval latency, no embedding drift. |
| 6 | EDA knowledge: Tukey-based (replaced CRISP-DM/SEMMA hybrid) | User provided comprehensive Tukey framework. More EDA-pure than CRISP-DM which is broader (includes modeling/deployment). CRISP-DM retained in frameworks.py for reference. |
| 7 | Viz knowledge: Tufte-based | User provided comprehensive Tufte principles. Enforced at tool level (e.g., bar Y-axis at zero, pie max 5 segments). |
| 8 | MCAR/MAR/MNAR missingness classification | User's Tukey framework requires classifying missingness before treatment. Implemented as utility function. |
| 9 | IQR outlier detection with "investigate before removing" | Tukey framework: never auto-delete outliers. Tool returns assessment text with this guidance. |
| 10 | Correlation strength labels (5-level) | Standardized: negligible (<0.2), weak (0.2-0.4), moderate (0.4-0.6), strong (0.6-0.8), very strong (>0.8). |
| 11 | Backend-first development | User confirmed: build backend solid with all tests passing before touching frontend. |
| 12 | Error recovery middleware between Executor and Specialists | Retry with exponential backoff for transient failures, circuit breaker per specialist (3 failures = open), error classification (5 categories), fallback tool suggestions, error context fed to reflector. |
| 13 | SQL Specialist with DuckDB execution engine | DuckDB queries pandas DataFrames directly with full SQL support (CTEs, window functions, JOINs). No external database needed for Phase 1. 13-section knowledge base covers style, performance, analytical patterns, anti-pattern detection. |
| 14 | Statistical Analysis Specialist with scipy/statsmodels | Full hypothesis testing framework: 5-step process, auto test selection, effect size + CI always paired with p-value. A/B test evaluation with SRM check. Regression with VIF diagnostics. Power analysis for experiment planning. |
| 15 | Data Cleaning & Transformation Specialist | 8-step auditable pipeline. Three laws (never modify source, document everything, validate before/after). MCAR/MAR/MNAR-aware missing handling. Handles Pandas 3.x str dtype. Category mapping, auto date/numeric detection, full validation suite. |
| 16 | Intent-based routing (4 execution modes) | DIRECT (0 LLM calls) for known single-tool requests, FOCUSED (2 calls) for scoped tasks, FULL (3-5 calls) for open exploration, CONVERSATIONAL (1+ calls) for follow-ups. Rule-based classification — zero latency, zero cost. Saves 2-4 LLM calls per request on common use cases. |

---

## 6. File Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI app entry point
│   ├── config.py                        # Settings (Pydantic BaseSettings)
│   ├── models/
│   │   └── schemas.py                   # Pydantic models for API
│   ├── api/
│   │   ├── middleware.py                # Request logging, error handling
│   │   └── routes/
│   │       ├── chat.py                  # Chat/analysis endpoint
│   │       ├── data.py                  # File upload endpoint
│   │       └── sessions.py             # Session management
│   ├── agent/
│   │   ├── __init__.py                  # create_supervisor() factory
│   │   ├── intent.py                   # Intent classifier (16 intents → 4 execution modes)
│   │   ├── supervisor.py               # Main orchestrator (intent-routed execution)
│   │   ├── planner.py                  # AnalysisPlan, AnalysisStep dataclasses + LLM planning
│   │   ├── executor.py                 # Step execution via ErrorRecoveryMiddleware
│   │   ├── error_recovery.py           # Retry, circuit breaker, error classification, fallback
│   │   ├── reflector.py                # Result evaluation + error context + follow-up decisions
│   │   ├── memory.py                   # Conversation/analysis memory
│   │   ├── prompts.py                  # All system prompts (Tukey + Tufte grounded)
│   │   ├── knowledge/
│   │   │   ├── __init__.py             # Exports all knowledge modules
│   │   │   ├── eda_knowledge.py        # 10-section Tukey EDA framework + utility functions
│   │   │   ├── viz_knowledge.py        # Tufte visualization framework + utility functions
│   │   │   ├── sql_knowledge.py        # 13-section SQL analytical mastery framework
│   │   │   ├── stats_knowledge.py       # 13-section statistical analysis framework
│   │   │   ├── cleaning_knowledge.py   # 13-section data cleaning & transformation framework
│   │   │   └── frameworks.py           # CRISP-DM, SEMMA, Analytics Maturity Ladder (reference)
│   │   └── specialists/
│   │       ├── __init__.py             # Exports all 5 specialists
│   │       ├── base.py                 # BaseSpecialist, SpecialistMode, SpecialistResult, SpecialistRegistry
│   │       ├── context.py              # AnalysisContext (shared state: datasets, results, variables)
│   │       ├── eda.py                  # EDA specialist (6 tools, Tukey knowledge)
│   │       ├── sql.py                  # SQL specialist (5 tools, DuckDB execution)
│   │       ├── stats.py                # Statistical analysis specialist (5 tools, scipy/statsmodels)
│   │       ├── cleaning.py             # Data cleaning specialist (6 tools, 8-step pipeline)
│   │       └── viz.py                  # Visualization specialist (8 tools, Tufte knowledge)
│   ├── connectors/
│   │   └── file_connector.py           # CSV/Excel/JSON/Parquet parsing
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── validator.py                # Input validation
│   │   ├── sanitizer.py                # Output sanitization
│   │   ├── rate_limiter.py             # Per-session LLM call limits
│   │   └── confirmation.py             # Human-in-the-loop
│   └── observability/
│       ├── __init__.py
│       ├── logger.py                   # structlog config
│       ├── metrics.py                  # Latency, token, tool tracking
│       └── events.py                   # Typed streaming events
├── requirements.txt
├── uploads/                            # Uploaded data files
└── .venv/                              # Python virtual environment
```

---

## 7. Pending Work (Phase 1 Remaining)

### Backend tasks:
- [x] **Error recovery middleware** — retry with backoff, circuit breaker, error classification, fallback suggestions, error context to reflector
- [x] **Unit tests (pytest)** — 635 tests across 14 test files, all passing
- [x] **Intent classifier & smart routing** — 4 execution modes (DIRECT/FOCUSED/FULL/CONVERSATIONAL) to minimize LLM cost

### Frontend tasks (deferred — backend-first):
- [ ] **Next.js setup** — Tailwind, app layout, API client, WebSocket hook
- [ ] **Chat UI** — message bubbles with reasoning steps, specialist indicators, streaming, code blocks
- [ ] **Data upload UI** — drag-and-drop, dataset list, table preview, schema viewer
- [ ] **Chart renderer** — Plotly.js interactive charts in chat
- [ ] **WebSocket streaming** — typed events between frontend and backend

### Future phases (not started):
- Phase 2: Code execution sandbox, database connectors
- Phase 3: Cloud data warehouse connectors, predictive modeling specialist
- Phase 4: Multi-agent upgrade (specialists as full sub-agents with own LLM instances)

---

## 8. Configuration

**Settings** (`config.py`):
- Model: `claude-sonnet-4-20250514`
- Max upload: 100 MB
- Allowed files: csv, xlsx, xls, json, parquet
- Max LLM calls/session: 50
- Max specialist calls/turn: 15
- Specialist timeout: 60s
- CORS origins: localhost:3000
- Database: SQLite (sessions)

---

## 9. Testing History

All tests run inline via Python scripts (no pytest suite yet — that's pending).

| Date | What was tested | Result |
|---|---|---|
| Phase 1 build | EDA specialist: profile, describe, correlations, value_counts, data_quality, smart_structure | All passed |
| Phase 1 build | EDA edge cases: empty dataset, 150K rows, all-null columns, imbalanced categoricals, binary columns | All passed (1 fix: KeyError 'type' → 'inferred_type') |
| Phase 1 build | Viz specialist: bar, line, scatter, histogram, box, heatmap, pie, recommend | All passed |
| Phase 1 build | Viz edge cases: zero-axis, >5 segments, nulls, single-value, dates, column-not-found | All passed |
| EDA KB replace | Knowledge base: correlation labels, skewness assessment, outlier assessment, missingness classification | All passed |
| EDA KB replace | EDA specialist with new KB: all 6 tools + 6 edge cases | All passed |
| Error recovery | Error classification (6 categories), retry with backoff, circuit breaker, fallback suggestions, unknown tool, error context for reflector, reset, serialization, integration with real EDA specialist | All 10 tests passed |
| Full pytest suite | 222 tests across 7 files: knowledge (44), EDA specialist (34), viz specialist (17), error recovery (25), guardrails (32), file connector (12), context/memory (21) | All 222 passed in 2.1s |
| SQL specialist | SQL knowledge (48 tests): structure, anti-pattern detection, style validation, templates, join recommendation, dialect equivalents, dtype mapping. SQL specialist (44 tests): schema, execute, validate, template, format + edge cases (cross-table join, window functions, CTEs, truncation, special chars, NULL handling). | All 89 new tests passed. Total: 311 tests in 2.3s |
| Stats specialist | Stats knowledge (67 tests): structure, effect size interpretation, p-value interpretation, CI interpretation, test selection, sample size, correction recommendation, descriptive recommendation. Stats specialist (40 tests): hypothesis testing, regression (linear + logistic), A/B testing, power analysis, assumption checking + edge cases. | All 107 new tests passed. Total: 418 tests in 7.9s |
| Cleaning specialist | Cleaning knowledge (60 tests): structure (13 sections), enums, normalise_column_name, validate_column_name, recommend_missing_treatment, recommend_dedup_strategy, classify_column_issues, get_pipeline_next_step. Cleaning specialist (62 tests): structural (9), deduplicate (7), missing (10), standardise (7), derive (9), validate (14), edge cases (7). Pandas 3.x str dtype compatibility fixes. | All 128 new tests passed. Total: 546 tests in 3.1s |
| Intent classifier | 89 tests: DIRECT mode (16 tests — profile, quality, describe, correlations, value counts, schema, validate), FOCUSED mode (22 tests — EDA, SQL, stats, viz, cleaning, A/B, regression), FULL mode (8 tests — analyze, insights, deep dive, comprehensive, investigate, report), CONVERSATIONAL mode (7 tests — follow-ups with history), edge cases (11), parametrized cost routing (16). | All 89 new tests passed. Total: 635 tests in 3.1s |

---

## 10. Evolution Log

| Change | What happened | Why |
|---|---|---|
| v1 → v2 EDA KB | Replaced CRISP-DM/SEMMA hybrid with 10-section Tukey framework | User provided comprehensive Tukey-based knowledge. More EDA-pure, richer (MCAR/MAR/MNAR, IQR outliers, skewness labels, anti-patterns). |
| Phase labels | Changed from "Data Understanding (CRISP-DM Phase 2)" to "Phase 1: Dataset Overview" etc. | Aligned with Tukey's 5-phase process. Clearer, simpler. |
| Correlation output | Changed from "strong if >0.7 else moderate" to 5-level labels | Tukey framework uses standard academic strength guide. |
| Describe output | Added skewness_label, skewness_action, heavy_tailed flag, IQR outlier detection | Tukey framework requires shape diagnostics with actionable recommendations. |
| Data quality output | Added MCAR/MAR/MNAR classification per column | Tukey framework: classify missingness before treatment. |
| Value counts | Added rare category detection (<1%) | Tukey framework: flag rare categories for potential grouping. |
| Prompts | Supervisor, Planner, Reflector updated to reference Tukey's 5 phases, two master questions, anti-patterns | Alignment with new knowledge base. |
| Error recovery | Added ErrorRecoveryMiddleware between Executor and Specialists | Robust production-grade error handling: retry transient failures, circuit breaker prevents cascading failures, error classification guides recovery, fallback suggestions help supervisor re-plan. |
| Executor | Rewired to go through middleware for all tool calls (both plan-based and dynamic) | Every tool call now gets retry/circuit-breaker protection automatically. |
| Reflector | Accepts error_context parameter | Reflector can now evaluate whether errors impacted analysis completeness and suggest re-planning. |
| SQL Specialist | New specialist: sql_knowledge.py (13 sections), sql.py (5 tools), DuckDB execution engine | SQL analytical queries against loaded DataFrames — CTEs, window functions, JOINs, anti-pattern validation. |
| Error recovery | Added SQL tool fallbacks (sql_execute → sql_validate/sql_schema, etc.) | SQL tools now covered by circuit breaker and retry logic. |
| Prompts | Supervisor and Planner updated with SQL awareness | LLM knows to use sql_schema → sql_execute flow, CTE structuring, NULL handling, anti-pattern avoidance. |
| requirements.txt | Added duckdb>=1.1.0 | In-process SQL engine for querying pandas DataFrames. |
| Stats Specialist | New specialist: stats_knowledge.py (13 sections), stats.py (5 tools), scipy + statsmodels | Hypothesis testing, regression, A/B tests, power analysis, assumption checking — always reports p + effect size + CI. |
| Error recovery | Added stats tool fallbacks (stats_test → stats_assumptions, etc.) | Stats tools now covered by circuit breaker and retry logic. |
| Prompts | Supervisor and Planner updated with statistical rigour section | LLM knows 5-step hypothesis framework, assumption checking, A/B testing standards. |
| Cleaning Specialist | New specialist: cleaning_knowledge.py (13 sections), cleaning.py (6 tools), 8-step pipeline | Full auditable cleaning pipeline: structural fixes, deduplication, missing values (MCAR/MAR/MNAR), standardisation, derived features, validation. Three laws enforced. |
| Error recovery | Added cleaning tool fallbacks (clean_structural → eda_profile, clean_missing → clean_structural, etc.) | Cleaning tools now covered by circuit breaker and retry logic. |
| Prompts | Supervisor and Planner updated with data cleaning pipeline section | LLM knows 8-step pipeline, three laws, missingness classification, validation requirements. |
| Pandas 3.x compat | Fixed string column detection across cleaning specialist | Pandas 3.x uses `str` dtype instead of `object`. Added `_is_string_col()` and `_string_columns()` helpers, fixed `operations: []` vs `None` distinction. |
| Intent classifier | New: intent.py with 16 UserIntents, 4 ExecutionModes, rule-based IntentClassifier | Eliminates wasted LLM calls. "Profile my data" → 0 calls (was 4). "Write SQL" → 2 calls (was 4). Only open exploration uses full loop. |
| Supervisor rewrite | Rewrote supervisor.py to route via intent classification | 4 execution paths: _run_direct, _run_focused, _run_full, _run_conversational. Each path invokes only the components it needs. |
| StreamEventType | Added INTENT event type | Frontend can display which mode was selected and why. |
| Prompts | Added FOCUSED_SYNTHESIS_PROMPT | Lightweight 3-8 sentence summary for FOCUSED mode (vs full narrative for FULL mode). |
| Memory | Added has_history property | Intent classifier uses conversation history to boost follow-up signal confidence. |
