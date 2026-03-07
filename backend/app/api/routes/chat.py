import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models.schemas import ChatRequest, StreamEvent, StreamEventType

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message")
async def send_message(request: ChatRequest) -> dict:
    """REST fallback for sending a chat message. Prefer WebSocket for streaming."""
    return {
        "session_id": request.session_id or "new-session",
        "response": "Agent orchestrator not yet wired. This is a skeleton endpoint.",
    }


@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for streaming agent responses."""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Placeholder: echo back with a plan event to prove streaming works
            plan_event = StreamEvent(
                event_type=StreamEventType.PLAN,
                data={"steps": ["This is a skeleton response. Agent not yet wired."]},
            )
            await websocket.send_text(plan_event.model_dump_json())

            final_event = StreamEvent(
                event_type=StreamEventType.FINAL_RESPONSE,
                data=f"Echo: {message.get('message', '')}",
            )
            await websocket.send_text(final_event.model_dump_json())

    except WebSocketDisconnect:
        pass
