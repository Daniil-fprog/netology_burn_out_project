"""Schemas for the shared work-type directory."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class WorkTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=255)
    category_group: str = Field(min_length=1, max_length=120)
    complexity_weight: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        le=1,
        max_digits=5,
        decimal_places=4,
    )
    requires_comment: bool = False
    description: str | None = None


class WorkTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_group: str | None = Field(default=None, min_length=1, max_length=120)
    complexity_weight: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
        max_digits=5,
        decimal_places=4,
    )
    requires_comment: bool | None = None
    is_active: bool | None = None
    description: str | None = None


class WorkTypeOut(ORMModel):
    id: str
    code: str
    name: str
    category_group: str
    complexity_weight: Decimal
    requires_comment: bool
    is_active: bool
    description: str | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
