"""
Metrics API — exposes per-session and aggregate observability data.

GET /metrics                → all session summaries
GET /metrics/{session_id}   → single session metrics
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.observability.metrics import metrics_collector

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def get_all_metrics() -> dict:
    summaries = metrics_collector.get_all_summaries()
    return {
        "active_sessions": len(summaries),
        "sessions": summaries,
    }


@router.get("/{session_id}")
async def get_session_metrics(session_id: str) -> dict:
    summary = metrics_collector.get_session_summary(session_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"No metrics for session {session_id}")
    return summary
