"""
Rate limiter — enforces per-session limits on LLM calls and specialist calls.
Prevents runaway loops and controls costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class RateLimitState:
    llm_calls: int = 0
    specialist_calls_this_turn: int = 0
    total_specialist_calls: int = 0

    def reset_turn(self) -> None:
        """Reset per-turn counters at the start of a new user message."""
        self.specialist_calls_this_turn = 0


@dataclass
class RateLimitResult:
    allowed: bool
    reason: Optional[str] = None
    remaining: Optional[int] = None


class RateLimiter:
    """
    Enforces rate limits per session.

    Limits:
    - Max LLM calls per session (default: 50)
    - Max specialist calls per turn (default: 15)
    """

    def __init__(
        self,
        max_llm_calls: int | None = None,
        max_specialist_calls_per_turn: int | None = None,
    ) -> None:
        self._max_llm_calls = max_llm_calls or settings.max_llm_calls_per_session
        self._max_specialist_per_turn = (
            max_specialist_calls_per_turn or settings.max_specialist_calls_per_turn
        )
        self._sessions: dict[str, RateLimitState] = {}

    def get_state(self, session_id: str) -> RateLimitState:
        if session_id not in self._sessions:
            self._sessions[session_id] = RateLimitState()
        return self._sessions[session_id]

    def check_llm_call(self, session_id: str) -> RateLimitResult:
        state = self.get_state(session_id)
        remaining = self._max_llm_calls - state.llm_calls

        if remaining <= 0:
            logger.warning(
                "rate_limit_llm_exceeded",
                session_id=session_id,
                limit=self._max_llm_calls,
            )
            return RateLimitResult(
                allowed=False,
                reason=f"LLM call limit reached ({self._max_llm_calls} per session). "
                       "Start a new session to continue.",
                remaining=0,
            )

        return RateLimitResult(allowed=True, remaining=remaining)

    def record_llm_call(self, session_id: str) -> None:
        state = self.get_state(session_id)
        state.llm_calls += 1

    def check_specialist_call(self, session_id: str) -> RateLimitResult:
        state = self.get_state(session_id)
        remaining = self._max_specialist_per_turn - state.specialist_calls_this_turn

        if remaining <= 0:
            logger.warning(
                "rate_limit_specialist_exceeded",
                session_id=session_id,
                limit=self._max_specialist_per_turn,
            )
            return RateLimitResult(
                allowed=False,
                reason=f"Specialist call limit reached ({self._max_specialist_per_turn} per turn). "
                       "Send a new message to continue.",
                remaining=0,
            )

        return RateLimitResult(allowed=True, remaining=remaining)

    def record_specialist_call(self, session_id: str) -> None:
        state = self.get_state(session_id)
        state.specialist_calls_this_turn += 1
        state.total_specialist_calls += 1

    def new_turn(self, session_id: str) -> None:
        """Call at the start of each user message to reset per-turn counters."""
        state = self.get_state(session_id)
        state.reset_turn()

    def get_usage_summary(self, session_id: str) -> dict:
        state = self.get_state(session_id)
        return {
            "llm_calls": state.llm_calls,
            "llm_calls_remaining": self._max_llm_calls - state.llm_calls,
            "specialist_calls_this_turn": state.specialist_calls_this_turn,
            "specialist_calls_remaining_this_turn": (
                self._max_specialist_per_turn - state.specialist_calls_this_turn
            ),
            "total_specialist_calls": state.total_specialist_calls,
        }
