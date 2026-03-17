"""
Supervisor — the main orchestrator of the Data Analyst Digital Twin.

Routes user requests to the right execution mode based on intent classification:

    DIRECT:         0 LLM calls  — known tool, skip Plan/Reflect/Synthesize
    FOCUSED:        2 LLM calls  — Plan + Execute + lightweight Synthesize (skip Reflect)
    FULL:           3-5 LLM calls — Plan + Execute + Reflect (up to 2 cycles) + Synthesize
    CONVERSATIONAL: 1+ LLM calls — dynamic tool-use loop, Claude decides tools

Examples:
    "Profile my data"              → DIRECT   (just eda_profile, return result)
    "Write SQL for top users"      → FOCUSED  (plan + execute, skip reflect)
    "What insights can you find?"  → FULL     (full Plan-Execute-Reflect-Synthesize)
    "Now show me a chart of that"  → CONVERSATIONAL (follow-up, dynamic)
"""

from __future__ import annotations

import time
from typing import AsyncGenerator

import structlog
from anthropic import AsyncAnthropic

from app.agent.error_recovery import ErrorRecoveryMiddleware
from app.agent.executor import Executor
from app.agent.intent import (
    ClassifiedIntent,
    ExecutionMode,
    IntentClassifier,
)
from app.agent.memory import ConversationMemory
from app.agent.planner import AnalysisPlan, Planner
from app.agent.prompts import (
    FOCUSED_SYNTHESIS_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
    SYNTHESIZER_PROMPT,
)
from app.agent.reflector import Reflector
from app.agent.specialists.base import ResultType, SpecialistRegistry, SpecialistResult
from app.agent.specialists.context import AnalysisContext
from app.config import settings
from app.guardrails.confirmation import ConfirmationManager
from app.models.schemas import StreamEvent, StreamEventType
from app.observability.metrics import metrics_collector

logger = structlog.get_logger(__name__)


class Supervisor:
    """
    Top-level agent orchestrator.

    One Supervisor instance per session. It holds the conversation memory,
    analysis context, and coordinates execution via intent-based routing.
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

        self._middleware = ErrorRecoveryMiddleware(registry)
        self._confirmation_manager = ConfirmationManager()
        self._intent_classifier = IntentClassifier()
        self._current_trace_id: str | None = None
        self._planner = Planner(self._client, registry)
        self._executor = Executor(
            self._client,
            registry,
            middleware=self._middleware,
            max_tool_calls=max_tool_calls_per_turn or settings.max_specialist_calls_per_turn,
            confirmation_manager=self._confirmation_manager,
        )
        self._reflector = Reflector(self._client, registry)
        self._max_reflect_cycles = max_reflect_cycles
        self._scoped_dataset_ids: list[str] | None = None

    @property
    def confirmation_manager(self) -> ConfirmationManager:
        return self._confirmation_manager

    async def reload_memory(self, session_id: str) -> int:
        """
        Load persisted conversation history from SQLite into memory.

        Called once when a supervisor is first created for a returning session,
        so the agent remembers past interactions even after a server restart.
        Returns the number of messages loaded.
        """
        from app.database import load_messages

        rows = await load_messages(session_id)
        pairs = [(r.role, r.content or "") for r in rows]
        loaded = self.memory.load_history(pairs)
        if loaded:
            logger.info(
                "memory_reloaded",
                session_id=session_id,
                messages_loaded=loaded,
            )
        return loaded

    async def run(
        self,
        user_message: str,
        trace_id: str | None = None,
        dataset_ids: list[str] | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Main entry point — classify intent, route to the right execution mode.
        Yields StreamEvents that the WebSocket handler forwards to the frontend.

        Every yielded StreamEvent carries the same ``trace_id`` so the client
        can correlate all events belonging to one user message.

        When dataset_ids is provided (from frontend selection), the planner and
        prompts only include those datasets, so the agent analyzes the right data.
        """
        self._current_trace_id = trace_id
        self._scoped_dataset_ids = dataset_ids
        start_time = time.perf_counter()

        logger.info(
            "supervisor_run_start",
            session_id=self.context.session_id,
            has_data=self.context.has_data,
            message_preview=user_message[:100],
        )

        if not self.context.has_data:
            async for event in self._handle_no_data(user_message):
                yield self._tag(event)
            return

        # ─── Intent Classification ────────────────────────────────────
        classified = self._intent_classifier.classify(
            user_message,
            has_conversation_history=self.memory.has_history,
            has_data=self.context.has_data,
        )

        yield self._tag(StreamEvent(
            event_type=StreamEventType.INTENT,
            data={
                "intent": classified.intent.value,
                "mode": classified.mode.value,
                "confidence": classified.confidence,
                "reasoning": classified.reasoning,
            },
        ))

        # ─── Route by execution mode ─────────────────────────────────
        if classified.mode == ExecutionMode.DIRECT:
            async for event in self._run_direct(user_message, classified):
                yield self._tag(event)

        elif classified.mode == ExecutionMode.FOCUSED:
            async for event in self._run_focused(user_message):
                yield self._tag(event)

        elif classified.mode == ExecutionMode.FULL:
            async for event in self._run_full(user_message):
                yield self._tag(event)

        elif classified.mode == ExecutionMode.CONVERSATIONAL:
            async for event in self._run_conversational(
                user_message, self._scoped_dataset_ids
            ):
                yield self._tag(event)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "supervisor_run_complete",
            session_id=self.context.session_id,
            mode=classified.mode.value,
            intent=classified.intent.value,
            elapsed_ms=round(elapsed_ms, 2),
        )

    def _tag(self, event: StreamEvent) -> StreamEvent:
        """Stamp trace_id onto an outgoing StreamEvent."""
        if self._current_trace_id and not event.trace_id:
            event.trace_id = self._current_trace_id
        return event

    # ─── DIRECT Mode ──────────────────────────────────────────────────
    # 0 LLM calls — known tool, known params, just execute and return

    async def _run_direct(
        self, user_message: str, classified: ClassifiedIntent,
    ) -> AsyncGenerator[StreamEvent, None]:
        tool_name = classified.direct_tool
        if not tool_name:
            async for event in self._run_focused(user_message):
                yield event
            return

        # Use user-selected dataset when available; otherwise all datasets
        ids = (
            self._scoped_dataset_ids
            if (self._scoped_dataset_ids and len(self._scoped_dataset_ids) > 0)
            else self.context.dataset_ids
        )
        params = self._intent_classifier.get_direct_params(classified, ids)

        yield StreamEvent(
            event_type=StreamEventType.SPECIALIST_CALL,
            data={
                "tool_name": tool_name,
                "params": params,
                "mode": "direct",
            },
            specialist_name=tool_name,
        )

        t0 = time.perf_counter()
        result, recovery_events = await self._middleware.execute_with_recovery(
            tool_name, params, self.context,
        )
        spec_latency = (time.perf_counter() - t0) * 1000
        metrics = metrics_collector.get_or_create(self.context.session_id)
        metrics.record_specialist_call(tool_name, spec_latency, result.success)

        for rev in recovery_events:
            yield StreamEvent(
                event_type=StreamEventType.ERROR_RECOVERY,
                data=rev.to_stream_data(),
                specialist_name=tool_name,
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
                data={"error": result.error, "summary": result.summary},
                specialist_name=tool_name,
            )

        self.memory.add_user_message(user_message)

        final_text = await self._synthesize_lightweight(user_message, [result])
        self.memory.add_assistant_message(final_text)

        yield StreamEvent(
            event_type=StreamEventType.FINAL_RESPONSE,
            data=final_text,
        )

    # ─── FOCUSED Mode ─────────────────────────────────────────────────
    # 2 LLM calls — Plan + Execute + lightweight Synthesize (skip Reflect)

    async def _run_focused(
        self, user_message: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        plan = await self._plan(user_message)
        yield StreamEvent(
            event_type=StreamEventType.PLAN,
            data=plan.to_display(),
        )

        if not plan.steps:
            async for event in self._run_conversational(user_message, self._scoped_dataset_ids):
                yield event
            return

        all_results: list[SpecialistResult] = []
        async for event in self._executor.execute_plan(plan, self.context):
            yield event
            if event.event_type == StreamEventType.SPECIALIST_RESULT:
                matched = self._find_latest_result()
                if matched:
                    all_results.append(matched)

        final_response = await self._synthesize_lightweight(user_message, all_results)

        self.memory.add_user_message(user_message)
        self.memory.add_assistant_message(final_response)

        yield StreamEvent(
            event_type=StreamEventType.FINAL_RESPONSE,
            data=final_response,
        )

    # ─── FULL Mode ────────────────────────────────────────────────────
    # 3-5 LLM calls — Plan + Execute + Reflect (up to 2 cycles) + Synthesize

    async def _run_full(
        self, user_message: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        plan = await self._plan(user_message)
        yield StreamEvent(
            event_type=StreamEventType.PLAN,
            data=plan.to_display(),
        )

        if not plan.steps:
            async for event in self._run_conversational(user_message, self._scoped_dataset_ids):
                yield event
            return

        # Execute
        all_results: list[SpecialistResult] = []
        async for event in self._executor.execute_plan(plan, self.context):
            yield event
            if event.event_type == StreamEventType.SPECIALIST_RESULT:
                matched = self._find_latest_result()
                if matched:
                    all_results.append(matched)

        # Reflect (up to max_reflect_cycles)
        error_context = self._middleware.get_error_context_for_reflector()
        for cycle in range(self._max_reflect_cycles):
            reflection = await self._reflector.reflect(
                user_message, all_results, self.context, error_context=error_context,
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

        # Synthesize (full narrative)
        final_response = await self._synthesize_full(user_message, all_results)

        self.memory.add_user_message(user_message)
        self.memory.add_assistant_message(final_response)

        yield StreamEvent(
            event_type=StreamEventType.FINAL_RESPONSE,
            data=final_response,
        )

    # ─── CONVERSATIONAL Mode ──────────────────────────────────────────
    # Dynamic tool-use loop — Claude decides which tools to call

    async def _run_conversational(
        self,
        user_message: str,
        dataset_ids: list[str] | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        async for event in self._executor.execute_dynamic(
            user_message,
            self.context,
            self.memory,
            dataset_ids=dataset_ids,
        ):
            yield event

    # ─── Planning ─────────────────────────────────────────────────────

    async def _plan(self, message: str) -> AnalysisPlan:
        return await self._planner.create_plan(
            message,
            self.context,
            dataset_ids=self._scoped_dataset_ids,
        )

    # ─── Synthesis ────────────────────────────────────────────────────

    async def _synthesize_full(
        self, user_message: str, results: list[SpecialistResult],
    ) -> str:
        """Full narrative synthesis — used in FULL mode."""
        results_summary = "\n".join(r.to_llm_context() for r in results)
        reflection_summary = self.context.get_recent_results_summary(limit=5)

        system_prompt = self._build_system_prompt()
        synth_message = SYNTHESIZER_PROMPT.format(
            user_message=user_message,
            results_summary=results_summary,
            reflection_summary=reflection_summary,
        )

        t0 = time.perf_counter()
        response = await self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": synth_message}],
        )
        latency = (time.perf_counter() - t0) * 1000

        metrics = metrics_collector.get_or_create(self.context.session_id)
        metrics.record_llm_call(response.usage.input_tokens, response.usage.output_tokens, latency)

        logger.info(
            "supervisor_synthesize_full",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=round(latency, 2),
        )
        return response.content[0].text

    async def _synthesize_lightweight(
        self, user_message: str, results: list[SpecialistResult],
    ) -> str:
        """Lightweight synthesis — used in FOCUSED mode. One short LLM call."""
        results_summary = "\n".join(r.to_llm_context() for r in results)

        synth_message = FOCUSED_SYNTHESIS_PROMPT.format(
            user_message=user_message,
            results_summary=results_summary,
        )

        t0 = time.perf_counter()
        response = await self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=(
                "You are a data analyst giving concise answers. "
                "FIRST sentence = the answer (a number or finding). No preamble. "
                "You have REAL data in the results — cite actual numbers, means, p-values, row counts. "
                "Bold key values with **markdown**. "
                "For SQL: If user asked for ONLY the query (e.g. 'just the query', 'SQL only', 'that\\'s all'), output ONLY the ```sql block. Otherwise show query + results table. "
                "NEVER say 'Phase 1', tool names, 'Based on my analysis', or 'Let me'. "
                "NEVER add 'Next Steps' or 'Recommendations' unless asked. "
                "3-6 sentences max. Every sentence must contain a specific number."
            ),
            messages=[{"role": "user", "content": synth_message}],
        )
        latency = (time.perf_counter() - t0) * 1000

        metrics = metrics_collector.get_or_create(self.context.session_id)
        metrics.record_llm_call(response.usage.input_tokens, response.usage.output_tokens, latency)

        logger.info(
            "supervisor_synthesize_lightweight",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=round(latency, 2),
        )
        return response.content[0].text

    # ─── No-data handler ──────────────────────────────────────────────

    async def _handle_no_data(self, user_message: str) -> AsyncGenerator[StreamEvent, None]:
        self.memory.add_user_message(user_message)

        text = (
            "I don't have any datasets loaded right now. This can happen if the server "
            "restarted since your last upload.\n\n"
            "**Please re-upload your dataset** using the upload panel on the left sidebar, "
            "and then ask your question again. I'll be ready to analyze it right away!\n\n"
            "I can help with:\n"
            "- **Exploratory Analysis** — profiling, distributions, correlations, outliers\n"
            "- **Visualizations** — interactive charts following best practices\n"
            "- **SQL Queries** — write and execute analytical SQL on your data\n"
            "- **Statistical Tests** — hypothesis testing, A/B tests, regression\n"
            "- **Data Cleaning** — deduplication, missing values, standardization"
        )
        self.memory.add_assistant_message(text)

        yield StreamEvent(
            event_type=StreamEventType.FINAL_RESPONSE,
            data=text,
        )

    # ─── Helpers ──────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        return SUPERVISOR_SYSTEM_PROMPT.format(
            dataset_summaries=self.context.get_dataset_summaries(
                limit_to_ids=self._scoped_dataset_ids
            ),
            recent_results=self.context.get_recent_results_summary(),
            capabilities_summary=self._registry.get_capabilities_summary(),
        )

    def _find_latest_result(self) -> SpecialistResult | None:
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

    def _serialize_result_data(self, result: SpecialistResult):
        from app.agent.executor import _sanitize_for_json
        return _sanitize_for_json(result.data)
