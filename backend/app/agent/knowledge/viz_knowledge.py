"""
Visualization Specialist Knowledge Base — comprehensive framework encoding:

1. Edward Tufte's Core Principles (data-ink ratio, graphical integrity, small multiples)
2. Chart Selection Rules (goal-to-chart mapping + anti-patterns)
3. Clarity & Simplicity Principles (5-second rule, one-chart-one-message)
4. Color Principles (sequential/diverging/categorical, colorblind-safe)
5. Audience-First Design (Executive / Manager / Analyst / Public)
6. Exploratory vs. Explanatory Visualization
7. Labeling & Annotation Standards
8. Scale & Proportion Rules
9. Analytics Visualization Ladder (Descriptive → Diagnostic → Predictive → Prescriptive)

This knowledge is embedded directly in the specialist (Level 1) and injected
into prompts as few-shot context (Level 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ─── 1. TUFTE'S CORE PRINCIPLES ───────────────────────────────────────────────

TUFTE_PRINCIPLES = {
    "data_ink_ratio": {
        "definition": "Maximize the proportion of ink/pixels that represent actual data.",
        "formula": "Data-Ink Ratio = Data-Ink / Total Ink Used",
        "rules": [
            "Every element on a chart must earn its place.",
            "Continuously ask: 'Can I remove this element without losing information?'",
            "Remove gridlines, borders, decorative colors, and 3D effects unless they convey data.",
        ],
    },
    "five_rules": [
        "Above all else, show the data.",
        "Maximize the data-ink ratio.",
        "Erase non-data-ink (gridlines, borders, decorative colors, 3D effects).",
        "Erase redundant data-ink (duplicate legends, unnecessary labels).",
        "Avoid Chartjunk (decorative graphics that distract from the data).",
    ],
    "graphical_integrity": {
        "rules": [
            "Never distort data through visual manipulation.",
            "Always start axes at zero for bar charts.",
            "Use consistent scales across related charts.",
            "Size shapes proportionally to the numbers they represent.",
        ],
        "lie_factor": {
            "formula": "Lie Factor = size of effect shown in graphic / size of effect in data",
            "target": 1.0,
            "description": "Keep the Lie Factor at 1.0 — the visual representation should match the data exactly.",
        },
    },
    "small_multiples": {
        "description": "Repeat the same small chart across different dimensions/categories.",
        "benefits": "Allows comparison without cluttering a single chart.",
        "when_to_use": "Preferred over complex multi-series charts when dimensions exceed 4+.",
    },
}


# ─── 2. CHART SELECTION RULES ─────────────────────────────────────────────────

class ChartGoal(str, Enum):
    COMPARE_CATEGORIES = "compare_categories"
    SHOW_TREND = "show_trend"
    SHOW_CORRELATION = "show_correlation"
    SHOW_CORRELATION_3D = "show_correlation_3d"
    SHOW_COMPOSITION = "show_composition"
    SHOW_DISTRIBUTION = "show_distribution"
    SHOW_GEOGRAPHIC = "show_geographic"
    COMPARE_PROPORTIONS = "compare_proportions"
    SHOW_HIERARCHY = "show_hierarchy"
    SHOW_MANY_VARIABLES = "show_many_variables"
    INLINE_TREND = "inline_trend"


@dataclass
class ChartRecommendation:
    goal: ChartGoal
    primary_chart: str
    alternatives: list[str]
    description: str
    when_to_use: str
    tool_name: str


CHART_SELECTION_RULES: list[ChartRecommendation] = [
    ChartRecommendation(
        goal=ChartGoal.COMPARE_CATEGORIES,
        primary_chart="bar",
        alternatives=["horizontal_bar"],
        description="Compare values across discrete categories.",
        when_to_use="When comparing named groups (departments, products, regions).",
        tool_name="viz_bar_chart",
    ),
    ChartRecommendation(
        goal=ChartGoal.SHOW_TREND,
        primary_chart="line",
        alternatives=["area"],
        description="Show how a value changes over time.",
        when_to_use="When the x-axis is temporal (dates, months, years).",
        tool_name="viz_line_chart",
    ),
    ChartRecommendation(
        goal=ChartGoal.SHOW_CORRELATION,
        primary_chart="scatter",
        alternatives=["bubble"],
        description="Show the relationship between two numeric variables.",
        when_to_use="When exploring whether two variables move together.",
        tool_name="viz_scatter_plot",
    ),
    ChartRecommendation(
        goal=ChartGoal.SHOW_COMPOSITION,
        primary_chart="stacked_bar",
        alternatives=["pie"],
        description="Show part-to-whole relationships.",
        when_to_use="When showing how parts add up to a total. Prefer stacked bar over pie.",
        tool_name="viz_bar_chart",
    ),
    ChartRecommendation(
        goal=ChartGoal.SHOW_DISTRIBUTION,
        primary_chart="histogram",
        alternatives=["box", "violin"],
        description="Show the distribution shape of a numeric variable.",
        when_to_use="When understanding spread, skew, and outliers matters.",
        tool_name="viz_histogram",
    ),
    ChartRecommendation(
        goal=ChartGoal.SHOW_MANY_VARIABLES,
        primary_chart="heatmap",
        alternatives=["radar"],
        description="Show values across many variables simultaneously.",
        when_to_use="Correlation matrices, cross-tabulations, or multi-variable comparison.",
        tool_name="viz_heatmap",
    ),
    ChartRecommendation(
        goal=ChartGoal.COMPARE_PROPORTIONS,
        primary_chart="stacked_bar",
        alternatives=["treemap"],
        description="Compare proportions across categories.",
        when_to_use="When part-to-whole comparison across groups is needed.",
        tool_name="viz_bar_chart",
    ),
]

CHART_ANTI_PATTERNS = [
    {"pattern": "3D charts of any kind", "reason": "Always distort perception. Use 2D equivalents."},
    {"pattern": "Pie charts with more than 5 segments", "reason": "Humans cannot accurately compare angles beyond 5 slices."},
    {"pattern": "Dual Y-axis charts", "reason": "Misleading by design — the relationship depends on arbitrary scale choices."},
    {"pattern": "Donut charts when precision matters", "reason": "Harder to compare arc lengths than bar lengths."},
    {"pattern": "Truncated Y-axes on bar charts", "reason": "Exaggerates differences. Bar charts must start at zero."},
    {"pattern": "Area/bubble charts for precise comparison", "reason": "Humans are poor at comparing areas accurately."},
    {"pattern": "Inconsistent bin sizes in histograms", "reason": "Distorts the apparent distribution shape."},
]


# ─── 3. CLARITY & SIMPLICITY PRINCIPLES ───────────────────────────────────────

CLARITY_PRINCIPLES = [
    {
        "name": "One chart, one message",
        "rule": "Each visualization should answer exactly one question.",
    },
    {
        "name": "The 5-second rule",
        "rule": "If the viewer can't understand the main point in 5 seconds, simplify.",
    },
    {
        "name": "Remove before adding",
        "rule": "Always try removing elements before adding new ones.",
    },
    {
        "name": "No legend if avoidable",
        "rule": "Label data directly on the chart when possible.",
    },
    {
        "name": "Minimal color",
        "rule": "Use 1-3 colors max; color should encode meaning, not decoration.",
    },
    {
        "name": "White space is not wasted space",
        "rule": "Breathing room improves comprehension.",
    },
]


# ─── 4. COLOR PRINCIPLES ──────────────────────────────────────────────────────

class PaletteType(str, Enum):
    SEQUENTIAL = "sequential"
    DIVERGING = "diverging"
    CATEGORICAL = "categorical"


@dataclass
class ColorPalette:
    name: str
    palette_type: PaletteType
    colors: list[str]
    colorblind_safe: bool = True
    description: str = ""


COLORBLIND_SAFE_PALETTES: dict[str, ColorPalette] = {
    "viridis": ColorPalette(
        name="Viridis",
        palette_type=PaletteType.SEQUENTIAL,
        colors=["#440154", "#482777", "#3E4A89", "#31688E", "#26838F", "#1F9D8A", "#6CCE59", "#B6DE2B", "#FEE825"],
        colorblind_safe=True,
        description="Perceptually uniform sequential palette. Best for continuous ordered data.",
    ),
    "okabe_ito": ColorPalette(
        name="Okabe-Ito",
        palette_type=PaletteType.CATEGORICAL,
        colors=["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#999999"],
        colorblind_safe=True,
        description="Universal categorical palette designed for colorblind accessibility.",
    ),
    "blue_orange_diverging": ColorPalette(
        name="Blue-Orange Diverging",
        palette_type=PaletteType.DIVERGING,
        colors=["#2166AC", "#4393C3", "#92C5DE", "#D1E5F0", "#F7F7F7", "#FDDBC7", "#F4A582", "#D6604D", "#B2182B"],
        colorblind_safe=True,
        description="Diverging palette for data with a meaningful midpoint (profit/loss, above/below average).",
    ),
    "plotly_qualitative": ColorPalette(
        name="Plotly Safe",
        palette_type=PaletteType.CATEGORICAL,
        colors=["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692"],
        colorblind_safe=True,
        description="Plotly's default qualitative palette with good contrast.",
    ),
}

COLOR_RULES = [
    "Use color to encode meaning, never for aesthetics alone.",
    "Sequential palettes (light to dark): for continuous data with a natural order.",
    "Diverging palettes (two hues from a center): for data with a meaningful midpoint.",
    "Categorical palettes (distinct hues): for unordered categories.",
    "Max 7 distinct colors in a single chart — beyond that, group into 'Other'.",
    "Always use colorblind-safe palettes (avoid red/green combinations).",
    "Never use color as the only differentiator — pair with shape, pattern, or label.",
]


# ─── 5. AUDIENCE-FIRST DESIGN ─────────────────────────────────────────────────

class AudienceLevel(str, Enum):
    EXECUTIVE = "executive"
    MANAGER = "manager"
    ANALYST = "analyst"
    PUBLIC = "public"


@dataclass
class AudienceConfig:
    level: AudienceLevel
    name: str
    key_question: str
    preferred_charts: list[str]
    style_notes: list[str]
    max_complexity: str


AUDIENCE_CONFIGS: dict[str, AudienceConfig] = {
    "executive": AudienceConfig(
        level=AudienceLevel.EXECUTIVE,
        name="Executive / C-Suite",
        key_question="Are we on track?",
        preferred_charts=["KPI cards", "sparklines", "simple bar", "RAG status"],
        style_notes=[
            "High-level KPIs only.",
            "Minimal detail, maximum clarity.",
            "Use big numbers, sparklines, RAG (Red/Amber/Green) status.",
            "Answer the key question in under 10 seconds.",
        ],
        max_complexity="simple",
    ),
    "manager": AudienceConfig(
        level=AudienceLevel.MANAGER,
        name="Business Analyst / Manager",
        key_question="Why did this happen?",
        preferred_charts=["line (trends)", "bar (comparisons)", "waterfall", "stacked bar"],
        style_notes=[
            "Trend lines, period-over-period comparisons.",
            "Some drill-down capability.",
            "Context like benchmarks and targets.",
        ],
        max_complexity="moderate",
    ),
    "analyst": AudienceConfig(
        level=AudienceLevel.ANALYST,
        name="Data Analyst / Technical",
        key_question="What patterns exist in the data?",
        preferred_charts=["scatter", "heatmap", "box plot", "histogram", "distribution"],
        style_notes=[
            "Dense, interactive, filterable.",
            "Scatter plots, distributions, heatmaps acceptable.",
            "Raw numbers alongside visuals.",
        ],
        max_complexity="complex",
    ),
    "public": AudienceConfig(
        level=AudienceLevel.PUBLIC,
        name="General / Public Audience",
        key_question="What does this mean for me?",
        preferred_charts=["bar", "line", "pie (sparingly)"],
        style_notes=[
            "Familiar chart types only (bar, line, pie).",
            "No jargon, annotate everything.",
            "Tell the story explicitly — don't assume inference.",
        ],
        max_complexity="simple",
    ),
}


# ─── 6. EXPLORATORY vs. EXPLANATORY ───────────────────────────────────────────

VIZ_MODES = {
    "exploratory": {
        "audience": "analyst",
        "purpose": "Discover patterns, test hypotheses, find anomalies.",
        "style": "Dense, interactive, multiple views.",
        "preferred_charts": ["scatter matrix", "heatmap", "box plot", "histogram"],
        "priority": "Speed over beauty.",
    },
    "explanatory": {
        "audience": "stakeholder",
        "purpose": "Communicate a specific finding.",
        "style": "Clean, single message, guided narrative.",
        "preferred_charts": ["annotated line", "annotated bar", "highlighted key points"],
        "priority": "Beauty in service of clarity.",
    },
    "golden_rule": "Never show an exploratory chart to an executive. Always convert it to explanatory first.",
}


# ─── 7. LABELING & ANNOTATION STANDARDS ───────────────────────────────────────

LABELING_STANDARDS = [
    {
        "element": "axis_labels",
        "rule": 'Always label axes with units: "Revenue (USD millions)" not just "Revenue".',
    },
    {
        "element": "title",
        "rule": 'Use active, insight-driven titles: "Revenue Declined 12% in Q3" not "Q3 Revenue".',
    },
    {
        "element": "subtitle",
        "rule": "Use subtitles for qualifiers: time period, geography, data source.",
    },
    {
        "element": "annotations",
        "rule": "Annotate outliers, turning points, and key events directly on the chart.",
    },
    {
        "element": "source",
        "rule": 'Cite data sources in small text at the bottom: "Source: Salesforce CRM, Q3 2025".',
    },
    {
        "element": "numbers",
        "rule": 'Round numbers for readability: "$2.4M" not "$2,413,827".',
    },
    {
        "element": "case",
        "rule": "Use sentence case for all labels (not ALL CAPS or Title Case Every Word).",
    },
]


# ─── 8. SCALE & PROPORTION RULES ──────────────────────────────────────────────

SCALE_RULES = [
    {"chart_type": "bar", "rule": "Y-axis must start at zero — always.", "enforced": True},
    {"chart_type": "line", "rule": "Y-axis can start at a non-zero value if the range of variation is the story.", "enforced": False},
    {"chart_type": "multiple", "rule": "Use consistent scales when comparing multiple charts side by side.", "enforced": True},
    {"chart_type": "area_bubble", "rule": "Avoid area/bubble charts where precise comparison matters (humans are poor at comparing areas).", "enforced": False},
    {"chart_type": "log", "rule": "Log scales are acceptable for data spanning multiple orders of magnitude — but always label them.", "enforced": True},
    {"chart_type": "histogram", "rule": "Never use inconsistent bin sizes in histograms.", "enforced": True},
]


# ─── 9. ANALYTICS VISUALIZATION LADDER ────────────────────────────────────────

ANALYTICS_VIZ_LADDER = [
    {
        "analytics_type": "descriptive",
        "question": "What happened?",
        "chart_examples": ["bar", "line", "table", "KPI cards"],
        "tool_names": ["viz_bar_chart", "viz_line_chart"],
    },
    {
        "analytics_type": "diagnostic",
        "question": "Why did it happen?",
        "chart_examples": ["scatter", "waterfall", "decomposition tree", "heatmap"],
        "tool_names": ["viz_scatter_plot", "viz_heatmap"],
    },
    {
        "analytics_type": "predictive",
        "question": "What will happen?",
        "chart_examples": ["forecast line", "confidence bands", "funnel"],
        "tool_names": ["viz_line_chart"],
    },
    {
        "analytics_type": "prescriptive",
        "question": "What should we do?",
        "chart_examples": ["scenario comparison", "decision matrix"],
        "tool_names": ["viz_bar_chart", "viz_heatmap"],
    },
]


# ─── PLOTLY DEFAULTS (applied to all charts) ──────────────────────────────────

PLOTLY_DEFAULTS = {
    "template": "plotly_white",
    "font_family": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    "font_size": 12,
    "title_font_size": 16,
    "margin": {"l": 60, "r": 30, "t": 60, "b": 50},
    "showlegend_threshold": 1,
    "gridcolor": "rgba(0,0,0,0.06)",
    "gridwidth": 1,
    "plot_bgcolor": "white",
    "paper_bgcolor": "white",
    "colorway": COLORBLIND_SAFE_PALETTES["okabe_ito"].colors,
    "hovermode": "closest",
}


# ─── UTILITY FUNCTIONS ────────────────────────────────────────────────────────

def get_chart_recommendation(goal: str) -> Optional[ChartRecommendation]:
    """Look up the best chart for a given analytical goal."""
    try:
        chart_goal = ChartGoal(goal)
    except ValueError:
        for rec in CHART_SELECTION_RULES:
            if goal.lower() in rec.goal.value.lower() or goal.lower() in rec.description.lower():
                return rec
        return None
    for rec in CHART_SELECTION_RULES:
        if rec.goal == chart_goal:
            return rec
    return None


def get_color_palette(
    data_type: str, n_colors: int = 7
) -> list[str]:
    """Select appropriate colors based on data type.

    data_type: "sequential", "diverging", or "categorical"
    """
    if data_type == "sequential":
        pal = COLORBLIND_SAFE_PALETTES["viridis"]
    elif data_type == "diverging":
        pal = COLORBLIND_SAFE_PALETTES["blue_orange_diverging"]
    else:
        pal = COLORBLIND_SAFE_PALETTES["okabe_ito"]

    colors = pal.colors
    if n_colors <= len(colors):
        step = max(1, len(colors) // n_colors)
        return colors[::step][:n_colors]
    return colors[:n_colors]


def get_audience_config(audience_level: str) -> AudienceConfig:
    """Get visualization configuration for a specific audience tier."""
    if audience_level in AUDIENCE_CONFIGS:
        return AUDIENCE_CONFIGS[audience_level]
    return AUDIENCE_CONFIGS["analyst"]


def get_anti_patterns() -> list[dict]:
    """Return all chart anti-patterns the specialist should avoid."""
    return CHART_ANTI_PATTERNS


def get_viz_workflow_summary() -> str:
    """Text summary of the full viz knowledge — for LLM prompt injection."""
    lines = []

    lines.append("=== Visualization Knowledge Base ===")
    lines.append("")

    lines.append("Tufte's 5 Rules:")
    for i, rule in enumerate(TUFTE_PRINCIPLES["five_rules"], 1):
        lines.append(f"  {i}. {rule}")
    lines.append("")

    lines.append("Chart Selection (goal → chart):")
    for rec in CHART_SELECTION_RULES:
        lines.append(f"  {rec.goal.value} → {rec.primary_chart} (tool: {rec.tool_name})")
    lines.append("")

    lines.append("Anti-patterns to AVOID:")
    for ap in CHART_ANTI_PATTERNS[:4]:
        lines.append(f"  - {ap['pattern']}: {ap['reason']}")
    lines.append("")

    lines.append("Color Rules:")
    lines.append("  Sequential (ordered data) | Diverging (midpoint data) | Categorical (unordered)")
    lines.append("  Max 7 colors. Always colorblind-safe. Never color-only encoding.")
    lines.append("")

    lines.append("Scale Rules:")
    lines.append("  Bar charts: Y-axis MUST start at zero.")
    lines.append("  Line charts: non-zero Y-axis OK if variation is the story.")
    lines.append("  Histograms: consistent bin sizes required.")
    lines.append("")

    lines.append("Labeling:")
    lines.append('  Axes with units. Insight-driven titles. Sentence case. Round numbers.')
    lines.append("")

    lines.append("Analytics Visualization Ladder:")
    for level in ANALYTICS_VIZ_LADDER:
        charts = ", ".join(level["chart_examples"])
        lines.append(f"  {level['analytics_type'].title()} ({level['question']}) → {charts}")

    return "\n".join(lines)


def get_plotly_layout_defaults(title: str = "", subtitle: str = "") -> dict:
    """Return a Plotly layout dict with Tufte-compliant defaults."""
    layout = {
        "template": PLOTLY_DEFAULTS["template"],
        "font": {
            "family": PLOTLY_DEFAULTS["font_family"],
            "size": PLOTLY_DEFAULTS["font_size"],
        },
        "title": {
            "text": f"{title}<br><sup>{subtitle}</sup>" if subtitle else title,
            "font": {"size": PLOTLY_DEFAULTS["title_font_size"]},
            "x": 0.0,
            "xanchor": "left",
        },
        "margin": PLOTLY_DEFAULTS["margin"],
        "plot_bgcolor": PLOTLY_DEFAULTS["plot_bgcolor"],
        "paper_bgcolor": PLOTLY_DEFAULTS["paper_bgcolor"],
        "hovermode": PLOTLY_DEFAULTS["hovermode"],
        "colorway": PLOTLY_DEFAULTS["colorway"],
    }
    return layout


def apply_tufte_axes(fig_layout: dict, chart_type: str = "bar") -> dict:
    """Apply Tufte-compliant axis styling."""
    axis_style = {
        "showgrid": True,
        "gridcolor": PLOTLY_DEFAULTS["gridcolor"],
        "gridwidth": PLOTLY_DEFAULTS["gridwidth"],
        "zeroline": False,
        "showline": False,
        "ticks": "outside",
        "tickcolor": "rgba(0,0,0,0.2)",
    }

    fig_layout["xaxis"] = {**fig_layout.get("xaxis", {}), **axis_style}
    fig_layout["yaxis"] = {**fig_layout.get("yaxis", {}), **axis_style}

    if chart_type == "bar":
        fig_layout["yaxis"]["rangemode"] = "tozero"

    return fig_layout


# Combined knowledge object for easy import
VIZ_KNOWLEDGE = {
    "tufte_principles": TUFTE_PRINCIPLES,
    "chart_selection_rules": CHART_SELECTION_RULES,
    "anti_patterns": CHART_ANTI_PATTERNS,
    "clarity_principles": CLARITY_PRINCIPLES,
    "color_rules": COLOR_RULES,
    "palettes": COLORBLIND_SAFE_PALETTES,
    "audience_configs": AUDIENCE_CONFIGS,
    "viz_modes": VIZ_MODES,
    "labeling_standards": LABELING_STANDARDS,
    "scale_rules": SCALE_RULES,
    "analytics_viz_ladder": ANALYTICS_VIZ_LADDER,
    "plotly_defaults": PLOTLY_DEFAULTS,
    "workflow_summary": get_viz_workflow_summary(),
}
