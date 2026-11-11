from enum import Enum


class RoleCode(str, Enum):
    TEACHER = "teacher"
    DIRECTOR = "director"
    HEAD = "head"
    GROUP_HEAD = "group_head"
    SYSTEM_ADMIN = "system_admin"


class WorkUnit(str, Enum):
    TEACHING_HOUR = "teaching_hour"
    CLOCK_HOUR = "clock_hour"


class WorkLocation(str, Enum):
    SCHOOL = "school"
    HOME = "home"
    OTHER = "other"


class DayType(str, Enum):
    SCHOOL_DAY = "Учебный день"
    WEEKEND = "Выходной"
    HOLIDAY = "Каникулы"
    VACATION = "Отпуск"
    SICK_LEAVE = "Больничный"
    OTHER = "Другое"


class WorkloadTemplateWorkTypeCode(str, Enum):
    """Fixed work-type columns supported by workload template version 1.0.

    This is not the complete work-type directory: additional categories remain
    configurable in the database.
    """

    LESSONS = "lessons"
    SUBSTITUTIONS = "substitutions"
    PREPARATION = "preparation"
    GRADING = "grading"
    DOCUMENTATION = "documentation"
    PARENT_COMMUNICATION = "parent_communication"
    CLASS_MANAGEMENT = "class_management"
    MEETINGS_METHODOLOGY = "meetings_methodology"
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
