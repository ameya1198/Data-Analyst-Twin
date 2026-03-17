"""
Planner — Phase 1 of the Plan-Execute-Reflect loop.

Takes the user's question + available data context and produces a structured
analysis plan with concrete tool calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog
from anthropic import AsyncAnthropic

from app.agent.prompts import SUPERVISOR_SYSTEM_PROMPT, PLANNER_PROMPT
from app.agent.specialists.base import SpecialistRegistry
from app.agent.specialists.context import AnalysisContext
from app.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class AnalysisStep:
    step_number: int
    description: str
    tool_name: str
    tool_params: dict[str, Any]
    rationale: str
    workflow_phase: str = ""


@dataclass
class AnalysisPlan:
    understanding: str
    approach: str
    steps: list[AnalysisStep]
    question_type: str = "descriptive"
    assumptions: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    raw_response: Optional[str] = None

    def to_display(self) -> dict:
        """Format for streaming to the frontend."""
        return {
            "understanding": self.understanding,
            "question_type": self.question_type,
            "approach": self.approach,
            "steps": [
                {
                    "step_number": s.step_number,
                    "description": s.description,
                    "tool_name": s.tool_name,
                    "rationale": s.rationale,
                    "workflow_phase": s.workflow_phase,
                }
                for s in self.steps
            ],
            "assumptions": self.assumptions,
            "caveats": self.caveats,
        }


class Planner:
    """Creates analysis plans by asking Claude to reason about the question and data."""

    def __init__(self, client: AsyncAnthropic, registry: SpecialistRegistry) -> None:
        self._client = client
        self._registry = registry

    async def create_plan(
        self,
        user_message: str,
        context: AnalysisContext,
        dataset_ids: list[str] | None = None,
    ) -> AnalysisPlan:
        system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
            dataset_summaries=context.get_dataset_summaries(limit_to_ids=dataset_ids),
            recent_results=context.get_recent_results_summary(),
            capabilities_summary=self._registry.get_capabilities_summary(),
        )

        planner_message = PLANNER_PROMPT.format(user_message=user_message)

        logger.info("planner_start", user_message=user_message[:100])

        response = await self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": planner_message}],
        )

        raw_text = response.content[0].text
        logger.info(
            "planner_complete",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        return self._parse_plan(raw_text)

    def _parse_plan(self, raw_text: str) -> AnalysisPlan:
        """Parse Claude's JSON response into a structured plan."""
        try:
            clean = raw_text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                clean = clean.rsplit("```", 1)[0]

            plan_data = json.loads(clean)

            steps = []
            for s in plan_data.get("steps", []):
                steps.append(AnalysisStep(
                    step_number=s.get("step_number", len(steps) + 1),
                    description=s.get("description", ""),
                    tool_name=s.get("tool_name", ""),
                    tool_params=s.get("tool_params", {}),
                    rationale=s.get("rationale", ""),
                    workflow_phase=s.get("workflow_phase", ""),
                ))

            return AnalysisPlan(
                understanding=plan_data.get("understanding", ""),
                approach=plan_data.get("approach", ""),
                steps=steps,
                question_type=plan_data.get("question_type", "descriptive"),
                assumptions=plan_data.get("assumptions", []),
                caveats=plan_data.get("caveats", []),
                raw_response=raw_text,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("planner_parse_fallback", error=str(e))
            return AnalysisPlan(
                understanding="Could not parse structured plan. Proceeding with direct tool-use.",
                approach="direct",
                steps=[],
                raw_response=raw_text,
            )
