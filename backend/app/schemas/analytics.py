"""Response contracts for workload analytics defined by the UI specification."""

from datetime import date

from pydantic import BaseModel


class PlannedKPI(BaseModel):
    planned_teaching_hours: float
    teacher_count: int
    average_teaching_hours: float | None
    median_teaching_hours: float | None


class PlannedWeeklyPoint(BaseModel):
    week_start: date
    hours: float


class PlannedSubjectPoint(BaseModel):
    subject: str
    hours: float


class PlannedSchoolPoint(BaseModel):
    school: str
    hours: float


class PlannedTeacherRow(BaseModel):
    teacher_id: str
    full_name: str | None
    subject: str
    planned_hours: float
    planned_teaching_hours: float
    individual_norm_hours: float | None
    deviation_from_norm_hours: float | None


class PlannedDashboardOut(BaseModel):
    date_from: date
    date_to: date
    kpi: PlannedKPI
    weekly: list[PlannedWeeklyPoint]
    by_subject: list[PlannedSubjectPoint]
    by_school: list[PlannedSchoolPoint]
    teachers: list[PlannedTeacherRow]
