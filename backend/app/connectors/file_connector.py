"""
File connector — handles CSV/Excel/JSON/Parquet ingestion into pandas DataFrames.

Validates files, reads them into DataFrames, and registers them in the
AnalysisContext so specialists can access them.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from app.agent.specialists.context import AnalysisContext, DataSchema
from app.config import settings
from app.guardrails.validator import InputValidator, ValidationResult

logger = structlog.get_logger(__name__)

READERS = {
    "csv": lambda buf, **kw: pd.read_csv(buf, **kw),
    "xlsx": lambda buf, **kw: pd.read_excel(buf, engine="openpyxl", **kw),
    "xls": lambda buf, **kw: pd.read_excel(buf, engine="openpyxl", **kw),
    "json": lambda buf, **kw: pd.read_json(buf, **kw),
    "parquet": lambda buf, **kw: pd.read_parquet(buf, **kw),
}


class FileConnector:
    """Ingests uploaded files into pandas DataFrames and registers them in the context."""

    def __init__(self, context: AnalysisContext) -> None:
        self._context = context
        self._validator = InputValidator()

    async def ingest_upload(
        self, filename: str, file_bytes: bytes
    ) -> tuple[DataSchema, list[dict[str, Any]]]:
        """
        Read an uploaded file into a DataFrame and register it.

        Returns:
            (schema, preview_rows) — schema metadata and first 20 rows as dicts.

        Raises:
            ValueError: If file validation or parsing fails.
        """
        validation = self._validator.validate_file_upload(filename, len(file_bytes))
        if not validation.valid:
            raise ValueError(validation.error)

        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        reader = READERS.get(extension)
        if reader is None:
            raise ValueError(f"Unsupported file type: '{extension}'")

        logger.info(
            "file_ingest_start",
            filename=filename,
            extension=extension,
            size_bytes=len(file_bytes),
        )

        try:
            buf = io.BytesIO(file_bytes)
            df = reader(buf)
        except UnicodeDecodeError:
            # Retry CSV/JSON with latin-1 which accepts any byte sequence
            if extension in ("csv", "json"):
                logger.info("file_ingest_encoding_fallback", filename=filename, fallback="latin-1")
                buf = io.BytesIO(file_bytes)
                df = reader(buf, encoding="latin-1")
            else:
                raise
        except Exception as e:
            logger.error("file_ingest_parse_error", filename=filename, error=str(e))
            raise ValueError(f"Failed to parse '{filename}': {str(e)}") from e

        if df.empty:
            raise ValueError(f"File '{filename}' contains no data.")

        dataset_id = str(uuid.uuid4())[:8]

        # Save to disk for persistence
        save_path = settings.upload_path / f"{dataset_id}_{filename}"
        save_path.write_bytes(file_bytes)

        schema = self._context.add_dataset(dataset_id, df, filename)

        preview = self._build_preview(df, max_rows=20)

        logger.info(
            "file_ingest_complete",
            dataset_id=dataset_id,
            filename=filename,
            rows=schema.row_count,
            columns=schema.column_count,
        )

        return schema, preview

    def get_dataset(self, dataset_id: str) -> pd.DataFrame | None:
        """Retrieve a loaded DataFrame by its ID."""
        return self._context.datasets.get(dataset_id)

    def get_schema(self, dataset_id: str) -> DataSchema | None:
        return self._context.schemas.get(dataset_id)

    def list_datasets(self) -> list[DataSchema]:
        return list(self._context.schemas.values())

    def get_preview(self, dataset_id: str, max_rows: int = 20) -> list[dict[str, Any]]:
        df = self.get_dataset(dataset_id)
        if df is None:
            return []
        return self._build_preview(df, max_rows)

    def _build_preview(self, df: pd.DataFrame, max_rows: int = 20) -> list[dict[str, Any]]:
        """Convert first N rows to a list of dicts, handling NaN serialization."""
        preview_df = df.head(max_rows)
        records = []
        for _, row in preview_df.iterrows():
            record = {}
            for col in preview_df.columns:
                val = row[col]
                if pd.isna(val):
                    record[str(col)] = None
                elif hasattr(val, "item"):
                    record[str(col)] = val.item()
                else:
                    record[str(col)] = val
            records.append(record)
        return records
