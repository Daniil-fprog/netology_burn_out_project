"""Shared Pydantic types for the teacher workload domain."""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base response schema that can read SQLAlchemy model attributes."""

    model_config = ConfigDict(from_attributes=True)


class RoleCode(str, Enum):
    TEACHER = "teacher"
    DIRECTOR = "director"
    HEAD = "head"
    GROUP_HEAD = "group_head"
    SYSTEM_ADMIN = "system_admin"


class WorkUnit(str, Enum):
    TEACHING_HOUR = "teaching_hour"
    CLOCK_MINUTE = "clock_minute"


class WorkLocation(str, Enum):
    SCHOOL = "school"
    HOME = "home"
    OTHER = "other"


class DailyLogStatus(str, Enum):
    NOT_STARTED = "not_started"
    DRAFT = "draft"
    COMPLETED = "completed"


class PlanStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SurveyCadence(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SurveyResponseStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    WITHDRAWN = "withdrawn"


class ExportFormat(str, Enum):
    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"
