import json
import traceback
import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agent import create_supervisor
from app.agent.supervisor import Supervisor
from app.api.routes.data import get_context
from app.database import (
    save_message,
    load_messages,
    get_session as db_get_session,
    create_session as db_create_session,
    touch_session,
)
from app.models.schemas import ChatRequest, StreamEvent, StreamEventType

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

_supervisors: dict[str, Supervisor] = {}


async def _get_or_create_supervisor(session_id: str) -> Supervisor:
    """Reuse a Supervisor per WebSocket session so conversation memory persists."""
    context = get_context()
    if session_id not in _supervisors:
        sup = create_supervisor(context=context)
        try:
            await sup.reload_memory(session_id)
        except Exception:
            logger.warning("memory_reload_failed", session_id=session_id)
        _supervisors[session_id] = sup
    else:
        sup = _supervisors[session_id]
        sup.context = context
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
    """
    WebSocket endpoint that streams agent events to the frontend.

    When a CONFIRMATION_REQUEST event is emitted by the supervisor (for
    destructive operations), the handler pauses the event stream, reads the
    next WebSocket message (the user's approval/rejection), resolves the
    ConfirmationManager future, and then resumes iterating.
    """
    await websocket.accept()
    logger.info("ws_connected", session_id=session_id)

    try:
        existing_session = await db_get_session(session_id)
        if existing_session is None:
            await db_create_session(session_id)
    except Exception as exc:
        logger.warning("session_persist_failed", session_id=session_id, error=str(exc))

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)

            if payload.get("type") == "confirmation_response":
                sup = _supervisors.get(session_id)
                if sup:
                    sup.confirmation_manager.resolve(
                        payload["request_id"],
                        payload["approved"],
                    )
                continue

            user_message = payload.get("message", "")

            if not user_message.strip():
                error_event = StreamEvent(
                    event_type=StreamEventType.ERROR,
                    data={"error": "Empty message", "summary": "Please type a message."},
                )
                await websocket.send_text(error_event.model_dump_json())
                continue

            try:
                await save_message(
                    message_id=str(uuid.uuid4()),
                    session_id=session_id,
                    role="user",
                    content=user_message,
                )
            except Exception:
                logger.warning("save_user_message_failed", session_id=session_id)

            supervisor = await _get_or_create_supervisor(session_id)
            assistant_content = ""

            try:
                async for event in supervisor.run(user_message):
                    await websocket.send_text(event.model_dump_json())

                    if event.event_type == StreamEventType.FINAL_RESPONSE:
                        data = event.data
                        if isinstance(data, dict):
                            assistant_content = data.get("response", data.get("summary", ""))
                        elif isinstance(data, str):
                            assistant_content = data

                    if event.event_type == StreamEventType.CONFIRMATION_REQUEST:
                        conf_raw = await websocket.receive_text()
                        conf_payload = json.loads(conf_raw)
                        if conf_payload.get("type") == "confirmation_response":
                            supervisor.confirmation_manager.resolve(
                                conf_payload["request_id"],
                                conf_payload["approved"],
                            )
                        else:
                            logger.warning(
                                "unexpected_message_during_confirmation",
                                payload=conf_payload,
                            )

                if assistant_content:
                    try:
                        await save_message(
                            message_id=str(uuid.uuid4()),
                            session_id=session_id,
                            role="assistant",
                            content=assistant_content,
                        )
                        await touch_session(session_id)
                    except Exception:
                        logger.warning("save_assistant_message_failed", session_id=session_id)

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
