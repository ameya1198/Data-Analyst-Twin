"""
Input validation — validates user messages and tool call parameters
before they reach the agent or specialists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

MAX_MESSAGE_LENGTH = 10_000
MAX_PARAM_VALUE_LENGTH = 5_000


@dataclass
class ValidationResult:
    valid: bool
    error: Optional[str] = None

    @staticmethod
    def ok() -> ValidationResult:
        return ValidationResult(valid=True)

    @staticmethod
    def fail(reason: str) -> ValidationResult:
        return ValidationResult(valid=False, error=reason)


class InputValidator:
    """Validates inputs before they reach the agent or specialists."""

    def validate_message(self, message: str) -> ValidationResult:
        if not message or not message.strip():
            return ValidationResult.fail("Message cannot be empty")

        if len(message) > MAX_MESSAGE_LENGTH:
            return ValidationResult.fail(
                f"Message too long ({len(message)} chars). Maximum is {MAX_MESSAGE_LENGTH}."
            )

        return ValidationResult.ok()

    def validate_file_upload(
        self, filename: str, size_bytes: int, content_type: str | None = None
    ) -> ValidationResult:
        if not filename:
            return ValidationResult.fail("Filename is required")

        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in settings.allowed_file_type_list:
            return ValidationResult.fail(
                f"File type '{extension}' not allowed. "
                f"Allowed: {', '.join(settings.allowed_file_type_list)}"
            )

        if size_bytes > settings.max_upload_size_bytes:
            max_mb = settings.max_upload_size_mb
            actual_mb = round(size_bytes / (1024 * 1024), 1)
            return ValidationResult.fail(
                f"File too large ({actual_mb} MB). Maximum is {max_mb} MB."
            )

        return ValidationResult.ok()

    def validate_tool_params(
        self, tool_name: str, params: dict[str, Any], schema: dict | None = None
    ) -> ValidationResult:
        """Basic parameter validation. Schema-based validation can be added later."""
        for key, value in params.items():
            if isinstance(value, str) and len(value) > MAX_PARAM_VALUE_LENGTH:
                return ValidationResult.fail(
                    f"Parameter '{key}' too long ({len(value)} chars). "
                    f"Maximum is {MAX_PARAM_VALUE_LENGTH}."
                )

        return ValidationResult.ok()
