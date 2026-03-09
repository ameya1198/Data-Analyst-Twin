import json
import traceback

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agent import create_supervisor
from app.api.routes.data import get_context
from app.models.schemas import ChatRequest, StreamEvent, StreamEventType

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

_supervisors: dict[str, object] = {}


def _get_or_create_supervisor(session_id: str):
    """Reuse a Supervisor per WebSocket session so conversation memory persists."""
    context = get_context()
    if session_id not in _supervisors:
        _supervisors[session_id] = create_supervisor(context=context)
    else:
        # Always update the context reference in case datasets were added
        sup = _supervisors[session_id]
        sup.context = context  # type: ignore[attr-defined]
    return _supervisors[session_id]


@router.post("/message")
async def send_message(request: ChatRequest) -> dict:
    """REST fallback for sending a chat message. Prefer WebSocket for streaming."""
    return {
        "session_id": request.session_id or "new-session",
        "response": "Use the WebSocket endpoint /ws/{session_id} for full streaming.",
    }


@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint that streams agent events to the frontend."""
    await websocket.accept()
    logger.info("ws_connected", session_id=session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            user_message = payload.get("message", "")

            if not user_message.strip():
                error_event = StreamEvent(
                    event_type=StreamEventType.ERROR,
                    data={"error": "Empty message", "summary": "Please type a message."},
                )
                await websocket.send_text(error_event.model_dump_json())
                continue

            supervisor = _get_or_create_supervisor(session_id)

            try:
                async for event in supervisor.run(user_message):
                    await websocket.send_text(event.model_dump_json())
            except Exception as exc:
                logger.error(
                    "supervisor_error",
                    session_id=session_id,
                    error=str(exc),
                    traceback=traceback.format_exc(),
                )
                error_event = StreamEvent(
                    event_type=StreamEventType.ERROR,
                    data={
                        "error": str(exc),
                        "summary": "An unexpected error occurred during analysis.",
                    },
                )
                await websocket.send_text(error_event.model_dump_json())

    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=session_id)
    except Exception as exc:
        logger.error("ws_fatal", session_id=session_id, error=str(exc))
    finally:
        _supervisors.pop(session_id, None)
