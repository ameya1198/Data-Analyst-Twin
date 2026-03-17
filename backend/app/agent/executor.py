"""
Executor — Phase 2 of the Plan-Execute-Reflect loop.

Takes an analysis plan and executes it step by step, delegating tool calls
to the specialist registry via the ErrorRecoveryMiddleware. Also handles the
Claude tool-use loop for dynamic execution when the plan has no pre-defined steps.

All tool calls go through the middleware, which provides:
- Retry with exponential backoff for transient failures
- Circuit breaker per specialist
- Error classification and fallback tool suggestions
- Recovery events streamed to the frontend
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

import structlog
from anthropic import AsyncAnthropic
from anthropic.types import Message as AnthropicMessage

from app.agent.error_recovery import ErrorRecoveryMiddleware, RecoveryEvent
from app.agent.memory import ConversationMemory
from app.agent.planner import AnalysisPlan, AnalysisStep
from app.agent.prompts import SUPERVISOR_SYSTEM_PROMPT
from app.agent.specialists.base import ResultType, SpecialistRegistry, SpecialistResult
from app.agent.specialists.context import AnalysisContext
from app.config import settings
from app.guardrails.confirmation import ConfirmationManager
from app.models.schemas import StreamEvent, StreamEventType

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionResult:
    """Accumulated results from executing an analysis plan."""
    specialist_results: list[SpecialistResult] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recovery_events: list[RecoveryEvent] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class Executor:
    """
    Executes analysis plans by delegating to specialists via ErrorRecoveryMiddleware.

    Two execution modes:
    1. Plan-based: walks through AnalysisPlan steps sequentially
    2. Dynamic (tool-use loop): lets Claude decide which tools to call in real-time
    """

    def __init__(
        self,
        client: AsyncAnthropic,
        registry: SpecialistRegistry,
        middleware: ErrorRecoveryMiddleware | None = None,
        max_tool_calls: int = 15,
        confirmation_manager: ConfirmationManager | None = None,
    ) -> None:
        self._client = client
        self._registry = registry
        self._middleware = middleware or ErrorRecoveryMiddleware(registry)
        self._max_tool_calls = max_tool_calls
        self._confirmation_manager = confirmation_manager

    @property
    def middleware(self) -> ErrorRecoveryMiddleware:
        return self._middleware

    async def _check_confirmation(
        self,
        tool_name: str,
        params: dict,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        If the tool requires human-in-the-loop confirmation, yield a
        CONFIRMATION_REQUEST event and block until the user responds.

        Yields either nothing (no confirmation needed, or approved) or a
        specialist_result with cancellation.
        """
        if not self._confirmation_manager:
            return

        specialist = self._registry.get_specialist_for_tool(tool_name)
        if not specialist:
            return

        if not self._confirmation_manager.needs_confirmation(specialist.name, tool_name):
            return

        request = self._confirmation_manager.build_request(
            specialist.name, tool_name, params,
        )
        self._confirmation_manager.create_pending(request.request_id)

        yield StreamEvent(
            event_type=StreamEventType.CONFIRMATION_REQUEST,
            data=request.to_stream_data(),
            specialist_name=specialist.name,
        )

        response = await self._confirmation_manager.wait_for(request.request_id)

        if not response.approved:
            reason = response.user_message or "Operation cancelled by user."
            logger.info(
                "operation_rejected_by_user",
                tool=tool_name,
                request_id=request.request_id,
            )
            yield StreamEvent(
                event_type=StreamEventType.SPECIALIST_RESULT,
                data={
                    "result_type": ResultType.ERROR.value,
                    "summary": reason,
                    "data": None,
                    "user_cancelled": True,
                },
                specialist_name=specialist.name,
            )

    async def execute_plan(
        self,
        plan: AnalysisPlan,
        context: AnalysisContext,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Execute a structured plan step by step, with error recovery.
        Yields StreamEvents for each specialist call, recovery attempt, and result.
        """
        execution = ExecutionResult()

        for step in plan.steps:
            # Human-in-the-loop confirmation for destructive operations
            cancelled = False
            async for conf_event in self._check_confirmation(step.tool_name, step.tool_params):
                yield conf_event
                if (
                    conf_event.event_type == StreamEventType.SPECIALIST_RESULT
                    and isinstance(conf_event.data, dict)
                    and conf_event.data.get("user_cancelled")
                ):
                    cancelled = True

            if cancelled:
                execution.skipped_steps.append(step.tool_name)
                continue

            yield StreamEvent(
                event_type=StreamEventType.SPECIALIST_CALL,
                data={
                    "step_number": step.step_number,
                    "description": step.description,
                    "tool_name": step.tool_name,
                    "rationale": step.rationale,
                },
                specialist_name=step.tool_name,
            )

            result, recovery_events = await self._execute_step_with_recovery(step, context)
            execution.specialist_results.append(result)
            execution.recovery_events.extend(recovery_events)

            # Stream any recovery events that occurred
            for rev in recovery_events:
                yield StreamEvent(
                    event_type=StreamEventType.ERROR_RECOVERY,
                    data=rev.to_stream_data(),
                    specialist_name=step.tool_name,
                )

            if not result.success:
                execution.errors.append(result.error or "Unknown error")

                fallback = result.metadata.get("fallback_tool") if result.metadata else None
                yield StreamEvent(
                    event_type=StreamEventType.ERROR,
                    data={
                        "step": step.step_number,
                        "error": result.error,
                        "error_category": result.metadata.get("error_category", "unknown") if result.metadata else "unknown",
                        "suggestion": result.metadata.get("suggestion", "") if result.metadata else "",
                        "fallback_tool": fallback,
                    },
                    specialist_name=step.tool_name,
                )
            else:
                yield StreamEvent(
                    event_type=StreamEventType.SPECIALIST_RESULT,
                    data={
                        "step_number": step.step_number,
                        "result_type": result.result_type.value,
                        "summary": result.summary,
                        "data": self._serialize_result_data(result),
                    },
                    specialist_name=result.specialist_name,
                )

    async def execute_dynamic(
        self,
        user_message: str,
        context: AnalysisContext,
        memory: ConversationMemory,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Dynamic tool-use loop — Claude decides which tools to call.
        Used as fallback when the planner can't produce a structured plan,
        or for follow-up questions within a conversation.
        """
        system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
            dataset_summaries=context.get_dataset_summaries(),
            recent_results=context.get_recent_results_summary(),
            capabilities_summary=self._registry.get_capabilities_summary(),
        )

        memory.add_user_message(user_message)
        tool_call_count = 0

        while tool_call_count < self._max_tool_calls:
            response = await self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                system=system_prompt,
                messages=memory.get_messages(),
                tools=self._registry.get_all_tools(),
            )

            if response.stop_reason == "end_turn":
                text_content = self._extract_text(response)
                memory.add_assistant_message(response.content)
                yield StreamEvent(
                    event_type=StreamEventType.FINAL_RESPONSE,
                    data=text_content,
                )
                return

            if response.stop_reason == "tool_use":
                memory.add_assistant_message(response.content)

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_call_count += 1

                        # Human-in-the-loop confirmation
                        cancelled = False
                        async for conf_event in self._check_confirmation(
                            block.name, block.input if isinstance(block.input, dict) else {},
                        ):
                            yield conf_event
                            if (
                                conf_event.event_type == StreamEventType.SPECIALIST_RESULT
                                and isinstance(conf_event.data, dict)
                                and conf_event.data.get("user_cancelled")
                            ):
                                cancelled = True

                        if cancelled:
                            tool_results.append({
                                "tool_use_id": block.id,
                                "content": "Operation cancelled by user.",
                            })
                            continue

                        yield StreamEvent(
                            event_type=StreamEventType.SPECIALIST_CALL,
                            data={
                                "tool_name": block.name,
                                "params": block.input,
                            },
                            specialist_name=block.name,
                        )

                        result, recovery_events = await self._middleware.execute_with_recovery(
                            block.name, block.input, context
                        )

                        for rev in recovery_events:
                            yield StreamEvent(
                                event_type=StreamEventType.ERROR_RECOVERY,
                                data=rev.to_stream_data(),
                                specialist_name=block.name,
                            )

                        if result.success:
                            yield StreamEvent(
                                event_type=StreamEventType.SPECIALIST_RESULT,
                                data={
                                    "result_type": result.result_type.value,
                                    "summary": result.summary,
                                    "data": self._serialize_result_data(result),
                                },
                                specialist_name=result.specialist_name,
                            )
                        else:
                            yield StreamEvent(
                                event_type=StreamEventType.ERROR,
                                data={
                                    "error": result.error,
                                    "error_category": result.metadata.get("error_category", "unknown") if result.metadata else "unknown",
                                    "suggestion": result.metadata.get("suggestion", "") if result.metadata else "",
                                    "fallback_tool": result.metadata.get("fallback_tool") if result.metadata else None,
                                },
                                specialist_name=block.name,
                            )

                        tool_results.append({
                            "tool_use_id": block.id,
                            "content": result.to_llm_context(),
                        })

                memory.add_tool_results_batch(tool_results)

            else:
                # Unexpected stop reason
                logger.warning("executor_unexpected_stop", stop_reason=response.stop_reason)
                text_content = self._extract_text(response)
                yield StreamEvent(
                    event_type=StreamEventType.FINAL_RESPONSE,
                    data=text_content or "Analysis complete.",
                )
                return

        yield StreamEvent(
            event_type=StreamEventType.ERROR,
            data={"error": f"Reached maximum tool call limit ({self._max_tool_calls})"},
        )

    async def _execute_step_with_recovery(
        self, step: AnalysisStep, context: AnalysisContext
    ) -> tuple[SpecialistResult, list[RecoveryEvent]]:
        """Execute a single plan step via the middleware (retry + circuit breaker)."""
        return await self._middleware.execute_with_recovery(
            step.tool_name, step.tool_params, context
        )

    def _extract_text(self, response: AnthropicMessage) -> str:
        """Pull text content out of a Claude response."""
        parts = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts)

    def _serialize_result_data(self, result: SpecialistResult) -> Any:
        """Make result data JSON-serializable for streaming."""
        return _sanitize_for_json(result.data)


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert numpy/pandas types to native Python for JSON serialization."""
    import numpy as np

    if obj is None:
        return None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(obj, np.ndarray):
        return [_sanitize_for_json(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)[:2000]
