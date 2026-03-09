"""
Conversation memory for the supervisor.

Phase 1: Simple sliding window of recent messages.
Phase 2 upgrade: Add LLM-generated summaries for long conversations + episodic memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    role: str  # "user", "assistant", "system"
    content: Any  # str or list of content blocks (for tool_use/tool_result)

    def to_api_format(self) -> dict:
        return {"role": self.role, "content": self.content}


class ConversationMemory:
    """
    Manages conversation history with a sliding window.

    Keeps the last `max_messages` exchanges. In Phase 2, this will be
    upgraded with periodic LLM-generated summaries for long conversations.
    """

    def __init__(self, max_messages: int = 40) -> None:
        self._messages: list[Message] = []
        self._max_messages = max_messages

    def add_user_message(self, content: str) -> None:
        self._messages.append(Message(role="user", content=content))
        self._trim()

    def add_assistant_message(self, content: Any) -> None:
        self._messages.append(Message(role="assistant", content=content))
        self._trim()

    def add_tool_result(self, tool_use_id: str, content: str) -> None:
        """Add a tool_result message following a tool_use response."""
        self._messages.append(Message(
            role="user",
            content=[{
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
            }],
        ))
        self._trim()

    def add_tool_results_batch(self, results: list[dict]) -> None:
        """Add multiple tool results in a single user message (Claude requires this)."""
        self._messages.append(Message(
            role="user",
            content=[
                {
                    "type": "tool_result",
                    "tool_use_id": r["tool_use_id"],
                    "content": r["content"],
                }
                for r in results
            ],
        ))
        self._trim()

    def get_messages(self) -> list[dict]:
        """Return messages in Claude API format."""
        return [m.to_api_format() for m in self._messages]

    def get_last_n(self, n: int) -> list[dict]:
        return [m.to_api_format() for m in self._messages[-n:]]

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def is_empty(self) -> bool:
        return len(self._messages) == 0

    @property
    def has_history(self) -> bool:
        return len(self._messages) > 0

    def clear(self) -> None:
        self._messages.clear()

    def _trim(self) -> None:
        """Remove oldest messages if over the limit, keeping pairs intact."""
        while len(self._messages) > self._max_messages:
            self._messages.pop(0)
