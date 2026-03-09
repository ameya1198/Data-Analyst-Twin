"""
Intent Classifier — routes user requests to the right execution mode.

Execution modes and their LLM cost:
    DIRECT:         0 LLM calls  — known tool, skip Plan/Reflect/Synthesize
    FOCUSED:        2 LLM calls  — Plan + Execute + lightweight Synthesize (skip Reflect)
    FULL:           3-5 LLM calls — Plan + Execute + Reflect (up to 2 cycles) + Synthesize
    CONVERSATIONAL: 1+ LLM calls — dynamic tool-use loop, Claude decides tools

Why this matters:
    "Profile my data"           → DIRECT  (just run eda_profile, return result)
    "Write SQL for top users"   → FOCUSED (plan + execute, skip reflection)
    "What insights can you find" → FULL   (full loop with reflection)
    "Now show me a chart of that" → CONVERSATIONAL (follow-up, dynamic)

Classification is rule-based (zero latency, zero cost). No LLM call needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ExecutionMode(str, Enum):
    DIRECT = "direct"
    FOCUSED = "focused"
    FULL = "full"
    CONVERSATIONAL = "conversational"


class UserIntent(str, Enum):
    PROFILE_DATA = "profile_data"
    DATA_QUALITY = "data_quality"
    DESCRIBE_COLUMNS = "describe_columns"
    CORRELATIONS = "correlations"
    VALUE_COUNTS = "value_counts"
    SCHEMA = "schema"
    VALIDATE = "validate"

    RUN_EDA = "run_eda"
    CLEAN_DATA = "clean_data"
    SQL_QUERY = "sql_query"
    STATISTICAL_TEST = "statistical_test"
    VISUALIZATION = "visualization"
    AB_TEST = "ab_test"
    REGRESSION = "regression"

    OPEN_EXPLORATION = "open_exploration"

    FOLLOW_UP = "follow_up"
    GENERAL = "general"


@dataclass
class ClassifiedIntent:
    intent: UserIntent
    mode: ExecutionMode
    confidence: float
    direct_tool: str | None = None
    direct_params: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""


# ─── Direct-mode tool routing table ──────────────────────────────────────────

DIRECT_INTENTS: dict[UserIntent, str] = {
    UserIntent.PROFILE_DATA: "eda_profile",
    UserIntent.DATA_QUALITY: "eda_data_quality",
    UserIntent.DESCRIBE_COLUMNS: "eda_describe",
    UserIntent.CORRELATIONS: "eda_correlations",
    UserIntent.VALUE_COUNTS: "eda_value_counts",
    UserIntent.SCHEMA: "sql_schema",
    UserIntent.VALIDATE: "clean_validate",
}

INTENT_TO_MODE: dict[UserIntent, ExecutionMode] = {
    UserIntent.PROFILE_DATA: ExecutionMode.DIRECT,
    UserIntent.DATA_QUALITY: ExecutionMode.DIRECT,
    UserIntent.DESCRIBE_COLUMNS: ExecutionMode.DIRECT,
    UserIntent.CORRELATIONS: ExecutionMode.DIRECT,
    UserIntent.VALUE_COUNTS: ExecutionMode.DIRECT,
    UserIntent.SCHEMA: ExecutionMode.DIRECT,
    UserIntent.VALIDATE: ExecutionMode.DIRECT,

    UserIntent.RUN_EDA: ExecutionMode.FOCUSED,
    UserIntent.CLEAN_DATA: ExecutionMode.FOCUSED,
    UserIntent.SQL_QUERY: ExecutionMode.FOCUSED,
    UserIntent.STATISTICAL_TEST: ExecutionMode.FOCUSED,
    UserIntent.VISUALIZATION: ExecutionMode.FOCUSED,
    UserIntent.AB_TEST: ExecutionMode.FOCUSED,
    UserIntent.REGRESSION: ExecutionMode.FOCUSED,

    UserIntent.OPEN_EXPLORATION: ExecutionMode.FULL,

    UserIntent.FOLLOW_UP: ExecutionMode.CONVERSATIONAL,
    UserIntent.GENERAL: ExecutionMode.CONVERSATIONAL,
}


# ─── Pattern Definitions ─────────────────────────────────────────────────────

_DIRECT_PATTERNS: list[tuple[str, UserIntent, float]] = [
    (r"\b(?:profile|overview|summarize?\s+(?:the\s+)?data)\b", UserIntent.PROFILE_DATA, 0.95),
    (r"\bdata\s*quality\b", UserIntent.DATA_QUALITY, 0.95),
    (r"\b(?:describe|summary\s+stat|descriptive\s+stat)", UserIntent.DESCRIBE_COLUMNS, 0.90),
    (r"\bcorrelat", UserIntent.CORRELATIONS, 0.90),
    (r"\b(?:value\s*count|frequency|distribution\s+of|how\s+many\s+(?:of|per|in|are)|per\s+\w+\s*(?:category|group|type|segment))", UserIntent.VALUE_COUNTS, 0.85),
    (r"\b(?:schema|show\s+tables|table\s+structure|columns?\s+(?:list|names))", UserIntent.SCHEMA, 0.90),
    (r"\bvalidat", UserIntent.VALIDATE, 0.85),
]

_FOCUSED_PATTERNS: list[tuple[str, UserIntent, float]] = [
    (r"\b(?:eda|exploratory\s+data|explore\s+(?:the\s+)?data)", UserIntent.RUN_EDA, 0.90),
    (r"\b(?:clean|fix|dedup|deduplic|duplicat|missing\s+value|impute|standardis|standardiz|structural\s+fix)", UserIntent.CLEAN_DATA, 0.90),
    (r"\b(?:sql|query|write\s+(?:a\s+)?query|select\s+|join|group\s+by|aggregat|cohort|funnel|retention)", UserIntent.SQL_QUERY, 0.90),
    (r"\b(?:hypothesis|significan|t-test|ttest|anova|chi-?square|mann-?whitney|kruskal|p-?value|statistical\s+test)", UserIntent.STATISTICAL_TEST, 0.90),
    (r"\b(?:chart|plot|graph|visuali[sz]|bar\s*chart|line\s*chart|scatter|histogram|heatmap|pie\s*chart|box\s*plot)", UserIntent.VISUALIZATION, 0.85),
    (r"\ba/?b\s*test", UserIntent.AB_TEST, 0.95),
    (r"\b(?:regress|predict|linear\s+model|logistic)", UserIntent.REGRESSION, 0.90),
    (r"\b(?:power\s+analy|sample\s+size|effect\s+size)", UserIntent.STATISTICAL_TEST, 0.85),
]

_FULL_PATTERNS: list[tuple[str, UserIntent, float]] = [
    (r"\b(?:analy[sz]e|analysis|insight|what\s+(?:can\s+you|do\s+you)\s+(?:find|see|tell))", UserIntent.OPEN_EXPLORATION, 0.85),
    (r"\b(?:deep\s+dive|thorough|comprehensive|full\s+analysis|complete\s+analysis)", UserIntent.OPEN_EXPLORATION, 0.90),
    (r"\b(?:what(?:'s|\s+is)\s+(?:going\s+on|happening)|summarize\s+everything|report)", UserIntent.OPEN_EXPLORATION, 0.80),
    (r"\b(?:investigate|dig\s+into|look\s+into\s+everything)", UserIntent.OPEN_EXPLORATION, 0.85),
]

_FOLLOW_UP_PATTERNS: list[tuple[str, UserIntent, float]] = [
    (r"^(?:now|also|and|then)\b", UserIntent.FOLLOW_UP, 0.80),
    (r"\b(?:what\s+about|how\s+about|can\s+you\s+also)\b", UserIntent.FOLLOW_UP, 0.85),
    (r"\b(?:that\s+(?:result|chart|table|data)|those\s+(?:results|numbers))\b", UserIntent.FOLLOW_UP, 0.80),
    (r"\b(?:the\s+(?:previous|last|same)\s+(?:result|chart|analysis|data|query))\b", UserIntent.FOLLOW_UP, 0.80),
    (r"\b(?:redo|rerun|re-?run)\b", UserIntent.FOLLOW_UP, 0.85),
    (r"^(?:show|do|run|make|give)\s+(?:me\s+)?(?:the\s+same|it|that)", UserIntent.FOLLOW_UP, 0.75),
]


class IntentClassifier:
    """
    Rule-based intent classifier. Zero latency, zero LLM cost.

    Classification order (first match wins within a tier, highest confidence across tiers):
    1. Follow-up signals (context-dependent)
    2. Direct-mode patterns (single known tool)
    3. Full-mode patterns (open-ended exploration)
    4. Focused-mode patterns (multi-step but scoped)
    5. Default → CONVERSATIONAL
    """

    def classify(
        self,
        message: str,
        has_conversation_history: bool = False,
        has_data: bool = True,
    ) -> ClassifiedIntent:
        lower = message.strip().lower()

        if not has_data:
            return ClassifiedIntent(
                intent=UserIntent.GENERAL,
                mode=ExecutionMode.CONVERSATIONAL,
                confidence=1.0,
                reasoning="No data loaded — conversational mode",
            )

        best: ClassifiedIntent | None = None

        # 1. Check follow-up signals (boosted confidence when history exists)
        if has_conversation_history:
            for pattern, intent, conf in _FOLLOW_UP_PATTERNS:
                if re.search(pattern, lower):
                    boosted = min(conf + 0.15, 1.0)
                    candidate = ClassifiedIntent(
                        intent=intent,
                        mode=INTENT_TO_MODE[intent],
                        confidence=boosted,
                        reasoning=f"Follow-up detected with conversation history",
                    )
                    if best is None or candidate.confidence > best.confidence:
                        best = candidate
            if best is not None:
                logger.info(
                    "intent_classified",
                    intent=best.intent.value,
                    mode=best.mode.value,
                    confidence=best.confidence,
                    reasoning=best.reasoning,
                    message_preview=lower[:60],
                )
                return best

        # 2. Check direct-mode patterns (highest priority for clear tool requests)
        for pattern, intent, conf in _DIRECT_PATTERNS:
            if re.search(pattern, lower):
                candidate = ClassifiedIntent(
                    intent=intent,
                    mode=ExecutionMode.DIRECT,
                    confidence=conf,
                    direct_tool=DIRECT_INTENTS[intent],
                    reasoning=f"Direct tool match: {DIRECT_INTENTS[intent]}",
                )
                if best is None or candidate.confidence > best.confidence:
                    best = candidate

        # 3. Check full-mode patterns (open exploration)
        for pattern, intent, conf in _FULL_PATTERNS:
            if re.search(pattern, lower):
                candidate = ClassifiedIntent(
                    intent=intent,
                    mode=ExecutionMode.FULL,
                    confidence=conf,
                    reasoning=f"Open exploration detected",
                )
                if best is None or candidate.confidence > best.confidence:
                    best = candidate

        # 4. Check focused-mode patterns
        for pattern, intent, conf in _FOCUSED_PATTERNS:
            if re.search(pattern, lower):
                candidate = ClassifiedIntent(
                    intent=intent,
                    mode=INTENT_TO_MODE[intent],
                    confidence=conf,
                    reasoning=f"Focused task: {intent.value}",
                )
                if best is None or candidate.confidence > best.confidence:
                    best = candidate

        # 5. Default
        if best is None:
            if has_conversation_history:
                best = ClassifiedIntent(
                    intent=UserIntent.FOLLOW_UP,
                    mode=ExecutionMode.CONVERSATIONAL,
                    confidence=0.5,
                    reasoning="No clear pattern — treating as conversational follow-up",
                )
            else:
                best = ClassifiedIntent(
                    intent=UserIntent.GENERAL,
                    mode=ExecutionMode.FULL,
                    confidence=0.5,
                    reasoning="No clear pattern — using full analysis mode",
                )

        logger.info(
            "intent_classified",
            intent=best.intent.value,
            mode=best.mode.value,
            confidence=best.confidence,
            reasoning=best.reasoning,
            message_preview=lower[:60],
        )

        return best

    def get_direct_params(
        self, intent: ClassifiedIntent, dataset_ids: list[str]
    ) -> dict[str, Any]:
        """Build tool params for DIRECT mode from context."""
        if not dataset_ids:
            return {}

        default_dataset = dataset_ids[0]
        return {"dataset_id": default_dataset}
