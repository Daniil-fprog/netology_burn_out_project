"""Schemas for roles and role assignments; no permission entities yet."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enum import RoleCode
from app.schemas.common import ORMModel


class RoleCreate(BaseModel):
    code: RoleCode
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class RoleOut(ORMModel):
    id: str
    code: RoleCode
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class UserRoleCreate(BaseModel):
    user_id: int
    role_id: str


class UserRoleOut(ORMModel):
    id: str
    user_id: int
    role_id: str
    created_at: datetime
    updated_at: datetime
