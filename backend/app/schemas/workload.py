"""Schemas for norms, versioned plans and daily actual work entries."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.core.enum import DailyLogStatus, DayType, PlanStatus, WorkLocation, WorkUnit
from app.core.work_duration import to_clock_hours
from app.schemas.common import ORMModel


class ClockHourDurationInput(BaseModel):
    """Accept clock hours directly or normalize an explicitly qualified duration."""

    duration_hours: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=4)
    duration: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=4, exclude=True)
    unit: WorkUnit = Field(default=WorkUnit.CLOCK_HOUR, exclude=True)

    @model_validator(mode="after")
    def normalize_to_clock_hours(self):
        if self.duration_hours is not None and self.duration is not None:
            raise ValueError("specify duration_hours or duration with unit, not both")
        if self.duration_hours is None:
            if self.duration is None:
                raise ValueError("duration_hours or duration is required")
            self.duration_hours = to_clock_hours(self.duration, self.unit)
            self.duration = None
        return self


class WorkloadNormCreate(BaseModel):
    teacher_id: str
    effective_from: date
    effective_to: date | None = None
    contract_teaching_hours_per_week: Decimal = Field(ge=0, max_digits=6, decimal_places=2)
    standard_teaching_hours_per_rate: Decimal = Field(gt=0, max_digits=6, decimal_places=2)
    comment: str | None = None
    plan_source: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def valid_period(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be earlier than effective_from")
        return self


class WorkloadNormOut(WorkloadNormCreate, ORMModel):
    id: str
    source_import_id: str | None
    created_at: datetime
    updated_at: datetime


class WorkloadPlanVersionCreate(BaseModel):
    school_id: str
    version: int = Field(ge=1)
    status: PlanStatus = PlanStatus.DRAFT
    effective_from: date
    effective_to: date
    source_import_id: str | None = None
    change_comment: str | None = None

    @model_validator(mode="after")
    def valid_period(self):
        if self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be earlier than effective_from")
        return self


class WorkloadPlanVersionOut(WorkloadPlanVersionCreate, ORMModel):
    id: str
    created_by: int | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PlannedWorkItemCreate(ClockHourDurationInput):
    plan_version_id: str
    teacher_id: str
    work_type_id: str
    work_date: date
    day_type: DayType
    subject: str | None = Field(default=None, max_length=150)
    sequence_no: int = Field(default=1, ge=1)
    comment: str | None = None


class PlannedWorkItemOut(ORMModel):
    id: str
    plan_version_id: str
    teacher_id: str
    work_type_id: str
    work_date: date
    day_type: DayType
    subject: str | None
    duration_hours: Decimal
    sequence_no: int
    comment: str | None
    created_at: datetime
    updated_at: datetime


class ActualWorkEntryCreate(ClockHourDurationInput):
    planned_work_item_id: str | None = None
    work_type_id: str
    location: WorkLocation
    comment: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def entry_not_longer_than_day(self):
        if self.duration_hours is not None and self.duration_hours > Decimal("24"):
            raise ValueError("one actual entry cannot exceed 24 hours")
        return self


class ActualWorkEntryOut(ORMModel):
    id: str
    daily_log_id: str
    planned_work_item_id: str | None
    work_type_id: str
    duration_hours: Decimal
    location: WorkLocation
    comment: str | None
    created_by: int | None
    updated_by: int | None
    created_at: datetime
    updated_at: datetime


class ActualPatch(BaseModel):
    day_type: DayType | None = None
    status: DailyLogStatus | None = None
    comment: str | None = Field(default=None, max_length=3000)
    entries: list[ActualWorkEntryCreate] | None = None

    @model_validator(mode="after")
    def total_does_not_exceed_day(self):
        if self.entries is not None:
            total = sum(
                (entry.duration_hours or Decimal("0") for entry in self.entries),
                start=Decimal("0"),
            )
            if total > Decimal("24"):
                raise ValueError("total actual workload cannot exceed 24 hours per day")
        return self


class DailyWorkLogCreate(BaseModel):
    teacher_id: str
    work_date: date
    day_type: DayType
    status: DailyLogStatus = DailyLogStatus.NOT_STARTED
    comment: str | None = Field(default=None, max_length=3000)
    entries: list[ActualWorkEntryCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def total_does_not_exceed_day(self):
        total = sum(
            (entry.duration_hours or Decimal("0") for entry in self.entries),
            start=Decimal("0"),
        )
        if total > Decimal("24"):
            raise ValueError("total actual workload cannot exceed 24 hours per day")
        return self


class DailyWorkLogOut(ORMModel):
    id: str
    teacher_id: str
    work_date: date
    day_type: DayType
    status: DailyLogStatus
    comment: str | None
    completed_at: datetime | None
    completed_by: int | None
    entries: list[ActualWorkEntryOut]
    created_at: datetime
    updated_at: datetime
