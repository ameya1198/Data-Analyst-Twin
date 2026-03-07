from fastapi import APIRouter
from app.models.schemas import SessionInfo

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/", response_model=SessionInfo)
async def create_session() -> dict:
    """Create a new analysis session."""
    return {"message": "Session creation not yet implemented (Phase 2)"}


@router.get("/", response_model=list[SessionInfo])
async def list_sessions() -> list:
    """List all sessions."""
    return []


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get session details."""
    return {"session_id": session_id, "message": "Session retrieval not yet implemented (Phase 2)"}


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete a session."""
    return {"session_id": session_id, "message": "Session deletion not yet implemented (Phase 2)"}
