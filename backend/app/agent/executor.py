"""
Executor — Phase 2 of the Plan-Execute-Reflect loop.

Takes an analysis plan and executes it step by step, delegating tool calls
to the specialist registry. Also handles the Claude tool-use loop for
dynamic execution when the plan has no pre-defined steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

import structlog
from anthropic import AsyncAnthropic
from anthropic.types import Message as AnthropicMessage

from app.agent.memory import ConversationMemory
from app.agent.planner import AnalysisPlan, AnalysisStep
from app.agent.prompts import SUPERVISOR_SYSTEM_PROMPT
from app.agent.specialists.base import SpecialistRegistry, SpecialistResult
from app.agent.specialists.context import AnalysisContext
from app.config import settings
from app.models.schemas import StreamEvent, StreamEventType

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionResult:
    """Accumulated results from executing an analysis plan."""
    specialist_results: list[SpecialistResult] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class Executor:
    """
    Executes analysis plans by delegating to specialists.

    Two execution modes:
    1. Plan-based: walks through AnalysisPlan steps sequentially
    2. Dynamic (tool-use loop): lets Claude decide which tools to call in real-time
    """

    def __init__(
        self,
        client: AsyncAnthropic,
        registry: SpecialistRegistry,
        max_tool_calls: int = 15,
    ) -> None:
        self._client = client
        self._registry = registry
        self._max_tool_calls = max_tool_calls

    async def execute_plan(
        self,
        plan: AnalysisPlan,
        context: AnalysisContext,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Execute a structured plan step by step.
        Yields StreamEvents for each specialist call and result.
        """
        execution = ExecutionResult()

        for step in plan.steps:
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

            result = await self._execute_step(step, context)
            execution.specialist_results.append(result)

            if not result.success:
                execution.errors.append(result.error or "Unknown error")
                yield StreamEvent(
                    event_type=StreamEventType.ERROR,
                    data={"step": step.step_number, "error": result.error},
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

                        yield StreamEvent(
                            event_type=StreamEventType.SPECIALIST_CALL,
                            data={
                                "tool_name": block.name,
                                "params": block.input,
                            },
                            specialist_name=block.name,
                        )

                        result = await self._registry.execute_tool(
                            block.name, block.input, context
                        )

                        yield StreamEvent(
                            event_type=StreamEventType.SPECIALIST_RESULT,
                            data={
                                "result_type": result.result_type.value,
                                "summary": result.summary,
                                "data": self._serialize_result_data(result),
                            },
                            specialist_name=result.specialist_name,
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

    async def _execute_step(
        self, step: AnalysisStep, context: AnalysisContext
    ) -> SpecialistResult:
        """Execute a single plan step via the specialist registry."""
        return await self._registry.execute_tool(
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
        data = result.data
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool, list, dict)):
            return data
        return str(data)[:2000]
