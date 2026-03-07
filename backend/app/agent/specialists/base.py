"""
BaseSpecialist — the core abstraction enabling the hybrid multi-agent architecture.

Each specialist supports two modes behind a single interface:
- ToolMode: direct function execution within the supervisor's context (Phase 1)
- AgentMode: own Claude instance with focused system prompt (Phase 4 upgrade)

The supervisor delegates to specialists via .execute() without knowing which mode
they run in. Upgrading a specialist from ToolMode to AgentMode requires zero
changes in the supervisor.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import structlog

from app.agent.specialists.context import AnalysisContext

logger = structlog.get_logger(__name__)


class SpecialistMode(str, Enum):
    TOOL = "tool"
    AGENT = "agent"


class ResultType(str, Enum):
    TABLE = "table"
    CHART = "chart"
    STATISTIC = "statistic"
    TEXT = "text"
    CODE = "code"
    ERROR = "error"


@dataclass
class SpecialistResult:
    """Structured output from any specialist execution."""
    success: bool
    specialist_name: str
    result_type: ResultType
    data: Any
    summary: str  # Human-readable summary for the LLM and UI
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: float = 0.0

    def to_llm_context(self) -> str:
        """Format result for injection into the next LLM call."""
        if not self.success:
            return f"[{self.specialist_name} ERROR] {self.error}"
        return f"[{self.specialist_name}] {self.summary}"


class BaseSpecialist(ABC):
    """
    Abstract base for all analyst specialists.

    Subclasses must implement:
    - get_tools(): returns Claude tool-use schemas for this specialist's capabilities
    - _execute_tool_mode(): the actual analysis logic (pandas, scipy, plotly, etc.)

    Optionally override _execute_agent_mode() when upgrading to AgentMode in Phase 4.
    """

    name: str
    description: str
    mode: SpecialistMode = SpecialistMode.TOOL
    system_prompt: str = ""

    # Per-specialist timeout (overridden by subclasses)
    timeout_seconds: int = 60

    # Whether this specialist's operations need user confirmation
    requires_confirmation: bool = False

    @abstractmethod
    def get_tools(self) -> list[dict]:
        """
        Return Claude tool-use JSON schemas for this specialist.

        Each tool is a dict with 'name', 'description', and 'input_schema'.
        A specialist may expose multiple tools (e.g., EDA has 'profile', 'correlations', 'describe').
        """

    @abstractmethod
    async def _execute_tool_mode(
        self, tool_name: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """
        Execute a tool call in ToolMode — direct function execution.
        This is where the actual pandas/scipy/plotly work happens.
        """

    async def _execute_agent_mode(
        self, tool_name: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """
        Execute in AgentMode — own Claude sub-agent with focused prompt.
        Override this when upgrading a specialist to AgentMode in Phase 4.

        Default implementation falls back to ToolMode.
        """
        logger.warning(
            "agent_mode_not_implemented",
            specialist=self.name,
            fallback="tool_mode",
        )
        return await self._execute_tool_mode(tool_name, params, context)

    async def execute(
        self, tool_name: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """
        Uniform entry point — delegates to the current mode.
        The supervisor calls this without knowing which mode is active.
        """
        start = time.perf_counter()

        logger.info(
            "specialist_execute_start",
            specialist=self.name,
            mode=self.mode.value,
            tool=tool_name,
            params_keys=list(params.keys()),
        )

        try:
            if self.mode == SpecialistMode.AGENT:
                result = await self._execute_agent_mode(tool_name, params, context)
            else:
                result = await self._execute_tool_mode(tool_name, params, context)

            result.latency_ms = (time.perf_counter() - start) * 1000

            # Write to shared context
            context.add_result(
                specialist_name=self.name,
                step_description=result.summary,
                result_type=result.result_type.value,
                data=result.data,
                latency_ms=result.latency_ms,
            )

            logger.info(
                "specialist_execute_complete",
                specialist=self.name,
                tool=tool_name,
                success=result.success,
                latency_ms=round(result.latency_ms, 2),
            )
            return result

        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "specialist_execute_error",
                specialist=self.name,
                tool=tool_name,
                error=str(e),
                latency_ms=round(latency_ms, 2),
            )
            return SpecialistResult(
                success=False,
                specialist_name=self.name,
                result_type=ResultType.ERROR,
                data=None,
                summary=f"Error in {self.name}: {str(e)}",
                error=str(e),
                latency_ms=latency_ms,
            )

    def get_tool_names(self) -> list[str]:
        """All tool names this specialist exposes."""
        return [t["name"] for t in self.get_tools()]


class SpecialistRegistry:
    """
    Registry of all available specialists.

    The supervisor uses this to:
    1. Collect all tool schemas for the Claude API call
    2. Route a tool_use response to the correct specialist
    """

    def __init__(self) -> None:
        self._specialists: dict[str, BaseSpecialist] = {}
        self._tool_to_specialist: dict[str, str] = {}  # tool_name -> specialist_name

    def register(self, specialist: BaseSpecialist) -> None:
        """Register a specialist and index its tools."""
        self._specialists[specialist.name] = specialist
        for tool_name in specialist.get_tool_names():
            if tool_name in self._tool_to_specialist:
                raise ValueError(
                    f"Tool name conflict: '{tool_name}' is registered by both "
                    f"'{self._tool_to_specialist[tool_name]}' and '{specialist.name}'"
                )
            self._tool_to_specialist[tool_name] = specialist.name

        logger.info(
            "specialist_registered",
            name=specialist.name,
            mode=specialist.mode.value,
            tools=specialist.get_tool_names(),
        )

    def get_specialist(self, name: str) -> Optional[BaseSpecialist]:
        return self._specialists.get(name)

    def get_specialist_for_tool(self, tool_name: str) -> Optional[BaseSpecialist]:
        """Look up which specialist owns a given tool name."""
        specialist_name = self._tool_to_specialist.get(tool_name)
        if specialist_name is None:
            return None
        return self._specialists.get(specialist_name)

    def get_all_tools(self) -> list[dict]:
        """All tool schemas from all specialists — passed to Claude."""
        tools = []
        for specialist in self._specialists.values():
            tools.extend(specialist.get_tools())
        return tools

    def get_all_specialists(self) -> list[BaseSpecialist]:
        return list(self._specialists.values())

    async def execute_tool(
        self, tool_name: str, params: dict, context: AnalysisContext
    ) -> SpecialistResult:
        """Route a tool call to the correct specialist and execute."""
        specialist = self.get_specialist_for_tool(tool_name)
        if specialist is None:
            return SpecialistResult(
                success=False,
                specialist_name="unknown",
                result_type=ResultType.ERROR,
                data=None,
                summary=f"No specialist found for tool '{tool_name}'",
                error=f"Unknown tool: {tool_name}",
            )
        return await specialist.execute(tool_name, params, context)

    @property
    def specialist_names(self) -> list[str]:
        return list(self._specialists.keys())

    @property
    def tool_names(self) -> list[str]:
        return list(self._tool_to_specialist.keys())

    def get_capabilities_summary(self) -> str:
        """Text summary of all specialists and their tools — for LLM context."""
        lines = []
        for s in self._specialists.values():
            tool_list = ", ".join(s.get_tool_names())
            lines.append(f"- {s.name}: {s.description} [tools: {tool_list}]")
        return "\n".join(lines)
