from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class StreamEventType(str, Enum):
    PLAN = "plan"
    SPECIALIST_CALL = "specialist_call"
    SPECIALIST_RESULT = "specialist_result"
    REFLECTION = "reflection"
    ERROR = "error"
    ERROR_RECOVERY = "error_recovery"
    CONFIRMATION_REQUEST = "confirmation_request"
    FINAL_RESPONSE = "final_response"


class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    dataset_ids: list[str] = Field(default_factory=list)


class StreamEvent(BaseModel):
    event_type: StreamEventType
    data: Any
    specialist_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DatasetInfo(BaseModel):
    id: str
    filename: str
    rows: int
    columns: int
    column_names: list[str]
    dtypes: dict[str, str]
    size_bytes: int
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class UploadResponse(BaseModel):
    dataset: DatasetInfo
    preview: list[dict[str, Any]]


class SessionInfo(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    dataset_ids: list[str]
    title: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    environment: str = "development"
