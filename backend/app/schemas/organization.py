"""Schemas for schools, school groups and their membership."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    external_code: str | None = Field(default=None, max_length=80)


class SchoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    external_code: str | None = Field(default=None, max_length=80)


class SchoolOut(ORMModel):
    id: str
    name: str
    external_code: str | None
    created_at: datetime
    updated_at: datetime


class SchoolGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    external_code: str | None = Field(default=None, max_length=80)


class SchoolGroupOut(ORMModel):
    id: str
    name: str
    external_code: str | None
    created_at: datetime
    updated_at: datetime


class SchoolGroupSchoolCreate(BaseModel):
    school_id: str


class SchoolGroupSchoolOut(ORMModel):
    id: str
    group_id: str
    school_id: str
