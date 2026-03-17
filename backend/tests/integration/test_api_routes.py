"""
Integration tests for FastAPI endpoints.

Tests the full HTTP layer — upload, download, datasets, sessions — using
httpx AsyncClient. The data and session routes are completely untested in
the existing suite, yet they are the direct entry point for every user action.
"""

from __future__ import annotations

import io
import json
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.routes import data as data_module


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


@pytest.fixture
def sample_csv_bytes() -> bytes:
    df = pd.DataFrame({"name": ["Alice", "Bob"], "age": [30, 25], "score": [90.5, 85.0]})
    return _csv_bytes(df)


@pytest.fixture
async def client():
    """Async test client that skips the lifespan (no real DB init needed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ─── Health ───────────────────────────────────────────────────────────────────


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body


# ─── Upload ───────────────────────────────────────────────────────────────────


class TestUpload:
    @pytest.mark.asyncio
    async def test_upload_csv(self, client, sample_csv_bytes):
        with patch.object(data_module, "save_dataset_metadata", new_callable=AsyncMock):
            resp = await client.post(
                "/api/v1/data/upload",
                files={"file": ("test.csv", sample_csv_bytes, "text/csv")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "dataset" in body
        assert body["dataset"]["filename"] == "test.csv"
        assert body["dataset"]["rows"] == 2
        assert body["dataset"]["columns"] == 3
        assert "preview" in body
        assert len(body["preview"]) == 2

    @pytest.mark.asyncio
    async def test_upload_no_file(self, client):
        resp = await client.post("/api/v1/data/upload")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_unsupported_type(self, client):
        resp = await client.post(
            "/api/v1/data/upload",
            files={"file": ("test.py", b"print('hello')", "text/plain")},
        )
        assert resp.status_code == 400


# ─── Datasets ────────────────────────────────────────────────────────────────


class TestDatasets:
    @pytest.mark.asyncio
    async def test_list_datasets_after_upload(self, client, sample_csv_bytes):
        with patch.object(data_module, "save_dataset_metadata", new_callable=AsyncMock):
            upload_resp = await client.post(
                "/api/v1/data/upload",
                files={"file": ("listed.csv", sample_csv_bytes, "text/csv")},
            )
        dataset_id = upload_resp.json()["dataset"]["id"]

        resp = await client.get("/api/v1/data/datasets")
        assert resp.status_code == 200
        ids = [d["id"] for d in resp.json()]
        assert dataset_id in ids

    @pytest.mark.asyncio
    async def test_preview_dataset(self, client, sample_csv_bytes):
        with patch.object(data_module, "save_dataset_metadata", new_callable=AsyncMock):
            upload_resp = await client.post(
                "/api/v1/data/upload",
                files={"file": ("preview.csv", sample_csv_bytes, "text/csv")},
            )
        dataset_id = upload_resp.json()["dataset"]["id"]

        resp = await client.get(f"/api/v1/data/datasets/{dataset_id}/preview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["dataset_id"] == dataset_id
        assert len(body["rows"]) == 2

    @pytest.mark.asyncio
    async def test_preview_nonexistent_returns_404(self, client):
        resp = await client.get("/api/v1/data/datasets/nonexistent/preview")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_download_csv(self, client, sample_csv_bytes):
        with patch.object(data_module, "save_dataset_metadata", new_callable=AsyncMock):
            upload_resp = await client.post(
                "/api/v1/data/upload",
                files={"file": ("dl.csv", sample_csv_bytes, "text/csv")},
            )
        dataset_id = upload_resp.json()["dataset"]["id"]

        resp = await client.get(f"/api/v1/data/datasets/{dataset_id}/download?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        lines = resp.text.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    @pytest.mark.asyncio
    async def test_download_json(self, client, sample_csv_bytes):
        with patch.object(data_module, "save_dataset_metadata", new_callable=AsyncMock):
            upload_resp = await client.post(
                "/api/v1/data/upload",
                files={"file": ("dlj.csv", sample_csv_bytes, "text/csv")},
            )
        dataset_id = upload_resp.json()["dataset"]["id"]

        resp = await client.get(f"/api/v1/data/datasets/{dataset_id}/download?format=json")
        assert resp.status_code == 200
        records = json.loads(resp.text)
        assert len(records) == 2
        assert "name" in records[0]

    @pytest.mark.asyncio
    async def test_download_nonexistent_returns_404(self, client):
        resp = await client.get("/api/v1/data/datasets/nonexistent/download")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_dataset(self, client, sample_csv_bytes):
        with patch.object(data_module, "save_dataset_metadata", new_callable=AsyncMock):
            upload_resp = await client.post(
                "/api/v1/data/upload",
                files={"file": ("del.csv", sample_csv_bytes, "text/csv")},
            )
        dataset_id = upload_resp.json()["dataset"]["id"]

        with patch.object(data_module, "delete_dataset_metadata", new_callable=AsyncMock):
            resp = await client.delete(f"/api/v1/data/datasets/{dataset_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        resp2 = await client.get(f"/api/v1/data/datasets/{dataset_id}/preview")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client):
        resp = await client.delete("/api/v1/data/datasets/nonexistent")
        assert resp.status_code == 404


# ─── Sessions ────────────────────────────────────────────────────────────────


class TestSessions:
    @pytest.mark.asyncio
    async def test_create_session(self, client):
        resp = await client.post("/api/v1/sessions/")
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert body["message_count"] == 0

    @pytest.mark.asyncio
    async def test_list_sessions(self, client):
        await client.post("/api/v1/sessions/")
        resp = await client.get("/api/v1/sessions/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_session(self, client):
        create_resp = await client.post("/api/v1/sessions/")
        session_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == session_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_returns_404(self, client):
        resp = await client.get("/api/v1/sessions/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        create_resp = await client.post("/api/v1/sessions/")
        session_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        get_resp = await client.get(f"/api/v1/sessions/{session_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session_returns_404(self, client):
        resp = await client.delete("/api/v1/sessions/nonexistent")
        assert resp.status_code == 404
