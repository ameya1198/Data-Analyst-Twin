import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.database import (
    create_session as db_create_session,
    get_session as db_get_session,
    list_sessions as db_list_sessions,
    delete_session as db_delete_session,
    count_messages,
    get_session_dataset_ids,
)
from app.models.schemas import SessionInfo

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/", response_model=SessionInfo)
async def create_session(title: str | None = None) -> SessionInfo:
    """Create a new analysis session."""
    session_id = str(uuid.uuid4())
    session = await db_create_session(session_id, title)
    return SessionInfo(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
        dataset_ids=[],
    )


@router.get("/", response_model=list[SessionInfo])
async def list_sessions() -> list[SessionInfo]:
    """List all sessions."""
    sessions = await db_list_sessions()
    results = []
    for s in sessions:
        msg_count = await count_messages(s.id)
        ds_ids = await get_session_dataset_ids(s.id)
        results.append(SessionInfo(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=msg_count,
            dataset_ids=ds_ids,
        ))
    return results


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str) -> SessionInfo:
    """Get session details."""
    session = await db_get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    msg_count = await count_messages(session_id)
    ds_ids = await get_session_dataset_ids(session_id)

    return SessionInfo(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=msg_count,
        dataset_ids=ds_ids,
    )


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete a session and its messages."""
    deleted = await db_delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"status": "deleted", "session_id": session_id}
