"""Schemas for the teacher directory and account linkage."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TeacherCreate(BaseModel):
    user_id: int | None = None
    external_id: str = Field(min_length=1, max_length=80)
    full_name: str | None = Field(default=None, max_length=255)
    subject: str = Field(min_length=1, max_length=150)


class TeacherUpdate(BaseModel):
    user_id: int | None = None
    full_name: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None


class TeacherOut(ORMModel):
    id: str
    school_id: str
    user_id: int | None
    external_id: str
    full_name: str | None
    subject: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
