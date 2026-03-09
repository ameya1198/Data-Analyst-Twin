"""
Error Recovery Middleware — robust error handling between the Executor and Specialists.

Provides:
1. Error classification (transient vs permanent, with specific error types)
2. Retry with exponential backoff for transient failures
3. Circuit breaker per specialist (stop hammering a failing specialist)
4. Fallback tool suggestions when a tool permanently fails
5. Error context accumulation (fed back to supervisor/reflector for plan adaptation)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import structlog

from app.agent.specialists.base import (
    BaseSpecialist,
    ResultType,
    SpecialistRegistry,
    SpecialistResult,
)
from app.agent.specialists.context import AnalysisContext

logger = structlog.get_logger(__name__)


# ─── Error Classification ─────────────────────────────────────────────────────

class ErrorCategory(str, Enum):
    TRANSIENT = "transient"
    DATA_ISSUE = "data_issue"
    TOOL_MISUSE = "tool_misuse"
    RESOURCE_LIMIT = "resource_limit"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedError:
    category: ErrorCategory
    is_retryable: bool
    message: str
    original_error: str
    suggestion: str
    fallback_tool: Optional[str] = None


TRANSIENT_PATTERNS = [
    "timeout", "timed out", "connection reset", "connection refused",
    "rate limit", "429", "503", "502", "overloaded", "temporarily unavailable",
    "ssl", "eof", "broken pipe",
]

DATA_ISSUE_PATTERNS = [
    "not found", "no such column", "column", "key error", "keyerror",
    "index out of", "empty dataframe", "no data", "0 rows",
    "missing column", "not in index", "invalid dtype",
]

TOOL_MISUSE_PATTERNS = [
    "unknown tool", "no specialist", "invalid param", "required parameter",
    "missing required", "type error", "typeerror", "invalid argument",
    "expected", "must be",
]

RESOURCE_PATTERNS = [
    "memory", "out of memory", "oom", "too large", "max retries",
    "disk", "quota", "limit exceeded",
]


def classify_error(error_str: str, tool_name: str = "") -> ClassifiedError:
    """Classify an error into a category with recovery guidance."""
    lower = error_str.lower()

    if any(p in lower for p in TRANSIENT_PATTERNS):
        return ClassifiedError(
            category=ErrorCategory.TRANSIENT,
            is_retryable=True,
            message="Transient failure — will retry automatically.",
            original_error=error_str,
            suggestion="Retrying with exponential backoff.",
        )

    if any(p in lower for p in DATA_ISSUE_PATTERNS):
        suggestion = "Check column names and dataset contents."
        fallback = None
        if "column" in lower or "not found" in lower:
            suggestion = "The requested column may not exist. Try eda_profile first to see available columns."
            fallback = "eda_profile"
        elif "empty" in lower or "0 rows" in lower:
            suggestion = "Dataset appears empty. Verify the upload was successful."

        return ClassifiedError(
            category=ErrorCategory.DATA_ISSUE,
            is_retryable=False,
            message=f"Data issue in {tool_name}: the requested data or column may not exist.",
            original_error=error_str,
            suggestion=suggestion,
            fallback_tool=fallback,
        )

    if any(p in lower for p in TOOL_MISUSE_PATTERNS):
        suggestion = "The tool was called with incorrect parameters."
        fallback = None
        if "unknown tool" in lower or "no specialist" in lower:
            suggestion = "The requested tool doesn't exist. Use eda_profile to start exploration."
            fallback = "eda_profile"

        return ClassifiedError(
            category=ErrorCategory.TOOL_MISUSE,
            is_retryable=False,
            message=f"Tool misuse: {tool_name} was called incorrectly.",
            original_error=error_str,
            suggestion=suggestion,
            fallback_tool=fallback,
        )

    if any(p in lower for p in RESOURCE_PATTERNS):
        return ClassifiedError(
            category=ErrorCategory.RESOURCE_LIMIT,
            is_retryable=False,
            message="Resource limit reached — dataset may be too large for this operation.",
            original_error=error_str,
            suggestion="Try operating on a subset of data or fewer columns.",
        )

    return ClassifiedError(
        category=ErrorCategory.UNKNOWN,
        is_retryable=True,
        message=f"Unexpected error in {tool_name}.",
        original_error=error_str,
        suggestion="Retrying once. If persistent, try a different approach.",
    )


# ─── Circuit Breaker ──────────────────────────────────────────────────────────

@dataclass
class CircuitState:
    failure_count: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False

    FAILURE_THRESHOLD: int = 3
    RECOVERY_TIMEOUT: float = 60.0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.FAILURE_THRESHOLD:
            self.is_open = True
            logger.warning(
                "circuit_breaker_open",
                failures=self.failure_count,
            )

    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False

    def should_allow(self) -> bool:
        if not self.is_open:
            return True
        elapsed = time.monotonic() - self.last_failure_time
        if elapsed >= self.RECOVERY_TIMEOUT:
            logger.info("circuit_breaker_half_open", elapsed_s=round(elapsed, 1))
            return True
        return False


# ─── Recovery Event (streamed to frontend) ─────────────────────────────────────

@dataclass
class RecoveryEvent:
    """Structured record of an error recovery attempt."""
    tool_name: str
    attempt: int
    max_attempts: int
    error_category: str
    error_message: str
    action_taken: str
    suggestion: str
    fallback_tool: Optional[str] = None
    recovered: bool = False

    def to_stream_data(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "action_taken": self.action_taken,
            "suggestion": self.suggestion,
            "fallback_tool": self.fallback_tool,
            "recovered": self.recovered,
        }


# ─── Fallback Map ─────────────────────────────────────────────────────────────

TOOL_FALLBACKS: dict[str, list[str]] = {
    "eda_describe": ["eda_profile"],
    "eda_correlations": ["eda_profile"],
    "eda_value_counts": ["eda_profile"],
    "eda_smart_structure": ["eda_data_quality"],
    "viz_bar_chart": ["viz_recommend"],
    "viz_line_chart": ["viz_recommend"],
    "viz_scatter_plot": ["viz_recommend"],
    "viz_histogram": ["viz_recommend"],
    "viz_box_plot": ["viz_recommend"],
    "viz_heatmap": ["viz_recommend"],
    "viz_pie_chart": ["viz_recommend"],
    "sql_execute": ["sql_validate", "sql_schema"],
    "sql_validate": ["sql_schema"],
    "sql_format": ["sql_validate"],
    "sql_template": ["sql_schema"],
    "stats_test": ["stats_assumptions"],
    "stats_regression": ["stats_assumptions"],
    "stats_ab_test": ["stats_test"],
    "stats_power": ["stats_test"],
    "clean_structural": ["eda_profile"],
    "clean_deduplicate": ["clean_structural"],
    "clean_missing": ["clean_structural", "eda_profile"],
    "clean_standardise": ["clean_structural"],
    "clean_derive": ["clean_structural"],
    "clean_validate": ["eda_profile", "clean_structural"],
}


# ─── Error Recovery Middleware ─────────────────────────────────────────────────

class ErrorRecoveryMiddleware:
    """
    Wraps specialist execution with retry, circuit breaker, and fallback logic.

    Usage:
        middleware = ErrorRecoveryMiddleware(registry)
        result, events = await middleware.execute_with_recovery(tool_name, params, context)
    """

    def __init__(
        self,
        registry: SpecialistRegistry,
        max_retries: int = 2,
        base_delay: float = 0.5,
        max_delay: float = 5.0,
    ) -> None:
        self._registry = registry
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._circuits: dict[str, CircuitState] = {}
        self._error_history: list[ClassifiedError] = []

    def _get_circuit(self, specialist_name: str) -> CircuitState:
        if specialist_name not in self._circuits:
            self._circuits[specialist_name] = CircuitState()
        return self._circuits[specialist_name]

    async def execute_with_recovery(
        self,
        tool_name: str,
        params: dict,
        context: AnalysisContext,
    ) -> tuple[SpecialistResult, list[RecoveryEvent]]:
        """
        Execute a tool call with error recovery.

        Returns:
            (result, recovery_events) — the final result and any recovery events
            that occurred during execution.
        """
        recovery_events: list[RecoveryEvent] = []

        specialist = self._registry.get_specialist_for_tool(tool_name)
        if specialist is None:
            classified = classify_error(f"Unknown tool: {tool_name}", tool_name)
            self._error_history.append(classified)
            event = RecoveryEvent(
                tool_name=tool_name,
                attempt=1,
                max_attempts=1,
                error_category=classified.category.value,
                error_message=classified.message,
                action_taken="No recovery possible — tool does not exist.",
                suggestion=classified.suggestion,
                fallback_tool=classified.fallback_tool,
            )
            recovery_events.append(event)

            return SpecialistResult(
                success=False,
                specialist_name="unknown",
                result_type=ResultType.ERROR,
                data=None,
                summary=f"Unknown tool '{tool_name}'. {classified.suggestion}",
                error=f"Unknown tool: {tool_name}",
            ), recovery_events

        circuit = self._get_circuit(specialist.name)

        # Circuit breaker check
        if not circuit.should_allow():
            event = RecoveryEvent(
                tool_name=tool_name,
                attempt=0,
                max_attempts=0,
                error_category="circuit_open",
                error_message=f"Circuit breaker open for {specialist.name} — too many recent failures.",
                action_taken="Blocked by circuit breaker. Waiting for recovery timeout.",
                suggestion=f"Specialist '{specialist.name}' has failed {circuit.failure_count} times. Try a different approach or wait.",
            )
            recovery_events.append(event)

            return SpecialistResult(
                success=False,
                specialist_name=specialist.name,
                result_type=ResultType.ERROR,
                data=None,
                summary=f"Specialist '{specialist.name}' is temporarily unavailable (circuit breaker open).",
                error="Circuit breaker open",
                metadata={"circuit_breaker": True},
            ), recovery_events

        # Attempt execution with retries
        last_error: Optional[str] = None
        for attempt in range(1, self._max_retries + 2):  # +1 for initial attempt, +1 for range
            result = await specialist.execute(tool_name, params, context)

            if result.success:
                circuit.record_success()
                if attempt > 1:
                    recovery_events.append(RecoveryEvent(
                        tool_name=tool_name,
                        attempt=attempt,
                        max_attempts=self._max_retries + 1,
                        error_category="recovered",
                        error_message="",
                        action_taken=f"Succeeded on attempt {attempt}.",
                        suggestion="",
                        recovered=True,
                    ))
                    logger.info(
                        "error_recovery_succeeded",
                        tool=tool_name,
                        attempt=attempt,
                    )
                return result, recovery_events

            # Execution failed — classify the error
            error_str = result.error or result.summary or "Unknown error"
            last_error = error_str
            classified = classify_error(error_str, tool_name)
            self._error_history.append(classified)

            is_last_attempt = attempt > self._max_retries

            if not classified.is_retryable or is_last_attempt:
                circuit.record_failure()

                action = "No retry — error is not transient." if not classified.is_retryable else f"Exhausted all {self._max_retries + 1} attempts."

                # Try fallback
                fallback = self._get_fallback(tool_name, classified)
                event = RecoveryEvent(
                    tool_name=tool_name,
                    attempt=attempt,
                    max_attempts=self._max_retries + 1,
                    error_category=classified.category.value,
                    error_message=classified.message,
                    action_taken=action,
                    suggestion=classified.suggestion,
                    fallback_tool=fallback,
                )
                recovery_events.append(event)

                logger.warning(
                    "error_recovery_failed",
                    tool=tool_name,
                    attempt=attempt,
                    category=classified.category.value,
                    retryable=classified.is_retryable,
                    fallback=fallback,
                )

                # Enrich the result with recovery context
                result.metadata = result.metadata or {}
                result.metadata["error_category"] = classified.category.value
                result.metadata["suggestion"] = classified.suggestion
                result.metadata["fallback_tool"] = fallback
                result.metadata["attempts"] = attempt

                return result, recovery_events

            # Retryable — backoff and try again
            delay = min(self._base_delay * (2 ** (attempt - 1)), self._max_delay)
            event = RecoveryEvent(
                tool_name=tool_name,
                attempt=attempt,
                max_attempts=self._max_retries + 1,
                error_category=classified.category.value,
                error_message=classified.message,
                action_taken=f"Retrying in {delay:.1f}s (attempt {attempt}/{self._max_retries + 1}).",
                suggestion=classified.suggestion,
            )
            recovery_events.append(event)

            logger.info(
                "error_recovery_retry",
                tool=tool_name,
                attempt=attempt,
                delay_s=delay,
                category=classified.category.value,
            )
            await asyncio.sleep(delay)

        # Should not reach here, but handle gracefully
        return SpecialistResult(
            success=False,
            specialist_name=specialist.name if specialist else "unknown",
            result_type=ResultType.ERROR,
            data=None,
            summary=f"All recovery attempts failed for {tool_name}.",
            error=last_error or "Unknown error",
        ), recovery_events

    def _get_fallback(self, tool_name: str, classified: ClassifiedError) -> Optional[str]:
        """Determine the best fallback tool for a failed tool call."""
        if classified.fallback_tool:
            if classified.fallback_tool in self._registry.tool_names:
                return classified.fallback_tool

        fallbacks = TOOL_FALLBACKS.get(tool_name, [])
        for fb in fallbacks:
            if fb in self._registry.tool_names:
                fb_specialist = self._registry.get_specialist_for_tool(fb)
                if fb_specialist:
                    circuit = self._get_circuit(fb_specialist.name)
                    if circuit.should_allow():
                        return fb
        return None

    def get_error_context_for_reflector(self) -> str:
        """
        Summarize accumulated errors for the reflector to consider
        when evaluating analysis completeness.
        """
        if not self._error_history:
            return ""

        lines = [f"Errors encountered during execution ({len(self._error_history)} total):"]
        for err in self._error_history[-5:]:
            lines.append(
                f"  - [{err.category.value}] {err.message} → {err.suggestion}"
            )
        return "\n".join(lines)

    def get_circuit_status(self) -> dict[str, dict[str, Any]]:
        """Current state of all circuit breakers — for monitoring."""
        return {
            name: {
                "failure_count": state.failure_count,
                "is_open": state.is_open,
                "last_failure_time": state.last_failure_time,
            }
            for name, state in self._circuits.items()
        }

    def reset(self) -> None:
        """Reset all state — call between sessions."""
        self._circuits.clear()
        self._error_history.clear()
