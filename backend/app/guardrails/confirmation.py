"""
Human-in-the-loop confirmation — requires user approval for destructive operations.

Specialists that modify data (cleaning) must go through this layer.
The confirmation request is sent via WebSocket and blocks until the user responds.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

CONFIRMATION_REQUIRED: dict[str, list[str]] = {
    "cleaning": [
        "clean_structural",
        "clean_deduplicate",
        "clean_missing",
        "clean_standardise",
        "clean_derive",
    ],
}

TOOL_IMPACT_DESCRIPTIONS: dict[str, str] = {
    "clean_structural": (
        "Normalize column names, fix data types, and strip whitespace. "
        "A new copy of the dataset will be created — the original stays untouched."
    ),
    "clean_deduplicate": (
        "Detect and remove duplicate rows from the dataset. "
        "A new deduplicated copy will be created."
    ),
    "clean_missing": (
        "Handle missing values by imputing, dropping, or flagging them. "
        "A new copy with treated missing values will be created."
    ),
    "clean_standardise": (
        "Standardize text (lowercase, trim), parse dates, and apply category mappings. "
        "A new standardized copy will be created."
    ),
    "clean_derive": (
        "Create new derived columns (date parts, bins, flags, calculated features). "
        "A new copy with additional columns will be created."
    ),
}


@dataclass
class ConfirmationRequest:
    request_id: str
    specialist_name: str
    tool_name: str
    description: str
    details: dict[str, Any]
    impact: str

    def to_stream_data(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "specialist_name": self.specialist_name,
            "tool_name": self.tool_name,
            "description": self.description,
            "details": self.details,
            "impact": self.impact,
        }


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
        tools = CONFIRMATION_REQUIRED.get(specialist_name, [])
        return tool_name in tools

    def build_request(
        self,
        specialist_name: str,
        tool_name: str,
        params: dict[str, Any],
    ) -> ConfirmationRequest:
        impact = TOOL_IMPACT_DESCRIPTIONS.get(
            tool_name,
            "This operation will modify the dataset. A new copy will be created.",
        )
        dataset_id = params.get("dataset_id", "unknown")
        details: dict[str, Any] = {"dataset_id": dataset_id}

        if tool_name == "clean_deduplicate":
            details["strategy"] = params.get("strategy", "keep_first")
        elif tool_name == "clean_missing":
            details["strategy"] = params.get("strategy", "auto")
            details["columns"] = params.get("columns", "all")
        elif tool_name == "clean_derive":
            details["operations"] = params.get("operations", [])

        human_name = tool_name.replace("clean_", "").replace("_", " ").title()

        return ConfirmationRequest(
            request_id=str(uuid.uuid4()),
            specialist_name=specialist_name,
            tool_name=tool_name,
            description=f"Data Cleaning: {human_name}",
            details=details,
            impact=impact,
        )

    def create_pending(self, request_id: str) -> None:
        """Create a Future for a pending confirmation request."""
        loop = asyncio.get_running_loop()
        self._pending[request_id] = loop.create_future()

    async def wait_for(self, request_id: str) -> ConfirmationResponse:
        """Block until the confirmation response arrives or times out."""
        future = self._pending.get(request_id)
        if future is None:
            return ConfirmationResponse(
                request_id=request_id,
                approved=False,
                user_message="No pending confirmation found.",
            )

        try:
            response = await asyncio.wait_for(future, timeout=self._timeout)
            logger.info(
                "confirmation_received",
                request_id=request_id,
                approved=response.approved,
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(
                "confirmation_timeout",
                request_id=request_id,
                timeout=self._timeout,
            )
            self._pending.pop(request_id, None)
            return ConfirmationResponse(
                request_id=request_id,
                approved=False,
                user_message="Confirmation timed out — operation cancelled.",
            )

    def resolve(self, request_id: str, approved: bool, message: str | None = None) -> bool:
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

    @property
    def has_pending(self) -> bool:
        return len(self._pending) > 0
