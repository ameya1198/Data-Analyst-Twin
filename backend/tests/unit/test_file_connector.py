"""Tests for the file connector."""

import io

import pandas as pd
import pytest

from app.agent.specialists.context import AnalysisContext
from app.connectors.file_connector import FileConnector


@pytest.fixture
def connector():
    ctx = AnalysisContext()
    return FileConnector(ctx), ctx


class TestFileConnector:
    async def test_ingest_csv(self, connector):
        fc, ctx = connector
        csv_bytes = b"name,age,salary\nAlice,30,50000\nBob,25,60000\n"
        schema, preview = await fc.ingest_upload("data.csv", csv_bytes)
        assert schema.row_count == 2
        assert schema.column_count == 3
        assert len(preview) == 2

    async def test_ingest_json(self, connector):
        fc, ctx = connector
        json_bytes = b'[{"name":"Alice","age":30},{"name":"Bob","age":25}]'
        schema, preview = await fc.ingest_upload("data.json", json_bytes)
        assert schema.row_count == 2

    async def test_ingest_unsupported_type(self, connector):
        fc, ctx = connector
        with pytest.raises(ValueError, match="not allowed"):
            await fc.ingest_upload("data.exe", b"binary stuff")

    async def test_ingest_empty_file(self, connector):
        fc, ctx = connector
        with pytest.raises(ValueError):
            await fc.ingest_upload("empty.csv", b"col1,col2\n")

    async def test_ingest_malformed_csv(self, connector):
        fc, ctx = connector
        with pytest.raises(ValueError, match="Failed to parse"):
            await fc.ingest_upload("bad.json", b"this is not json{{{")

    async def test_dataset_registered_in_context(self, connector):
        fc, ctx = connector
        csv_bytes = b"x,y\n1,2\n3,4\n"
        schema, _ = await fc.ingest_upload("test.csv", csv_bytes)
        assert schema.dataset_id in ctx.datasets
        df = fc.get_dataset(schema.dataset_id)
        assert df is not None
        assert len(df) == 2

    async def test_list_datasets(self, connector):
        fc, ctx = connector
        assert len(fc.list_datasets()) == 0
        csv_bytes = b"x,y\n1,2\n3,4\n"
        await fc.ingest_upload("test.csv", csv_bytes)
        assert len(fc.list_datasets()) == 1

    async def test_get_preview(self, connector):
        fc, ctx = connector
        rows = "\n".join(f"x,y\n" + "\n".join(f"{i},{i*2}" for i in range(30)))
        csv_bytes = f"x,y\n" + "\n".join(f"{i},{i*2}" for i in range(30))
        schema, _ = await fc.ingest_upload("big.csv", csv_bytes.encode())
        preview = fc.get_preview(schema.dataset_id, max_rows=10)
        assert len(preview) == 10

    async def test_get_nonexistent_dataset(self, connector):
        fc, ctx = connector
        assert fc.get_dataset("nope") is None
        assert fc.get_schema("nope") is None

    async def test_preview_handles_nan(self, connector):
        fc, ctx = connector
        csv_bytes = b"x,y\n1,2\n3,\n5,6\n"
        schema, preview = await fc.ingest_upload("nan.csv", csv_bytes)
        null_row = preview[1]
        assert null_row["y"] is None

    async def test_no_filename(self, connector):
        fc, ctx = connector
        with pytest.raises(ValueError):
            await fc.ingest_upload("", b"data")

    async def test_file_too_large(self, connector):
        fc, ctx = connector
        huge = b"x" * (200 * 1024 * 1024)
        with pytest.raises(ValueError, match="too large"):
            await fc.ingest_upload("big.csv", huge)
