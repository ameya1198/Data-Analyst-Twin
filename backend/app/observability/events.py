"""
Structured event types for observability.

Every agent decision, tool call, and error is captured as a typed event.
These feed into the logger and metrics tracker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class AgentEvent:
    timestamp: datetime
    session_id: str
    event_type: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    success: bool = True
    specialist_name: Optional[str] = None
    specialist_mode: Optional[str] = None
    tool_name: Optional[str] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def add(self, input_tok: int, output_tok: int) -> None:
        self.input_tokens += input_tok
        self.output_tokens += output_tok
        self.total_tokens = self.input_tokens + self.output_tokens
        # Claude Sonnet pricing approximation: $3/M input, $15/M output
        self.estimated_cost_usd = (
            (self.input_tokens / 1_000_000) * 3.0
            + (self.output_tokens / 1_000_000) * 15.0
        )
