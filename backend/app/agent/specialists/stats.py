"""
Statistical Analysis Specialist — hypothesis testing, regression, A/B tests in ToolMode.

Every statistical analysis must answer three questions:
1. Is the effect real? (Hypothesis testing — p-value)
2. How big is the effect? (Effect size — Cohen's d, r, η²)
3. How certain are we? (Confidence intervals — plausible range)

Core principle: Never report p-value alone. Always pair with effect size + CI.

Knowledge framework covers 13 domains:
 1. Foundational Philosophy (3 questions, p-value meaning)
 2. Hypothesis Testing (5-step process, Type I/II errors)
 3. Effect Size (Cohen's d, r, η², OR thresholds, business translation)
 4. Test Selection Guide (parametric vs non-parametric decision tree)
 5. Assumptions (normality, equal variance, independence, transformations)
 6. Confidence Intervals (interpretation, reporting standard)
 7. Power & Sample Size (4 factors, rules of thumb)
 8. A/B Testing Standards (pre/during/post checklist, common mistakes)
 9. Multiple Comparisons (Bonferroni, Holm, FDR, p-hacking patterns)
10. Regression (linear + logistic, LINE assumptions, anti-patterns)
11. Descriptive Statistics Standards (mean(SD) vs median[IQR] by data type)
12. Anti-Patterns (12 patterns)
13. Communicating to Non-Technical Audiences (translation table)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import structlog
from scipy import stats as sp_stats

from app.agent.knowledge.stats_knowledge import (
    STATS_KNOWLEDGE,
    get_correction_recommendation,
    get_descriptive_recommendation,
    get_required_sample_size,
    interpret_ci,
    interpret_effect_size,
    interpret_p_value,
    select_test,
)
from app.agent.specialists.base import (
    BaseSpecialist,
    ResultType,
    SpecialistMode,
    SpecialistResult,
)
from app.agent.specialists.context import AnalysisContext

logger = structlog.get_logger(__name__)


class StatsSpecialist(BaseSpecialist):
    name = "stats"
    description = (
        "Statistical analysis specialist. Runs hypothesis tests (t-test, ANOVA, "
        "chi-squared, Mann-Whitney, Wilcoxon), checks assumptions (normality, "
        "equal variance), computes effect sizes (Cohen's d, η², odds ratios), "
        "performs linear and logistic regression with diagnostics, evaluates A/B "
        "tests with full reporting (p-value + effect size + CI + business impact), "
        "and calculates sample size / power. Never reports p-value alone."
    )
    mode = SpecialistMode.TOOL
    timeout_seconds = 30
    system_prompt = (
        "You are the statistical analysis specialist of a data analyst digital twin. "
        "Every analysis must answer three questions: Is the effect real? How big? How certain? "
        "Never report p-value alone — always pair with effect size and confidence interval. "
        "Follow the 5-step hypothesis testing framework: state hypotheses → set α → check "
        "assumptions → calculate → interpret with context. Use non-parametric tests when "
        "n < 30 and normality is violated. For A/B tests, check SRM, report uplift + CI + "
        "projected business impact. Flag p-hacking patterns. Translate all statistics to "
        "plain English for stakeholders."
    )

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "stats_test",
                "description": (
                    "Run a hypothesis test on loaded data. Auto-selects the appropriate test "
                    "based on data type, number of groups, and assumption checks. Follows the "
                    "5-step framework: H₀/H₁ → α → assumptions → test statistic → interpretation. "
                    "Returns p-value + effect size + 95% CI + plain English interpretation. "
                    "Supports: t-test (one-sample, independent, paired, Welch's), ANOVA, "
                    "Mann-Whitney U, Wilcoxon, Kruskal-Wallis, Chi-squared, Fisher's exact. "
                    "Checks normality (Shapiro-Wilk/KS) and equal variance (Levene's) automatically."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "column": {"type": "string", "description": "Primary variable to test."},
                        "group_column": {
                            "type": "string",
                            "description": "Grouping variable (for comparing groups). Omit for one-sample test.",
                        },
                        "test_type": {
                            "type": "string",
                            "enum": ["auto", "ttest", "anova", "chi_squared", "mann_whitney", "wilcoxon", "kruskal_wallis"],
                            "description": "Specific test to run. Default: 'auto' (selects based on data).",
                        },
                        "alpha": {"type": "number", "description": "Significance level. Default: 0.05."},
                        "alternative": {
                            "type": "string",
                            "enum": ["two-sided", "less", "greater"],
                            "description": "Alternative hypothesis direction. Default: two-sided.",
                        },
                        "population_mean": {
                            "type": "number",
                            "description": "Known population mean for one-sample t-test.",
                        },
                    },
                    "required": ["dataset_id", "column"],
                },
            },
            {
                "name": "stats_regression",
                "description": (
                    "Run linear or logistic regression. Returns coefficients with p-values, "
                    "R² (linear) or AUC (logistic), assumption diagnostics (LINE for linear), "
                    "VIF for multicollinearity (flags > 5), residual analysis, and confidence "
                    "intervals for all coefficients. Checks regression anti-patterns: "
                    "multicollinearity, residual patterns, adjusted R² for model comparison."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "target": {"type": "string", "description": "Dependent variable (Y)."},
                        "predictors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Independent variables (X). If empty, uses all numeric columns except target.",
                        },
                        "regression_type": {
                            "type": "string",
                            "enum": ["linear", "logistic"],
                            "description": "Type of regression. Default: auto-detected from target variable.",
                        },
                    },
                    "required": ["dataset_id", "target"],
                },
            },
            {
                "name": "stats_ab_test",
                "description": (
                    "Evaluate an A/B test result. Computes: uplift %, p-value, 95% CI, "
                    "effect size, and projected business impact. Checks for Sample Ratio "
                    "Mismatch (SRM). Reports whether the result is both statistically and "
                    "practically significant. Follows the A/B testing standards: one primary "
                    "metric, no peeking, pre-specified MDE. Flags common A/B testing mistakes."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "group_column": {"type": "string", "description": "Column that identifies control/treatment (e.g. 'variant')."},
                        "metric_column": {"type": "string", "description": "Primary metric to compare (e.g. 'converted', 'revenue')."},
                        "control_label": {"type": "string", "description": "Label for control group. Default: auto-detected."},
                        "treatment_label": {"type": "string", "description": "Label for treatment group. Default: auto-detected."},
                        "mde": {"type": "number", "description": "Minimum Detectable Effect (absolute). Optional."},
                    },
                    "required": ["dataset_id", "group_column", "metric_column"],
                },
            },
            {
                "name": "stats_power",
                "description": (
                    "Calculate required sample size for a given effect size and power, or "
                    "calculate achieved power for a given sample size. Essential for experiment "
                    "planning. Standard target: 80% power. High-stakes: 90%. "
                    "Supports: two-sample t-test, proportions test. "
                    "Rule: Always calculate BEFORE running an experiment. Post-hoc power is misleading."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "effect_size": {
                            "type": "number",
                            "description": "Expected effect size (Cohen's d for means, absolute difference for proportions). Default: 0.5 (medium).",
                        },
                        "alpha": {"type": "number", "description": "Significance level. Default: 0.05."},
                        "power": {"type": "number", "description": "Desired power (1-β). Default: 0.80."},
                        "baseline_rate": {
                            "type": "number",
                            "description": "Baseline conversion rate (for proportion tests). E.g. 0.10 for 10%.",
                        },
                        "n_per_group": {
                            "type": "integer",
                            "description": "If provided, calculates achieved power instead of required n.",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "stats_assumptions",
                "description": (
                    "Check statistical assumptions for columns in a dataset. Tests: "
                    "normality (Shapiro-Wilk for n<50, Kolmogorov-Smirnov for n≥50), "
                    "equal variance (Levene's test across groups), independence guidance. "
                    "Suggests transformations when normality is violated (log, sqrt, Box-Cox). "
                    "Recommends parametric vs non-parametric tests. "
                    "Always run this before hypothesis testing — skipping assumptions invalidates results."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Columns to check. If empty, checks all numeric columns.",
                        },
                        "group_column": {
                            "type": "string",
                            "description": "Optional grouping variable for equal variance test.",
                        },
                    },
                    "required": ["dataset_id"],
                },
            },
        ]

    async def _execute_tool_mode(
        self, tool_name: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        dispatch = {
            "stats_test": self._hypothesis_test,
            "stats_regression": self._regression,
            "stats_ab_test": self._ab_test,
            "stats_power": self._power_analysis,
            "stats_assumptions": self._check_assumptions,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Unknown stats tool: {tool_name}",
                error=f"Unknown tool: {tool_name}",
            )

        return await handler(params, context)

    # ─── Tool Implementations ─────────────────────────────────────────

    async def _hypothesis_test(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._dataset_not_found(dataset_id, context)

        col = params.get("column", "")
        if col not in df.columns:
            return self._column_not_found(col, df)

        group_col = params.get("group_column")
        test_type = params.get("test_type", "auto")
        alpha = params.get("alpha", 0.05)
        alternative = params.get("alternative", "two-sided")
        pop_mean = params.get("population_mean")

        series = pd.to_numeric(df[col], errors="coerce").dropna()

        if group_col and group_col not in df.columns:
            return self._column_not_found(group_col, df)

        if group_col:
            groups = df.groupby(group_col)[col].apply(
                lambda s: pd.to_numeric(s, errors="coerce").dropna().tolist()
            ).to_dict()
            group_names = list(groups.keys())
            n_groups = len(group_names)
        else:
            groups = None
            group_names = []
            n_groups = 1

        # Step 3: Check assumptions
        assumptions: dict[str, Any] = {}
        if len(series) >= 3:
            normality = self._test_normality(series.values)
            assumptions["normality"] = normality

        if groups and n_groups == 2:
            group_arrays = [np.array(groups[g]) for g in group_names if len(groups[g]) >= 2]
            if len(group_arrays) == 2:
                lev_stat, lev_p = sp_stats.levene(*group_arrays)
                assumptions["equal_variance"] = {
                    "levene_statistic": round(float(lev_stat), 4),
                    "p_value": round(float(lev_p), 4),
                    "equal_variance": lev_p > 0.05,
                }

        normality_ok = assumptions.get("normality", {}).get("is_normal", True)
        n_min = min(len(series), min((len(groups[g]) for g in group_names), default=len(series))) if groups else len(series)

        # Step 4: Select and run test
        if test_type == "auto":
            if group_col is None and pop_mean is not None:
                data_type = "continuous"
                n_groups_for_select = 1
            elif group_col:
                unique_vals = df[group_col].nunique()
                if pd.api.types.is_numeric_dtype(series):
                    data_type = "continuous"
                    n_groups_for_select = unique_vals
                else:
                    data_type = "categorical"
                    n_groups_for_select = unique_vals
            else:
                data_type = "continuous"
                n_groups_for_select = 1

            recommendation = select_test(
                data_type=data_type,
                n_groups=n_groups_for_select,
                normality_ok=normality_ok,
                n_samples=n_min,
            )
            selected_test = recommendation["test"]
        else:
            selected_test = test_type

        # Execute the test
        test_result = self._run_test(
            selected_test, series, groups, group_names, alpha, alternative, pop_mean
        )

        if test_result is None:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Could not run test '{selected_test}'. Check data requirements.",
                error=f"Test execution failed: {selected_test}",
            )

        # Step 5: Interpret
        p_interp = interpret_p_value(test_result["p_value"], alpha)
        effect_interp = interpret_effect_size(
            test_result.get("effect_metric", "cohens_d"),
            test_result.get("effect_size", 0),
        ) if "effect_size" in test_result else {"label": "not computed", "interpretation": ""}

        result_data = {
            "dataset_id": dataset_id,
            "column": col,
            "group_column": group_col,
            "test_name": test_result["test_name"],
            "test_statistic": test_result.get("statistic"),
            "p_value": test_result["p_value"],
            "alpha": alpha,
            "significant": p_interp["significant"],
            "effect_size": test_result.get("effect_size"),
            "effect_metric": test_result.get("effect_metric"),
            "effect_label": effect_interp["label"],
            "ci_lower": test_result.get("ci_lower"),
            "ci_upper": test_result.get("ci_upper"),
            "assumptions": assumptions,
            "interpretation": p_interp["interpretation"],
            "effect_interpretation": effect_interp["interpretation"],
            "caveats": p_interp["caveats"],
            "group_stats": test_result.get("group_stats"),
        }

        sig_str = "significant" if p_interp["significant"] else "NOT significant"
        effect_str = f", {effect_interp['label']} effect" if effect_interp["label"] != "not computed" else ""
        ci_str = ""
        if test_result.get("ci_lower") is not None:
            ci_str = f" (95% CI: {test_result['ci_lower']:.4f}, {test_result['ci_upper']:.4f})"

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.STATISTIC, data=result_data,
            summary=(
                f"{test_result['test_name']}: p = {test_result['p_value']:.4f}, "
                f"{sig_str} at α = {alpha}{effect_str}{ci_str}. "
                f"{p_interp['strength']}."
            ),
            metadata={"tool": "stats_test"},
        )

    async def _regression(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        import statsmodels.api as sm
        from statsmodels.stats.outliers_influence import variance_inflation_factor

        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._dataset_not_found(dataset_id, context)

        target = params.get("target", "")
        if target not in df.columns:
            return self._column_not_found(target, df)

        predictors = params.get("predictors") or [
            c for c in df.select_dtypes(include=[np.number]).columns if c != target
        ]
        missing = [p for p in predictors if p not in df.columns]
        if missing:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Predictor columns not found: {missing}",
                error=f"Missing columns: {missing}",
            )

        if len(predictors) == 0:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary="No numeric predictor columns available.",
                error="No predictors",
            )

        reg_type = params.get("regression_type")
        y = df[target]

        is_binary = set(y.dropna().unique()).issubset({0, 1, True, False, 0.0, 1.0})
        if reg_type is None:
            reg_type = "logistic" if is_binary else "linear"

        sub = df[[target] + predictors].dropna()
        if len(sub) < len(predictors) + 2:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Not enough observations ({len(sub)}) for {len(predictors)} predictors.",
                error="Insufficient data",
            )

        Y = sub[target].astype(float)
        X = sub[predictors].astype(float)
        X_const = sm.add_constant(X)

        try:
            if reg_type == "logistic":
                model = sm.Logit(Y, X_const).fit(disp=0)
                coefficients = []
                for name, coef, pval in zip(X_const.columns, model.params, model.pvalues):
                    ci = model.conf_int().loc[name]
                    entry: dict[str, Any] = {
                        "variable": str(name),
                        "coefficient": round(float(coef), 4),
                        "odds_ratio": round(float(np.exp(coef)), 4),
                        "p_value": round(float(pval), 6),
                        "ci_lower": round(float(ci[0]), 4),
                        "ci_upper": round(float(ci[1]), 4),
                        "significant": float(pval) < 0.05,
                    }
                    coefficients.append(entry)

                y_pred_prob = model.predict(X_const)
                y_pred = (y_pred_prob >= 0.5).astype(int)
                tp = int(((y_pred == 1) & (Y == 1)).sum())
                fp = int(((y_pred == 1) & (Y == 0)).sum())
                tn = int(((y_pred == 0) & (Y == 0)).sum())
                fn = int(((y_pred == 0) & (Y == 1)).sum())

                auc = float(self._compute_auc(Y.values, y_pred_prob.values))

                result_data: dict[str, Any] = {
                    "regression_type": "logistic",
                    "coefficients": coefficients,
                    "auc": round(auc, 4),
                    "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
                    "accuracy": round((tp + tn) / len(Y), 4),
                    "n_observations": len(sub),
                    "n_predictors": len(predictors),
                    "pseudo_r_squared": round(float(model.prsquared), 4),
                    "log_likelihood": round(float(model.llf), 2),
                    "aic": round(float(model.aic), 2),
                }

                summary = (
                    f"Logistic regression: AUC = {auc:.3f}, "
                    f"pseudo-R² = {model.prsquared:.3f}, "
                    f"{len(predictors)} predictors, n = {len(sub)}. "
                    f"Accuracy = {(tp + tn) / len(Y):.1%}."
                )

            else:
                model = sm.OLS(Y, X_const).fit()
                coefficients = []
                for name, coef, pval in zip(X_const.columns, model.params, model.pvalues):
                    ci = model.conf_int().loc[name]
                    entry = {
                        "variable": str(name),
                        "coefficient": round(float(coef), 4),
                        "p_value": round(float(pval), 6),
                        "ci_lower": round(float(ci[0]), 4),
                        "ci_upper": round(float(ci[1]), 4),
                        "significant": float(pval) < 0.05,
                    }
                    coefficients.append(entry)

                # VIF check
                vif_data = []
                if len(predictors) > 1:
                    for i, pred in enumerate(predictors):
                        vif_val = float(variance_inflation_factor(X.values, i))
                        vif_data.append({
                            "variable": pred,
                            "vif": round(vif_val, 2),
                            "multicollinear": vif_val > 5,
                        })

                # Residual normality
                residuals = model.resid
                resid_normality = self._test_normality(residuals.values)

                result_data = {
                    "regression_type": "linear",
                    "coefficients": coefficients,
                    "r_squared": round(float(model.rsquared), 4),
                    "adj_r_squared": round(float(model.rsquared_adj), 4),
                    "f_statistic": round(float(model.fvalue), 4),
                    "f_p_value": round(float(model.f_pvalue), 6),
                    "n_observations": len(sub),
                    "n_predictors": len(predictors),
                    "aic": round(float(model.aic), 2),
                    "bic": round(float(model.bic), 2),
                    "vif": vif_data,
                    "residual_normality": resid_normality,
                    "diagnostics": [],
                }

                multicollinear = [v for v in vif_data if v["multicollinear"]]
                if multicollinear:
                    result_data["diagnostics"].append(
                        f"Multicollinearity warning: {', '.join(v['variable'] for v in multicollinear)} have VIF > 5"
                    )
                if not resid_normality.get("is_normal", True):
                    result_data["diagnostics"].append(
                        "Residuals are not normally distributed — coefficients may be unreliable"
                    )

                summary = (
                    f"Linear regression: R² = {model.rsquared:.3f}, "
                    f"Adj R² = {model.rsquared_adj:.3f}, "
                    f"F = {model.fvalue:.2f} (p = {model.f_pvalue:.4f}), "
                    f"{len(predictors)} predictors, n = {len(sub)}."
                    + (f" Warnings: {'; '.join(result_data['diagnostics'])}" if result_data["diagnostics"] else "")
                )

        except Exception as e:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Regression failed: {str(e)}",
                error=str(e),
            )

        result_data["dataset_id"] = dataset_id

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.STATISTIC, data=result_data,
            summary=summary,
            metadata={"tool": "stats_regression"},
        )

    async def _ab_test(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._dataset_not_found(dataset_id, context)

        group_col = params.get("group_column", "")
        metric_col = params.get("metric_column", "")

        for col in (group_col, metric_col):
            if col not in df.columns:
                return self._column_not_found(col, df)

        groups = df[group_col].dropna().unique()
        if len(groups) < 2:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Need at least 2 groups in '{group_col}', found {len(groups)}.",
                error="Insufficient groups",
            )

        control_label = params.get("control_label") or str(groups[0])
        treatment_label = params.get("treatment_label") or str(groups[1])
        mde = params.get("mde")

        control = pd.to_numeric(df[df[group_col] == control_label][metric_col], errors="coerce").dropna()
        treatment = pd.to_numeric(df[df[group_col] == treatment_label][metric_col], errors="coerce").dropna()

        if len(control) < 2 or len(treatment) < 2:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary="Both groups need at least 2 observations.",
                error="Insufficient data per group",
            )

        # SRM check
        expected_ratio = 0.5
        n_total = len(control) + len(treatment)
        observed_ratio = len(control) / n_total
        srm_chi2 = ((len(control) - n_total * expected_ratio) ** 2 / (n_total * expected_ratio) +
                     (len(treatment) - n_total * (1 - expected_ratio)) ** 2 / (n_total * (1 - expected_ratio)))
        srm_p = float(1 - sp_stats.chi2.cdf(srm_chi2, 1))
        srm_ok = srm_p > 0.01

        # Test
        t_stat, p_value = sp_stats.ttest_ind(treatment, control, equal_var=False)
        p_value = float(p_value)

        control_mean = float(control.mean())
        treatment_mean = float(treatment.mean())
        diff = treatment_mean - control_mean
        relative_uplift = diff / control_mean * 100 if control_mean != 0 else 0

        # Effect size (Cohen's d)
        pooled_std = math.sqrt(
            ((len(control) - 1) * control.std() ** 2 + (len(treatment) - 1) * treatment.std() ** 2)
            / (len(control) + len(treatment) - 2)
        )
        cohens_d = diff / pooled_std if pooled_std > 0 else 0

        # CI for the difference
        se_diff = math.sqrt(control.var() / len(control) + treatment.var() / len(treatment))
        z = sp_stats.norm.ppf(0.975)
        ci_lower = diff - z * se_diff
        ci_upper = diff + z * se_diff

        p_interp = interpret_p_value(p_value)
        effect_interp = interpret_effect_size("cohens_d", cohens_d)
        ci_interp = interpret_ci(diff, ci_lower, ci_upper)

        practical_significance = True
        if mde is not None:
            practical_significance = abs(diff) >= mde

        warnings_list: list[str] = []
        if not srm_ok:
            warnings_list.append(f"SRM detected (p = {srm_p:.4f}): sample ratio {observed_ratio:.3f} deviates from expected 0.5. Randomisation may be broken.")
        if not p_interp["significant"]:
            power_info = get_required_sample_size(abs(cohens_d) if cohens_d != 0 else 0.2)
            warnings_list.append(f"Not significant. Would need ~{power_info['n_per_group']} per group for 80% power.")
        if mde is not None and not practical_significance:
            warnings_list.append(f"Effect ({abs(diff):.4f}) below MDE ({mde}). Not practically significant.")

        result_data = {
            "dataset_id": dataset_id,
            "control": {"label": control_label, "n": len(control), "mean": round(control_mean, 4), "std": round(float(control.std()), 4)},
            "treatment": {"label": treatment_label, "n": len(treatment), "mean": round(treatment_mean, 4), "std": round(float(treatment.std()), 4)},
            "difference": round(diff, 4),
            "relative_uplift_pct": round(relative_uplift, 2),
            "p_value": round(p_value, 6),
            "significant": p_interp["significant"],
            "cohens_d": round(cohens_d, 4),
            "effect_label": effect_interp["label"],
            "ci_lower": round(ci_lower, 4),
            "ci_upper": round(ci_upper, 4),
            "srm_check": {"p_value": round(srm_p, 4), "ok": srm_ok, "observed_ratio": round(observed_ratio, 3)},
            "practical_significance": practical_significance,
            "mde": mde,
            "warnings": warnings_list,
        }

        sig_str = "SIGNIFICANT" if p_interp["significant"] else "NOT significant"
        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.STATISTIC, data=result_data,
            summary=(
                f"A/B Test: {treatment_label} vs {control_label}. "
                f"Uplift: {relative_uplift:+.2f}% (diff = {diff:+.4f}). "
                f"p = {p_value:.4f} — {sig_str}. "
                f"Cohen's d = {cohens_d:.3f} ({effect_interp['label']}). "
                f"95% CI: ({ci_lower:.4f}, {ci_upper:.4f}). "
                f"SRM: {'OK' if srm_ok else 'WARNING'}."
                + (f" Warnings: {'; '.join(warnings_list)}" if warnings_list else "")
            ),
            metadata={"tool": "stats_ab_test"},
        )

    async def _power_analysis(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        effect_size = params.get("effect_size", 0.5)
        alpha = params.get("alpha", 0.05)
        power = params.get("power", 0.80)
        baseline_rate = params.get("baseline_rate")
        n_per_group = params.get("n_per_group")

        if effect_size <= 0:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary="Effect size must be > 0.",
                error="Invalid effect_size",
            )

        if n_per_group:
            z_alpha = sp_stats.norm.ppf(1 - alpha / 2)
            noncentrality = effect_size * math.sqrt(n_per_group / 2)
            achieved_power = float(1 - sp_stats.norm.cdf(z_alpha - noncentrality))

            result_data: dict[str, Any] = {
                "mode": "calculate_power",
                "n_per_group": n_per_group,
                "total_n": n_per_group * 2,
                "effect_size": effect_size,
                "alpha": alpha,
                "achieved_power": round(achieved_power, 4),
                "adequate": achieved_power >= 0.80,
                "interpretation": (
                    f"With n = {n_per_group} per group and d = {effect_size}, "
                    f"achieved power = {achieved_power:.1%}. "
                    + ("Adequate (≥80%)." if achieved_power >= 0.80 else
                       f"UNDERPOWERED (<80%). Need more subjects.")
                ),
            }
            summary = (
                f"Power analysis: n = {n_per_group}/group, d = {effect_size} → "
                f"power = {achieved_power:.1%} "
                f"({'adequate' if achieved_power >= 0.80 else 'UNDERPOWERED'})."
            )
        else:
            if baseline_rate is not None:
                new_rate = baseline_rate + effect_size
                p_avg = (baseline_rate + new_rate) / 2
                es_prop = abs(effect_size) / math.sqrt(p_avg * (1 - p_avg)) if p_avg > 0 and p_avg < 1 else 0.5
                sample_info = get_required_sample_size(es_prop, alpha, power)
                sample_info["baseline_rate"] = baseline_rate
                sample_info["expected_new_rate"] = round(new_rate, 4)
                sample_info["test_type"] = "proportions"
            else:
                sample_info = get_required_sample_size(effect_size, alpha, power)
                sample_info["test_type"] = "two-sample t-test"

            result_data = {
                "mode": "calculate_sample_size",
                **sample_info,
            }
            summary = (
                f"Sample size: need {sample_info['n_per_group']} per group "
                f"({sample_info['total_n']} total) for d = {effect_size}, "
                f"α = {alpha}, power = {int(power * 100)}%."
            )

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.STATISTIC, data=result_data,
            summary=summary,
            metadata={"tool": "stats_power"},
        )

    async def _check_assumptions(
        self, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        dataset_id = params.get("dataset_id", "")
        df = context.datasets.get(dataset_id)
        if df is None:
            return self._dataset_not_found(dataset_id, context)

        columns = params.get("columns") or list(df.select_dtypes(include=[np.number]).columns)
        group_col = params.get("group_column")

        missing = [c for c in columns if c not in df.columns]
        if missing:
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary=f"Columns not found: {missing}",
                error=f"Missing columns: {missing}",
            )

        results: dict[str, Any] = {}
        recommendations: list[str] = []

        for col in columns:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) < 3:
                results[col] = {"error": "Too few values for assumption testing"}
                continue

            col_result: dict[str, Any] = {"n": len(series)}

            # Normality
            normality = self._test_normality(series.values)
            col_result["normality"] = normality

            if not normality.get("is_normal", True):
                skew = float(series.skew())
                if skew > 1:
                    col_result["suggested_transformation"] = "Log or Square root (right-skewed)"
                elif skew < -1:
                    col_result["suggested_transformation"] = "Square or Cube (left-skewed)"
                else:
                    col_result["suggested_transformation"] = "Box-Cox or non-parametric test"
                recommendations.append(f"{col}: not normal → use non-parametric test or transform")
            else:
                recommendations.append(f"{col}: normality OK → parametric tests appropriate")

            # Equal variance (if grouping variable)
            if group_col and group_col in df.columns:
                groups_data = []
                for grp_name, grp_df in df.groupby(group_col):
                    grp_vals = pd.to_numeric(grp_df[col], errors="coerce").dropna()
                    if len(grp_vals) >= 2:
                        groups_data.append(grp_vals.values)

                if len(groups_data) >= 2:
                    lev_stat, lev_p = sp_stats.levene(*groups_data)
                    equal_var = float(lev_p) > 0.05
                    col_result["equal_variance"] = {
                        "levene_statistic": round(float(lev_stat), 4),
                        "p_value": round(float(lev_p), 4),
                        "equal_variance": equal_var,
                    }
                    if not equal_var:
                        recommendations.append(f"{col}: unequal variance → use Welch's t-test")

            # Recommendation
            is_normal = normality.get("is_normal", True)
            n = len(series)
            test_rec = select_test("continuous", n_groups=2, normality_ok=is_normal, n_samples=n)
            col_result["recommended_test"] = test_rec

            results[col] = col_result

        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.TABLE, data={
                "dataset_id": dataset_id,
                "columns_checked": columns,
                "results": results,
                "recommendations": recommendations,
                "group_column": group_col,
            },
            summary=(
                f"Assumption checks for {len(columns)} column(s). "
                + " ".join(recommendations[:5])
            ),
            metadata={"tool": "stats_assumptions"},
        )

    # ─── Helper Methods ───────────────────────────────────────────────

    def _test_normality(self, values: np.ndarray) -> dict[str, Any]:
        """Run the appropriate normality test based on sample size."""
        n = len(values)
        if n < 3:
            return {"is_normal": None, "test": "insufficient data", "p_value": None}

        if n < 50:
            stat, p = sp_stats.shapiro(values[:5000])
            test_name = "Shapiro-Wilk"
        else:
            stat, p = sp_stats.kstest(values, "norm", args=(values.mean(), values.std()))
            test_name = "Kolmogorov-Smirnov"

        return {
            "test": test_name,
            "statistic": round(float(stat), 4),
            "p_value": round(float(p), 4),
            "is_normal": float(p) > 0.05,
            "n": n,
        }

    def _run_test(
        self,
        test_name: str,
        series: pd.Series,
        groups: dict | None,
        group_names: list,
        alpha: float,
        alternative: str,
        pop_mean: float | None,
    ) -> dict[str, Any] | None:
        """Execute a statistical test and return structured results."""

        scipy_alt = alternative if alternative != "two-sided" else "two-sided"

        if "t-test" in test_name.lower() or test_name == "ttest":
            if pop_mean is not None and groups is None:
                stat, p = sp_stats.ttest_1samp(series, pop_mean, alternative=scipy_alt)
                se = series.std() / math.sqrt(len(series))
                diff = series.mean() - pop_mean
                d = diff / series.std() if series.std() > 0 else 0
                ci_low = diff - sp_stats.t.ppf(0.975, len(series) - 1) * se
                ci_high = diff + sp_stats.t.ppf(0.975, len(series) - 1) * se
                return {
                    "test_name": "One-sample t-test",
                    "statistic": round(float(stat), 4),
                    "p_value": round(float(p), 6),
                    "effect_size": round(float(d), 4),
                    "effect_metric": "cohens_d",
                    "ci_lower": round(float(ci_low), 4),
                    "ci_upper": round(float(ci_high), 4),
                    "group_stats": {"mean": round(float(series.mean()), 4), "population_mean": pop_mean},
                }

            if groups and len(group_names) >= 2:
                g1 = np.array(groups[group_names[0]])
                g2 = np.array(groups[group_names[1]])
                stat, p = sp_stats.ttest_ind(g1, g2, equal_var=False, alternative=scipy_alt)
                diff = float(g1.mean() - g2.mean())
                pooled = math.sqrt(((len(g1) - 1) * g1.std() ** 2 + (len(g2) - 1) * g2.std() ** 2) / (len(g1) + len(g2) - 2))
                d = diff / pooled if pooled > 0 else 0
                se = math.sqrt(g1.var() / len(g1) + g2.var() / len(g2))
                ci_low = diff - 1.96 * se
                ci_high = diff + 1.96 * se
                return {
                    "test_name": "Welch's t-test",
                    "statistic": round(float(stat), 4),
                    "p_value": round(float(p), 6),
                    "effect_size": round(float(d), 4),
                    "effect_metric": "cohens_d",
                    "ci_lower": round(float(ci_low), 4),
                    "ci_upper": round(float(ci_high), 4),
                    "group_stats": {
                        str(group_names[0]): {"mean": round(float(g1.mean()), 4), "n": len(g1)},
                        str(group_names[1]): {"mean": round(float(g2.mean()), 4), "n": len(g2)},
                    },
                }

        if "mann" in test_name.lower() or test_name == "mann_whitney":
            if groups and len(group_names) >= 2:
                g1 = np.array(groups[group_names[0]])
                g2 = np.array(groups[group_names[1]])
                stat, p = sp_stats.mannwhitneyu(g1, g2, alternative=scipy_alt)
                r = 1 - (2 * stat) / (len(g1) * len(g2))
                return {
                    "test_name": "Mann-Whitney U",
                    "statistic": round(float(stat), 4),
                    "p_value": round(float(p), 6),
                    "effect_size": round(float(r), 4),
                    "effect_metric": "r",
                    "group_stats": {
                        str(group_names[0]): {"median": round(float(np.median(g1)), 4), "n": len(g1)},
                        str(group_names[1]): {"median": round(float(np.median(g2)), 4), "n": len(g2)},
                    },
                }

        if "anova" in test_name.lower() or test_name == "anova":
            if groups and len(group_names) >= 2:
                arrays = [np.array(groups[g]) for g in group_names if len(groups[g]) >= 2]
                if len(arrays) >= 2:
                    stat, p = sp_stats.f_oneway(*arrays)
                    grand_mean = np.concatenate(arrays).mean()
                    ss_between = sum(len(a) * (a.mean() - grand_mean) ** 2 for a in arrays)
                    ss_total = sum((a - grand_mean).var() * len(a) for a in arrays) + ss_between
                    eta_sq = ss_between / ss_total if ss_total > 0 else 0
                    return {
                        "test_name": "One-way ANOVA",
                        "statistic": round(float(stat), 4),
                        "p_value": round(float(p), 6),
                        "effect_size": round(float(eta_sq), 4),
                        "effect_metric": "eta_squared",
                        "group_stats": {
                            str(g): {"mean": round(float(np.mean(groups[g])), 4), "n": len(groups[g])}
                            for g in group_names
                        },
                    }

        if "kruskal" in test_name.lower() or test_name == "kruskal_wallis":
            if groups and len(group_names) >= 2:
                arrays = [np.array(groups[g]) for g in group_names if len(groups[g]) >= 2]
                if len(arrays) >= 2:
                    stat, p = sp_stats.kruskal(*arrays)
                    n_total = sum(len(a) for a in arrays)
                    eta_sq = (float(stat) - len(arrays) + 1) / (n_total - len(arrays))
                    return {
                        "test_name": "Kruskal-Wallis H-test",
                        "statistic": round(float(stat), 4),
                        "p_value": round(float(p), 6),
                        "effect_size": round(float(max(eta_sq, 0)), 4),
                        "effect_metric": "eta_squared",
                        "group_stats": {
                            str(g): {"median": round(float(np.median(groups[g])), 4), "n": len(groups[g])}
                            for g in group_names
                        },
                    }

        if "chi" in test_name.lower() or test_name == "chi_squared":
            if groups and len(group_names) >= 2:
                contingency = pd.crosstab(
                    pd.Series(np.concatenate([[g] * len(groups[g]) for g in group_names])),
                    pd.Series(np.concatenate([groups[g] for g in group_names])),
                )
                chi2, p, dof, expected = sp_stats.chi2_contingency(contingency)
                n_obs = contingency.values.sum()
                cramers_v = math.sqrt(chi2 / (n_obs * (min(contingency.shape) - 1))) if n_obs > 0 else 0
                return {
                    "test_name": "Chi-squared test",
                    "statistic": round(float(chi2), 4),
                    "p_value": round(float(p), 6),
                    "degrees_of_freedom": int(dof),
                    "effect_size": round(float(cramers_v), 4),
                    "effect_metric": "cramers_v",
                }

        if "wilcoxon" in test_name.lower() or test_name == "wilcoxon":
            if pop_mean is not None:
                stat, p = sp_stats.wilcoxon(series - pop_mean, alternative=scipy_alt)
                r = float(stat) / (len(series) * (len(series) + 1) / 2)
                return {
                    "test_name": "Wilcoxon signed-rank",
                    "statistic": round(float(stat), 4),
                    "p_value": round(float(p), 6),
                    "effect_size": round(r, 4),
                    "effect_metric": "r",
                }

        return None

    @staticmethod
    def _compute_auc(y_true: np.ndarray, y_scores: np.ndarray) -> float:
        """Simple AUC computation without sklearn dependency."""
        pos = y_scores[y_true == 1]
        neg = y_scores[y_true == 0]
        if len(pos) == 0 or len(neg) == 0:
            return 0.5
        auc = sum(1 for p in pos for n in neg if p > n) + 0.5 * sum(1 for p in pos for n in neg if p == n)
        return auc / (len(pos) * len(neg))

    def _dataset_not_found(self, dataset_id: str, context: AnalysisContext) -> SpecialistResult:
        available = ", ".join(context.dataset_ids) or "none"
        return SpecialistResult(
            success=False, specialist_name=self.name,
            result_type=ResultType.ERROR, data=None,
            summary=f"Dataset '{dataset_id}' not found. Available: {available}",
            error=f"Dataset not found: {dataset_id}",
        )

    def _column_not_found(self, col: str, df: pd.DataFrame) -> SpecialistResult:
        available = ", ".join(str(c) for c in df.columns)
        return SpecialistResult(
            success=False, specialist_name=self.name,
            result_type=ResultType.ERROR, data=None,
            summary=f"Column '{col}' not found. Available: {available}",
            error=f"Column not found: {col}",
        )
