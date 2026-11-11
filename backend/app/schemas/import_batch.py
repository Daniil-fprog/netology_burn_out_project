"""Schemas for workload import validation and history."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ImportBatchCreate(BaseModel):
    school_id: str
    original_filename: str = Field(min_length=1, max_length=255)
    template_version: str = Field(default="1.0", max_length=20)
    mode: str = Field(pattern="^(insert_only|upsert|replace_period)$")
    effective_from: date


class ImportBatchOut(ORMModel):
    id: str
    school_id: str
    original_filename: str
    sha256: str
    template_version: str
    status: str
    mode: str
    effective_from: date
    rows_total: int
    rows_created: int
    rows_updated: int
    rows_skipped: int
    validation_report: dict[str, Any]
    uploaded_by: int | None
    imported_at: datetime | None
    created_at: datetime
    updated_at: datetime
