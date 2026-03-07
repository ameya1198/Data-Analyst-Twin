"""
Structured logging setup for the agent.

Uses structlog with context variables so every log line within a request
automatically includes session_id and request_id.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

import structlog

# Context variables — set once per request, automatically included in all log lines
session_id_var: ContextVar[str] = ContextVar("session_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def bind_session_context(session_id: str) -> None:
    """Call at the start of a request to bind session context to all subsequent logs."""
    session_id_var.set(session_id)
    request_id_var.set(str(uuid.uuid4())[:8])
    structlog.contextvars.bind_contextvars(
        session_id=session_id,
        request_id=request_id_var.get(),
    )


def clear_session_context() -> None:
    structlog.contextvars.unbind_contextvars("session_id", "request_id")


def log_agent_decision(
    event: str,
    **kwargs: Any,
) -> None:
    """Convenience wrapper for logging agent-level decisions with consistent structure."""
    logger = structlog.get_logger("agent")
    logger.info(event, **kwargs)
