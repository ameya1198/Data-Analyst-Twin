"""
Offline LLM regression tests (no real Claude calls).

Why offline:
- LLM outputs are non-deterministic and expensive to call in CI.
- Most regressions we care about are *prompt contract* and *output contract* issues:
  placeholders, missing dataset_id guidance, malformed plan JSON, etc.

What we test here:
1) Planner prompt contract: the prompt we send MUST include required invariants.
2) Planner parsing contract: a representative LLM JSON plan must parse and route.
3) Synthesis prompt contract: lightweight synthesis MUST forbid placeholders and
   demand executed SQL / real identifiers.

These tests catch prompt regressions when `app/agent/prompts.py` changes, without
needing external API access.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd
import pytest

from app.agent.planner import Planner
from app.agent.prompts import PLANNER_PROMPT, SUPERVISOR_SYSTEM_PROMPT, FOCUSED_SYNTHESIS_PROMPT
from app.agent.specialists.base import SpecialistRegistry
from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.eda import EDASpecialist
from app.agent.supervisor import Supervisor


def _mock_anthropic_response(text: str):
    """Minimal shape used by our code: response.content[0].text + usage fields."""
    block = SimpleNamespace(text=text, type="text")
    usage = SimpleNamespace(input_tokens=123, output_tokens=45)
    return SimpleNamespace(content=[block], usage=usage, stop_reason="end_turn")


@pytest.fixture
def ctx_with_dataset() -> AnalysisContext:
    np.random.seed(42)
    df = pd.DataFrame(
        {
            "age": np.random.randint(20, 65, 50),
            "salary": np.random.normal(75000, 15000, 50).round(2),
            "dept": np.random.choice(["Eng", "Sales"], 50),
        }
    )
    ctx = AnalysisContext()
    ctx.add_dataset("abc123", df, "employees.csv")
    return ctx


@pytest.fixture
def registry() -> SpecialistRegistry:
    reg = SpecialistRegistry()
    reg.register(EDASpecialist())
    return reg


class TestPlannerPromptContract:
    def test_planner_prompt_includes_dataset_id_requirement(self):
        # This is the highest-signal invariant that prevented dataset_name/filename bugs.
        assert "CRITICAL: Every tool_params MUST include \"dataset_id\"" in PLANNER_PROMPT
        assert "Do NOT use the filename as dataset_id" in PLANNER_PROMPT

    def test_supervisor_system_prompt_has_required_sections(self):
        # Prompt contract: these headers should not disappear accidentally.
        assert "## Available Data" in SUPERVISOR_SYSTEM_PROMPT
        assert "## Analysis So Far" in SUPERVISOR_SYSTEM_PROMPT
        assert "## Available Specialists" in SUPERVISOR_SYSTEM_PROMPT

    def test_foocused_synthesis_forbids_placeholders(self):
        # Prompt contract: ensure we keep the anti-placeholder rule.
        assert "Never give instructions like \"replace your_table_name\"" in FOCUSED_SYNTHESIS_PROMPT


class TestPlannerCreatePlanContract:
    @pytest.mark.asyncio
    async def test_create_plan_calls_llm_with_expected_shapes(self, ctx_with_dataset, registry):
        # Arrange
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(
                json.dumps(
                    {
                        "understanding": "Profile the dataset.",
                        "question_type": "descriptive",
                        "approach": "Run eda_profile then summarize.",
                        "steps": [
                            {
                                "step_number": 1,
                                "description": "Profile dataset",
                                "tool_name": "eda_profile",
                                "tool_params": {"dataset_id": "abc123"},
                                "rationale": "Get overview",
                                "workflow_phase": "exploration",
                            }
                        ],
                        "assumptions": ["One dataset loaded"],
                        "caveats": [],
                    }
                )
            )
        )

        planner = Planner(client=mock_client, registry=registry)

        # Act
        plan = await planner.create_plan("profile my data", ctx_with_dataset)

        # Assert plan parsed
        assert plan.steps
        assert plan.steps[0].tool_name == "eda_profile"
        assert plan.steps[0].tool_params["dataset_id"] == "abc123"

        # Assert LLM called with both system + user prompt
        assert mock_client.messages.create.await_count == 1
        _, kwargs = mock_client.messages.create.call_args
        assert "system" in kwargs
        assert "messages" in kwargs
        assert isinstance(kwargs["messages"], list)
        assert kwargs["messages"][0]["role"] == "user"
        assert "User question:" in kwargs["messages"][0]["content"]


class TestSynthesisPromptContract:
    @pytest.mark.asyncio
    async def test_supervisor_lightweight_synthesis_system_rules(self, ctx_with_dataset, registry):
        """
        Regression test: ensure the synthesis call includes the no-placeholder + SQL rules
        in the 'system' instruction. This is where verbose/templated output used to slip in.
        """
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("OK.")
        )

        supervisor = Supervisor(registry=registry, context=ctx_with_dataset)
        supervisor._client = mock_client  # inject mocked LLM

        # Call the private method directly to keep it deterministic and fast.
        out = await supervisor._synthesize_lightweight(
            "profile my data",
            [],
        )
        assert out == "OK."

        _, kwargs = mock_client.messages.create.call_args
        system = kwargs.get("system", "")
        assert "Lead with the answer" in system
        assert "template placeholders" in system
        assert "For SQL: show the query in a code block" in system

