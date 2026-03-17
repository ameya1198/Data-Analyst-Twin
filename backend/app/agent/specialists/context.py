"""
AnalysisContext — shared mutable state across all specialists within a session.

Every specialist receives and writes to this context. It holds loaded datasets,
their schemas, accumulated analysis results, and named intermediate variables.
This is how the Viz specialist knows what the EDA specialist found.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import pandas as pd


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    non_null_count: int
    null_count: int
    null_pct: float
    unique_count: int
    sample_values: list[Any] = field(default_factory=list)


@dataclass
class DataSchema:
    dataset_id: str
    filename: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile] = field(default_factory=list)
    size_bytes: int = 0

    def to_summary(self) -> str:
        """One-paragraph text summary for LLM context injection."""
        col_desc = ", ".join(
            f"{c.name} ({c.dtype}, {c.null_pct:.0f}% null)" for c in self.columns
        )
        return (
            f"Dataset '{self.filename}' (dataset_id='{self.dataset_id}'): "
            f"{self.row_count} rows x {self.column_count} columns. "
            f"Columns: [{col_desc}]"
        )


@dataclass
class SpecialistResultEntry:
    """One result produced by a specialist during execution."""
    specialist_name: str
    step_description: str
    result_type: str  # "table", "chart", "statistic", "text", "code", "error"
    data: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisContext:
    """
    Shared state passed to every specialist.

    The supervisor creates one per session. Specialists read from and write to it,
    enabling downstream specialists to build on upstream results.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Loaded datasets keyed by dataset_id
    datasets: dict[str, pd.DataFrame] = field(default_factory=dict)

    # Computed schemas keyed by dataset_id
    schemas: dict[str, DataSchema] = field(default_factory=dict)

    # Accumulated results from all specialists (chronological)
    results: list[SpecialistResultEntry] = field(default_factory=list)

    # Named intermediate variables (e.g. "filtered_df", "correlation_matrix")
    variables: dict[str, Any] = field(default_factory=dict)

    # User preferences and connection configs
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_dataset(self, dataset_id: str, df: pd.DataFrame, filename: str) -> DataSchema:
        """Register a dataset and compute its schema."""
        self.datasets[dataset_id] = df

        columns = []
        for col in df.columns:
            series = df[col]
            null_count = int(series.isna().sum())
            total = len(series)
            columns.append(ColumnProfile(
                name=str(col),
                dtype=str(series.dtype),
                non_null_count=total - null_count,
                null_count=null_count,
                null_pct=round((null_count / total) * 100, 1) if total > 0 else 0.0,
                unique_count=int(series.nunique()),
                sample_values=series.dropna().head(5).tolist(),
            ))

        schema = DataSchema(
            dataset_id=dataset_id,
            filename=filename,
            row_count=len(df),
            column_count=len(df.columns),
            columns=columns,
            size_bytes=df.memory_usage(deep=True).sum(),
        )
        self.schemas[dataset_id] = schema
        return schema

    def add_result(self, specialist_name: str, step_description: str,
                   result_type: str, data: Any, **metadata: Any) -> None:
        """Append a result entry from a specialist."""
        self.results.append(SpecialistResultEntry(
            specialist_name=specialist_name,
            step_description=step_description,
            result_type=result_type,
            data=data,
            metadata=metadata,
        ))

    def set_variable(self, name: str, value: Any) -> None:
        """Store a named intermediate value for downstream specialists."""
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, default)

    def get_dataset_summaries(self) -> str:
        """All dataset schemas as text — injected into LLM prompts."""
        if not self.schemas:
            return "No datasets loaded."
        return "\n\n".join(s.to_summary() for s in self.schemas.values())

    def get_recent_results_summary(self, limit: int = 10) -> str:
        """Last N results as text — injected into LLM prompts for continuity."""
        recent = self.results[-limit:]
        if not recent:
            return "No analysis results yet."
        lines = []
        for r in recent:
            data_preview = str(r.data)[:200] if r.data is not None else "None"
            lines.append(f"[{r.specialist_name}] {r.step_description}: {data_preview}")
        return "\n".join(lines)

    def resolve_dataset_id(self, identifier: str) -> str | None:
        """Resolve a dataset_id, dataset_name, or filename to a valid dataset_id."""
        if identifier in self.datasets:
            return identifier
        for did, schema in self.schemas.items():
            if schema.filename == identifier or schema.filename.lower() == identifier.lower():
                return did
        if not identifier and len(self.datasets) == 1:
            return next(iter(self.datasets))
        return None

    @property
    def dataset_ids(self) -> list[str]:
        return list(self.datasets.keys())

    @property
    def has_data(self) -> bool:
        return len(self.datasets) > 0
