"""Schemas for assigning users to schools and school groups."""

from datetime import datetime

from pydantic import BaseModel

from app.core.enum import RoleCode
from app.schemas.common import ORMModel


class AccessCreate(BaseModel):
    user_id: int
    role: RoleCode


class UserSchoolAssignmentCreate(BaseModel):
    user_id: int
    school_id: str


class UserSchoolAssignmentOut(ORMModel):
    id: str
    user_id: int
    school_id: str
    created_at: datetime
    updated_at: datetime


class UserSchoolGroupAssignmentCreate(BaseModel):
    user_id: int
    school_group_id: str


class UserSchoolGroupAssignmentOut(ORMModel):
    id: str
    user_id: int
    school_group_id: str
    created_at: datetime
    updated_at: datetime
