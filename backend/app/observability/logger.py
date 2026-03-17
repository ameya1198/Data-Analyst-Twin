"""
Structured logging setup for the agent.

Uses structlog with context variables so every log line within a request
automatically includes session_id, request_id, and trace_id.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

import structlog

session_id_var: ContextVar[str] = ContextVar("session_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def generate_trace_id() -> str:
    """Create a short, unique trace ID for one user message → response cycle."""
    return str(uuid.uuid4())[:8]


def bind_session_context(session_id: str, trace_id: str | None = None) -> None:
    """Bind session + trace context to all subsequent log lines in this async task."""
    tid = trace_id or generate_trace_id()
    session_id_var.set(session_id)
    request_id_var.set(tid)
    trace_id_var.set(tid)
    structlog.contextvars.bind_contextvars(
        session_id=session_id,
        request_id=tid,
        trace_id=tid,
    )


def clear_session_context() -> None:
    structlog.contextvars.unbind_contextvars("session_id", "request_id", "trace_id")
    session_id_var.set("")
    request_id_var.set("")
    trace_id_var.set("")


def get_current_trace_id() -> str:
    return trace_id_var.get("")


def log_agent_decision(
    event: str,
    **kwargs: Any,
) -> None:
    """Convenience wrapper for logging agent-level decisions with consistent structure."""
    logger = structlog.get_logger("agent")
    logger.info(event, **kwargs)
