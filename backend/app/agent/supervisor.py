"""
Supervisor — the main orchestrator of the Data Analyst Digital Twin.

Implements the Plan-Execute-Reflect loop:
1. PLAN: Ask Claude to create a structured analysis plan
2. EXECUTE: Walk through the plan, delegating tool calls to specialists
3. REFLECT: Evaluate results — re-plan if gaps are found
4. SYNTHESIZE: Generate a final narrative response

Falls back to dynamic tool-use loop when planning isn't possible
(e.g., no data loaded, or simple conversational follow-ups).
"""

from __future__ import annotations

import time
from typing import AsyncGenerator

import structlog
from anthropic import AsyncAnthropic

from app.agent.executor import Executor
from app.agent.memory import ConversationMemory
from app.agent.planner import AnalysisPlan, Planner
from app.agent.prompts import SUPERVISOR_SYSTEM_PROMPT, SYNTHESIZER_PROMPT
from app.agent.reflector import Reflector
from app.agent.specialists.base import ResultType, SpecialistRegistry, SpecialistResult
from app.agent.specialists.context import AnalysisContext
from app.config import settings
from app.models.schemas import StreamEvent, StreamEventType

logger = structlog.get_logger(__name__)


class Supervisor:
    """
    Top-level agent orchestrator.

    One Supervisor instance per session. It holds the conversation memory,
    analysis context, and coordinates the Plan-Execute-Reflect cycle.
    """

    def __init__(
        self,
        registry: SpecialistRegistry,
        context: AnalysisContext | None = None,
        max_reflect_cycles: int = 2,
        max_tool_calls_per_turn: int | None = None,
    ) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._registry = registry
        self.context = context or AnalysisContext()
        self.memory = ConversationMemory()

        self._planner = Planner(self._client, registry)
        self._executor = Executor(
            self._client,
            registry,
            max_tool_calls=max_tool_calls_per_turn or settings.max_specialist_calls_per_turn,
        )
        self._reflector = Reflector(self._client, registry)
        self._max_reflect_cycles = max_reflect_cycles

    async def run(self, user_message: str) -> AsyncGenerator[StreamEvent, None]:
        """
        Main entry point — process a user message through the full agent loop.

        Yields StreamEvents that the WebSocket handler forwards to the frontend.
        """
        start_time = time.perf_counter()

        logger.info(
            "supervisor_run_start",
            session_id=self.context.session_id,
            has_data=self.context.has_data,
            message_preview=user_message[:100],
        )

        if not self.context.has_data:
            async for event in self._handle_no_data(user_message):
                yield event
            return

        # --- PLAN ---
        plan = await self._plan(user_message)
        yield StreamEvent(
            event_type=StreamEventType.PLAN,
            data=plan.to_display(),
        )

        if not plan.steps:
            # Planner couldn't produce steps — fall back to dynamic execution
            logger.info("supervisor_fallback_dynamic", reason="empty_plan")
            async for event in self._executor.execute_dynamic(
                user_message, self.context, self.memory
            ):
                yield event
            return

        # --- EXECUTE ---
        all_results: list[SpecialistResult] = []
        async for event in self._executor.execute_plan(plan, self.context):
            yield event
            if event.event_type == StreamEventType.SPECIALIST_RESULT:
                matched = self._find_latest_result()
                if matched:
                    all_results.append(matched)

        # --- REFLECT ---
        for cycle in range(self._max_reflect_cycles):
            reflection = await self._reflector.reflect(
                user_message, all_results, self.context
            )

            yield StreamEvent(
                event_type=StreamEventType.REFLECTION,
                data={
                    "cycle": cycle + 1,
                    "is_satisfactory": reflection.is_satisfactory,
                    "quality_score": reflection.quality_score,
                    "strengths": reflection.strengths,
                    "gaps": reflection.gaps,
                },
            )

            if reflection.is_satisfactory:
                break

            # Re-plan to address gaps
            logger.info(
                "supervisor_replan",
                cycle=cycle + 1,
                follow_up=reflection.follow_up[:100],
            )
            follow_up_plan = await self._plan(reflection.follow_up)
            if follow_up_plan.steps:
                yield StreamEvent(
                    event_type=StreamEventType.PLAN,
                    data=follow_up_plan.to_display(),
                )
                async for event in self._executor.execute_plan(
                    follow_up_plan, self.context
                ):
                    yield event
                    if event.event_type == StreamEventType.SPECIALIST_RESULT:
                        matched = self._find_latest_result()
                        if matched:
                            all_results.append(matched)

        # --- SYNTHESIZE ---
        final_response = await self._synthesize(user_message, all_results)

        self.memory.add_user_message(user_message)
        self.memory.add_assistant_message(final_response)

        yield StreamEvent(
            event_type=StreamEventType.FINAL_RESPONSE,
            data=final_response,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "supervisor_run_complete",
            session_id=self.context.session_id,
            elapsed_ms=round(elapsed_ms, 2),
            result_count=len(all_results),
        )

    async def _plan(self, message: str) -> AnalysisPlan:
        """Create an analysis plan via the Planner."""
        return await self._planner.create_plan(message, self.context)

    async def _synthesize(
        self, user_message: str, results: list[SpecialistResult]
    ) -> str:
        """Generate the final narrative response using Claude."""
        results_summary = "\n".join(r.to_llm_context() for r in results)

        # Get the most recent reflection for context
        reflection_summary = self.context.get_recent_results_summary(limit=5)

        system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
            dataset_summaries=self.context.get_dataset_summaries(),
            recent_results=self.context.get_recent_results_summary(),
            capabilities_summary=self._registry.get_capabilities_summary(),
        )

        synth_message = SYNTHESIZER_PROMPT.format(
            user_message=user_message,
            results_summary=results_summary,
            reflection_summary=reflection_summary,
        )

        response = await self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": synth_message}],
        )

        logger.info(
            "supervisor_synthesize_complete",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        return response.content[0].text

    async def _handle_no_data(self, user_message: str) -> AsyncGenerator[StreamEvent, None]:
        """Handle queries when no dataset is loaded yet."""
        system_prompt = (
            "You are a data analyst digital twin. The user hasn't uploaded any data yet. "
            "Help them understand what you can do, or ask them to upload a dataset. "
            "Be friendly and specific about your capabilities: EDA, visualization, "
            "statistical analysis, data cleaning, and natural language insights."
        )

        self.memory.add_user_message(user_message)

        response = await self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=system_prompt,
            messages=self.memory.get_messages(),
        )

        text = response.content[0].text
        self.memory.add_assistant_message(text)

        yield StreamEvent(
            event_type=StreamEventType.FINAL_RESPONSE,
            data=text,
        )

    def _find_latest_result(self) -> SpecialistResult | None:
        """Get the most recently added result from the context."""
        if self.context.results:
            entry = self.context.results[-1]
            try:
                result_type = ResultType(entry.result_type)
            except ValueError:
                result_type = ResultType.TEXT
            return SpecialistResult(
                success=entry.result_type != "error",
                specialist_name=entry.specialist_name,
                result_type=result_type,
                data=entry.data,
                summary=entry.step_description,
                metadata=entry.metadata,
            )
        return None
