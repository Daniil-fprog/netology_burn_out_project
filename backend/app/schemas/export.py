"""Schemas for asynchronous report and ML dataset exports."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.enum import ExportFormat
from app.schemas.common import ORMModel


class ExportJobCreate(BaseModel):
    school_id: str | None = None
    school_group_id: str | None = None
    report_type: str = Field(min_length=1, max_length=50)
    format: ExportFormat
    filters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def exactly_one_scope(self):
        if (self.school_id is None) == (self.school_group_id is None):
            raise ValueError("exactly one of school_id or school_group_id is required")
        return self


class ExportJobOut(ORMModel):
    id: str
    requested_by: int | None
    school_id: str | None
    school_group_id: str | None
    report_type: str
    format: ExportFormat
    filters_jsonb: dict[str, Any]
    status: str
    row_count: int | None
    expires_at: datetime | None
    downloaded_at: datetime | None
    download_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
