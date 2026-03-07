from typing import Any

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.agent.specialists.context import AnalysisContext
from app.connectors.file_connector import FileConnector
from app.models.schemas import DatasetInfo, UploadResponse

router = APIRouter(prefix="/data", tags=["data"])

# Shared context and connector — will be replaced by proper DI in Phase 2
_context = AnalysisContext()
_connector = FileConnector(_context)


def get_connector() -> FileConnector:
    return _connector


def get_context() -> AnalysisContext:
    return _context


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a CSV/Excel file for analysis."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_bytes = await file.read()

    try:
        schema, preview = await _connector.ingest_upload(file.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return UploadResponse(
        dataset=DatasetInfo(
            id=schema.dataset_id,
            filename=schema.filename,
            rows=schema.row_count,
            columns=schema.column_count,
            column_names=[c.name for c in schema.columns],
            dtypes={c.name: c.dtype for c in schema.columns},
            size_bytes=schema.size_bytes,
        ),
        preview=preview,
    )


@router.get("/datasets")
async def list_datasets() -> list[DatasetInfo]:
    """List all uploaded datasets in the current session."""
    schemas = _connector.list_datasets()
    return [
        DatasetInfo(
            id=s.dataset_id,
            filename=s.filename,
            rows=s.row_count,
            columns=s.column_count,
            column_names=[c.name for c in s.columns],
            dtypes={c.name: c.dtype for c in s.columns},
            size_bytes=s.size_bytes,
        )
        for s in schemas
    ]


@router.get("/datasets/{dataset_id}/preview")
async def preview_dataset(dataset_id: str, rows: int = 20) -> dict[str, Any]:
    """Preview first N rows of a dataset."""
    schema = _connector.get_schema(dataset_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

    preview = _connector.get_preview(dataset_id, max_rows=rows)
    return {
        "dataset_id": dataset_id,
        "filename": schema.filename,
        "rows": preview,
        "total_rows": schema.row_count,
    }
