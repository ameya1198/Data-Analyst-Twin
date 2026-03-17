import io
from typing import Any

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.agent.specialists.context import AnalysisContext
from app.connectors.file_connector import FileConnector
from app.database import save_dataset_metadata, delete_dataset_metadata
from app.config import settings
from app.models.schemas import DatasetInfo, UploadResponse

router = APIRouter(prefix="/data", tags=["data"])

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

    file_path = str(settings.upload_path / f"{schema.dataset_id}_{file.filename}")
    await save_dataset_metadata(
        dataset_id=schema.dataset_id,
        filename=schema.filename,
        file_path=file_path,
        rows=schema.row_count,
        columns=schema.column_count,
        column_names=[c.name for c in schema.columns],
        dtypes={c.name: c.dtype for c in schema.columns},
        size_bytes=schema.size_bytes,
    )

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


@router.delete("/datasets/{dataset_id}")
async def remove_dataset(dataset_id: str) -> dict[str, str]:
    """Remove a dataset from context and database."""
    if dataset_id not in _context.datasets:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

    _context.datasets.pop(dataset_id, None)
    _context.schemas.pop(dataset_id, None)
    await delete_dataset_metadata(dataset_id)

    return {"status": "deleted", "dataset_id": dataset_id}


@router.get("/datasets/{dataset_id}/download")
async def download_dataset(
    dataset_id: str,
    format: str = Query("csv", pattern="^(csv|xlsx|json)$"),
):
    """Download a dataset as CSV, Excel, or JSON."""
    df = _context.datasets.get(dataset_id)
    if df is None:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

    schema = _context.schemas.get(dataset_id)
    base_name = schema.filename.rsplit(".", 1)[0] if schema else dataset_id

    if format == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.csv"'},
        )

    if format == "xlsx":
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.xlsx"'},
        )

    if format == "json":
        content = df.to_json(orient="records", date_format="iso")
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.json"'},
        )
