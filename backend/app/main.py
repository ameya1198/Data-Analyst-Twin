from contextlib import asynccontextmanager
from pathlib import Path
import io
import json

import pandas as pd
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import RequestLoggingMiddleware
from app.api.routes import chat, data, sessions
from app.config import settings
from app.database import init_db, load_all_datasets


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.is_development else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

READERS = {
    "csv": lambda buf: pd.read_csv(buf),
    "xlsx": lambda buf: pd.read_excel(buf, engine="openpyxl"),
    "xls": lambda buf: pd.read_excel(buf, engine="openpyxl"),
    "json": lambda buf: pd.read_json(buf),
    "parquet": lambda buf: pd.read_parquet(buf),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "startup",
        environment=settings.app_env,
        host=settings.app_host,
        port=settings.app_port,
        cors_origins=settings.cors_origin_list,
    )
    settings.upload_path

    await init_db()

    ctx = data.get_context()
    saved_datasets = await load_all_datasets()
    reloaded = 0
    for ds in saved_datasets:
        file_path = Path(ds.file_path)
        if not file_path.exists():
            logger.warning("dataset_file_missing", dataset_id=ds.id, path=str(file_path))
            continue

        ext = ds.filename.rsplit(".", 1)[-1].lower() if "." in ds.filename else ""
        reader = READERS.get(ext)
        if reader is None:
            logger.warning("dataset_unsupported_ext", dataset_id=ds.id, ext=ext)
            continue

        try:
            df = reader(file_path)
            ctx.add_dataset(ds.id, df, ds.filename)
            reloaded += 1
        except Exception as e:
            logger.warning("dataset_reload_failed", dataset_id=ds.id, error=str(e))

    if reloaded:
        logger.info("datasets_reloaded", count=reloaded, total=len(saved_datasets))

    yield
    logger.info("shutdown")


app = FastAPI(
    title="Data Analyst Digital Twin",
    description="AI-powered agent that mimics the reasoning, workflow, and outputs of a real data analyst.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(chat.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "environment": settings.app_env,
    }
