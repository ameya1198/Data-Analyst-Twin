"""Tests for the error recovery middleware."""

import asyncio

import pytest

from app.agent.error_recovery import (
    ErrorRecoveryMiddleware,
    CircuitState,
    RecoveryEvent,
    classify_error,
    ErrorCategory,
    TOOL_FALLBACKS,
)
from app.agent.specialists.base import (
    BaseSpecialist,
    SpecialistMode,
    SpecialistResult,
    ResultType,
    SpecialistRegistry,
)
from app.agent.specialists.context import AnalysisContext


# ─── Test helpers ──────────────────────────────────────────────────────────────

class AlwaysFailSpecialist(BaseSpecialist):
    name = "always_fail"
    description = "Always fails with configurable error"
    mode = SpecialistMode.TOOL
    call_count = 0
    error_message = "Connection timeout"

    def get_tools(self):
        return [{"name": "fail_tool", "description": "Fails",
                 "input_schema": {"type": "object", "properties": {}, "required": []}}]

    async def _execute_tool_mode(self, tool_name, params, context):
        AlwaysFailSpecialist.call_count += 1
        raise Exception(self.error_message)


class RecoverAfterNSpecialist(BaseSpecialist):
    name = "recover_n"
    description = "Fails N times then succeeds"
    mode = SpecialistMode.TOOL
    call_count = 0
    fail_until = 1

    def get_tools(self):
        return [{"name": "recover_tool", "description": "Recovers",
                 "input_schema": {"type": "object", "properties": {}, "required": []}}]

    async def _execute_tool_mode(self, tool_name, params, context):
        RecoverAfterNSpecialist.call_count += 1
        if RecoverAfterNSpecialist.call_count <= RecoverAfterNSpecialist.fail_until:
            raise Exception("Connection timeout — transient failure")
        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.TEXT, data="ok", summary="Recovered.",
        )


class DataErrorSpecialist(BaseSpecialist):
    name = "data_err"
    description = "Returns a data error"
    mode = SpecialistMode.TOOL

    def get_tools(self):
        return [
            {"name": "data_err_tool", "description": "Data error",
             "input_schema": {"type": "object", "properties": {}, "required": []}},
            {"name": "eda_profile", "description": "Fallback",
             "input_schema": {"type": "object", "properties": {}, "required": []}},
        ]

    async def _execute_tool_mode(self, tool_name, params, context):
        if tool_name == "data_err_tool":
            return SpecialistResult(
                success=False, specialist_name=self.name,
                result_type=ResultType.ERROR, data=None,
                summary="Column not found", error='Column "salary" not found in dataset',
            )
        return SpecialistResult(
            success=True, specialist_name=self.name,
            result_type=ResultType.TABLE, data={}, summary="Profiled.",
        )


# ─── Error Classification ─────────────────────────────────────────────────────

class TestErrorClassification:
    @pytest.mark.parametrize("error_str,expected_category", [
        ("Connection timeout after 30s", ErrorCategory.TRANSIENT),
        ("Rate limit exceeded: 429", ErrorCategory.TRANSIENT),
        ("503 Service Unavailable", ErrorCategory.TRANSIENT),
        ("SSL handshake failed", ErrorCategory.TRANSIENT),
        ("Column 'salary' not found", ErrorCategory.DATA_ISSUE),
        ("KeyError: 'revenue'", ErrorCategory.DATA_ISSUE),
        ("Empty DataFrame", ErrorCategory.DATA_ISSUE),
        ("Unknown tool: foo_bar", ErrorCategory.TOOL_MISUSE),
        ("TypeError: expected int", ErrorCategory.TOOL_MISUSE),
        ("Missing required parameter", ErrorCategory.TOOL_MISUSE),
        ("Out of memory", ErrorCategory.RESOURCE_LIMIT),
        ("Quota exceeded", ErrorCategory.RESOURCE_LIMIT),
        ("A very strange glitch occurred", ErrorCategory.UNKNOWN),
    ])
    def test_classification(self, error_str, expected_category):
        result = classify_error(error_str, "test_tool")
        assert result.category == expected_category

    def test_transient_is_retryable(self):
        result = classify_error("Connection timeout", "t")
        assert result.is_retryable

    def test_data_issue_not_retryable(self):
        result = classify_error("Column not found", "t")
        assert not result.is_retryable

    def test_data_issue_suggests_profile(self):
        result = classify_error("Column not found", "t")
        assert result.fallback_tool == "eda_profile"

    def test_tool_misuse_not_retryable(self):
        result = classify_error("Unknown tool: xyz", "xyz")
        assert not result.is_retryable

    def test_unknown_defaults_to_retryable(self):
        result = classify_error("¯\\_(ツ)_/¯", "t")
        assert result.is_retryable


# ─── Circuit Breaker ──────────────────────────────────────────────────────────

class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitState()
        assert not cb.is_open
        assert cb.should_allow()

    def test_opens_after_threshold(self):
        cb = CircuitState()
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open
        assert not cb.should_allow()

    def test_closes_on_success(self):
        cb = CircuitState()
        for _ in range(3):
            cb.record_failure()
        assert cb.is_open
        cb.record_success()
        assert not cb.is_open
        assert cb.failure_count == 0

    def test_two_failures_stays_closed(self):
        cb = CircuitState()
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_open
        assert cb.should_allow()


# ─── Retry Logic ──────────────────────────────────────────────────────────────

class TestRetryLogic:
    async def test_retries_transient_then_succeeds(self):
        registry = SpecialistRegistry()
        RecoverAfterNSpecialist.call_count = 0
        RecoverAfterNSpecialist.fail_until = 1
        registry.register(RecoverAfterNSpecialist())

        mw = ErrorRecoveryMiddleware(registry, max_retries=2, base_delay=0.01)
        ctx = AnalysisContext()
        result, events = await mw.execute_with_recovery("recover_tool", {}, ctx)

        assert result.success
        assert RecoverAfterNSpecialist.call_count == 2
        assert len(events) == 2
        assert any(e.recovered for e in events)

    async def test_exhausts_retries(self):
        registry = SpecialistRegistry()
        AlwaysFailSpecialist.call_count = 0
        AlwaysFailSpecialist.error_message = "Connection timeout"
        registry.register(AlwaysFailSpecialist())

        mw = ErrorRecoveryMiddleware(registry, max_retries=2, base_delay=0.01)
        ctx = AnalysisContext()
        result, events = await mw.execute_with_recovery("fail_tool", {}, ctx)

        assert not result.success
        assert AlwaysFailSpecialist.call_count == 3  # initial + 2 retries

    async def test_no_retry_for_data_issue(self):
        registry = SpecialistRegistry()
        registry.register(DataErrorSpecialist())

        mw = ErrorRecoveryMiddleware(registry, max_retries=2, base_delay=0.01)
        ctx = AnalysisContext()
        result, events = await mw.execute_with_recovery("data_err_tool", {}, ctx)

        assert not result.success
        assert len(events) == 1
        assert events[0].error_category == "data_issue"

    async def test_no_events_on_clean_execution(self, middleware, ctx):
        result, events = await middleware.execute_with_recovery("eda_profile", {"dataset_id": "test"}, ctx)
        assert result.success
        assert len(events) == 0


# ─── Circuit Breaker Integration ──────────────────────────────────────────────

class TestCircuitBreakerIntegration:
    async def test_blocks_after_threshold(self):
        registry = SpecialistRegistry()
        AlwaysFailSpecialist.call_count = 0
        AlwaysFailSpecialist.error_message = "Connection timeout"
        registry.register(AlwaysFailSpecialist())

        mw = ErrorRecoveryMiddleware(registry, max_retries=0, base_delay=0.01)
        ctx = AnalysisContext()

        for _ in range(3):
            await mw.execute_with_recovery("fail_tool", {}, ctx)

        result, events = await mw.execute_with_recovery("fail_tool", {}, ctx)
        assert not result.success
        assert "circuit breaker" in result.summary.lower() or "circuit" in result.error.lower()
        assert any("circuit" in e.error_category for e in events)

    async def test_circuit_status(self):
        registry = SpecialistRegistry()
        AlwaysFailSpecialist.call_count = 0
        AlwaysFailSpecialist.error_message = "Connection timeout"
        registry.register(AlwaysFailSpecialist())

        mw = ErrorRecoveryMiddleware(registry, max_retries=0, base_delay=0.01)
        ctx = AnalysisContext()

        for _ in range(3):
            await mw.execute_with_recovery("fail_tool", {}, ctx)

        status = mw.get_circuit_status()
        assert "always_fail" in status
        assert status["always_fail"]["is_open"]


# ─── Fallback Suggestions ─────────────────────────────────────────────────────

class TestFallbackSuggestions:
    async def test_fallback_in_metadata(self):
        registry = SpecialistRegistry()
        registry.register(DataErrorSpecialist())

        mw = ErrorRecoveryMiddleware(registry, max_retries=0, base_delay=0.01)
        ctx = AnalysisContext()
        result, events = await mw.execute_with_recovery("data_err_tool", {}, ctx)

        assert result.metadata.get("fallback_tool") == "eda_profile"

    async def test_unknown_tool_handled(self):
        mw = ErrorRecoveryMiddleware(SpecialistRegistry())
        ctx = AnalysisContext()
        result, events = await mw.execute_with_recovery("nonexistent", {}, ctx)

        assert not result.success
        assert len(events) == 1
        assert "Unknown tool" in result.summary

    def test_fallback_map_entries(self):
        assert "eda_describe" in TOOL_FALLBACKS
        assert "viz_bar_chart" in TOOL_FALLBACKS


# ─── Error Context & Reset ─────────────────────────────────────────────────────

class TestErrorContext:
    async def test_error_context_accumulates(self):
        registry = SpecialistRegistry()
        registry.register(DataErrorSpecialist())

        mw = ErrorRecoveryMiddleware(registry, max_retries=0, base_delay=0.01)
        ctx = AnalysisContext()
        await mw.execute_with_recovery("data_err_tool", {}, ctx)
        await mw.execute_with_recovery("data_err_tool", {}, ctx)

        error_ctx = mw.get_error_context_for_reflector()
        assert "Errors encountered" in error_ctx
        assert "data_issue" in error_ctx

    async def test_no_error_context_when_clean(self, middleware, ctx):
        await middleware.execute_with_recovery("eda_profile", {"dataset_id": "test"}, ctx)
        assert middleware.get_error_context_for_reflector() == ""

    async def test_reset_clears_state(self):
        registry = SpecialistRegistry()
        registry.register(DataErrorSpecialist())

        mw = ErrorRecoveryMiddleware(registry, max_retries=0, base_delay=0.01)
        ctx = AnalysisContext()
        await mw.execute_with_recovery("data_err_tool", {}, ctx)

        mw.reset()
        assert mw.get_error_context_for_reflector() == ""
        assert mw.get_circuit_status() == {}


# ─── RecoveryEvent Serialization ──────────────────────────────────────────────

class TestRecoveryEvent:
    def test_serialization(self):
        ev = RecoveryEvent(
            tool_name="eda_profile", attempt=2, max_attempts=3,
            error_category="transient", error_message="timeout",
            action_taken="Retrying", suggestion="Wait.",
            fallback_tool="eda_data_quality", recovered=False,
        )
        data = ev.to_stream_data()
        assert data["tool_name"] == "eda_profile"
        assert data["attempt"] == 2
        assert data["fallback_tool"] == "eda_data_quality"
        assert len(data) == 9
