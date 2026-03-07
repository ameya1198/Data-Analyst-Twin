"""
Human-in-the-loop confirmation — requires user approval for destructive operations.

Specialists that modify data (cleaning, SQL writes) must go through this layer.
The confirmation request is sent via WebSocket and blocks until the user responds.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

# Specialists whose operations require user confirmation
CONFIRMATION_REQUIRED = {
    "data_cleaning": [
        "clean_drop_nulls",
        "clean_drop_duplicates",
        "clean_fill_nulls",
        "clean_cast_types",
    ],
    "sql": [
        "sql_execute_write",
    ],
}


@dataclass
class ConfirmationRequest:
    request_id: str
    specialist_name: str
    tool_name: str
    description: str
    details: dict[str, Any]
    impact: str  # What will be affected


@dataclass
class ConfirmationResponse:
    request_id: str
    approved: bool
    user_message: Optional[str] = None


class ConfirmationManager:
    """
    Manages the human-in-the-loop confirmation flow.

    When a specialist requires confirmation, the manager:
    1. Creates a ConfirmationRequest
    2. Sends it to the frontend via a callback
    3. Waits for the user's response (with timeout)
    """

    def __init__(self, timeout_seconds: int = 120) -> None:
        self._pending: dict[str, asyncio.Future[ConfirmationResponse]] = {}
        self._timeout = timeout_seconds

    def needs_confirmation(self, specialist_name: str, tool_name: str) -> bool:
        """Check if a tool call requires user confirmation."""
        tools = CONFIRMATION_REQUIRED.get(specialist_name, [])
        return tool_name in tools

    async def request_confirmation(
        self,
        request: ConfirmationRequest,
        send_callback: Any,
    ) -> ConfirmationResponse:
        """
        Send a confirmation request and wait for user response.

        Args:
            request: The confirmation details
            send_callback: Async function to send the request to the frontend
        """
        future: asyncio.Future[ConfirmationResponse] = asyncio.get_event_loop().create_future()
        self._pending[request.request_id] = future

        logger.info(
            "confirmation_requested",
            request_id=request.request_id,
            specialist=request.specialist_name,
            tool=request.tool_name,
        )

        await send_callback(request)

        try:
            response = await asyncio.wait_for(future, timeout=self._timeout)
            logger.info(
                "confirmation_received",
                request_id=request.request_id,
                approved=response.approved,
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(
                "confirmation_timeout",
                request_id=request.request_id,
                timeout=self._timeout,
            )
            self._pending.pop(request.request_id, None)
            return ConfirmationResponse(
                request_id=request.request_id,
                approved=False,
                user_message="Confirmation timed out",
            )

    def resolve(self, request_id: str, approved: bool, message: str | None = None) -> bool:
        """Called when the frontend sends a confirmation response."""
        future = self._pending.pop(request_id, None)
        if future is None:
            logger.warning("confirmation_resolve_not_found", request_id=request_id)
            return False

        future.set_result(ConfirmationResponse(
            request_id=request_id,
            approved=approved,
            user_message=message,
        ))
        return True
