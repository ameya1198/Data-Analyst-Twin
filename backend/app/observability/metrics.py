"""
Metrics tracker — accumulates token usage, latency, and error counts per session.

Phase 1: In-memory tracking with log output.
Phase 4: Upgrade to Prometheus/Grafana or similar.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from app.observability.events import AgentEvent, TokenUsage

logger = structlog.get_logger(__name__)


@dataclass
class SessionMetrics:
    session_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    llm_calls: int = 0
    specialist_calls: int = 0
    errors: int = 0
    reflect_cycles: int = 0
    latency_by_specialist: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    events: list[AgentEvent] = field(default_factory=list)

    def record_llm_call(self, input_tokens: int, output_tokens: int, latency_ms: float) -> None:
        self.llm_calls += 1
        self.token_usage.add(input_tokens, output_tokens)
        logger.debug(
            "metric_llm_call",
            session_id=self.session_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(latency_ms, 2),
            total_calls=self.llm_calls,
        )

    def record_specialist_call(
        self, specialist_name: str, latency_ms: float, success: bool
    ) -> None:
        self.specialist_calls += 1
        self.latency_by_specialist[specialist_name].append(latency_ms)
        if not success:
            self.errors += 1
        logger.debug(
            "metric_specialist_call",
            session_id=self.session_id,
            specialist=specialist_name,
            latency_ms=round(latency_ms, 2),
            success=success,
            total_calls=self.specialist_calls,
        )

    def record_reflection(self) -> None:
        self.reflect_cycles += 1

    def record_event(self, event: AgentEvent) -> None:
        self.events.append(event)

    def get_summary(self) -> dict[str, Any]:
        avg_latencies = {}
        for name, latencies in self.latency_by_specialist.items():
            if latencies:
                avg_latencies[name] = round(sum(latencies) / len(latencies), 2)

        return {
            "session_id": self.session_id,
            "llm_calls": self.llm_calls,
            "specialist_calls": self.specialist_calls,
            "errors": self.errors,
            "reflect_cycles": self.reflect_cycles,
            "total_tokens": self.token_usage.total_tokens,
            "estimated_cost_usd": round(self.token_usage.estimated_cost_usd, 4),
            "avg_latency_by_specialist_ms": avg_latencies,
        }


class MetricsCollector:
    """Manages metrics across all active sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionMetrics] = {}

    def get_or_create(self, session_id: str) -> SessionMetrics:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMetrics(session_id=session_id)
        return self._sessions[session_id]

    def get_session_summary(self, session_id: str) -> dict[str, Any] | None:
        metrics = self._sessions.get(session_id)
        return metrics.get_summary() if metrics else None

    def get_all_summaries(self) -> list[dict[str, Any]]:
        return [m.get_summary() for m in self._sessions.values()]


# Global singleton
metrics_collector = MetricsCollector()
