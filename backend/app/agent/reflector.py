"""
Reflector — Phase 3 of the Plan-Execute-Reflect loop.

Evaluates whether the analysis results adequately answer the user's question.
If not, it suggests additional analysis for the supervisor to re-plan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

import structlog
from anthropic import AsyncAnthropic

from app.agent.prompts import SUPERVISOR_SYSTEM_PROMPT, REFLECTOR_PROMPT
from app.agent.specialists.base import SpecialistRegistry, SpecialistResult
from app.agent.specialists.context import AnalysisContext
from app.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class Reflection:
    is_satisfactory: bool
    quality_score: int
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    follow_up: str = ""
    suggested_narrative: str = ""
    raw_response: Optional[str] = None


class Reflector:
    """Evaluates analysis quality and decides whether more work is needed."""

    def __init__(self, client: AsyncAnthropic, registry: SpecialistRegistry) -> None:
        self._client = client
        self._registry = registry

    async def reflect(
        self,
        user_message: str,
        results: list[SpecialistResult],
        context: AnalysisContext,
        error_context: str = "",
    ) -> Reflection:
        results_summary = "\n".join(r.to_llm_context() for r in results)
        if error_context:
            results_summary += f"\n\n{error_context}"

        system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
            dataset_summaries=context.get_dataset_summaries(),
            recent_results=context.get_recent_results_summary(),
            capabilities_summary=self._registry.get_capabilities_summary(),
        )

        reflector_message = REFLECTOR_PROMPT.format(
            user_message=user_message,
            results_summary=results_summary,
        )

        logger.info("reflector_start", result_count=len(results))

        response = await self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": reflector_message}],
        )

        raw_text = response.content[0].text
        logger.info(
            "reflector_complete",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        return self._parse_reflection(raw_text)

    def _parse_reflection(self, raw_text: str) -> Reflection:
        try:
            clean = raw_text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                clean = clean.rsplit("```", 1)[0]

            data = json.loads(clean)

            return Reflection(
                is_satisfactory=data.get("is_satisfactory", True),
                quality_score=data.get("quality_score", 7),
                strengths=data.get("strengths", []),
                gaps=data.get("gaps", []),
                follow_up=data.get("follow_up", ""),
                suggested_narrative=data.get("suggested_narrative", ""),
                raw_response=raw_text,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("reflector_parse_fallback", error=str(e))
            return Reflection(
                is_satisfactory=True,
                quality_score=6,
                suggested_narrative=raw_text,
                raw_response=raw_text,
            )
