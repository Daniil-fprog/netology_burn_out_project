"""Focused checks for the normalized teacher-domain data contract."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.enum import DayType, RoleCode, WorkLocation, WorkUnit, WorkloadTemplateWorkTypeCode
from app.core.workload_import_contract import DAY_TYPES, WORK_TYPE_CODES
from app.db.database import Base
from app.schemas.work_type import WorkTypeCreate
from app.schemas.survey import SurveyResponseRequest
from app.schemas.workload import ActualWorkEntryCreate, DailyWorkLogCreate


def test_required_domain_tables_are_registered():
    expected = {
        "roles", "user_roles", "school_groups", "school_group_schools",
        "user_school_group_assignments", "workload_types", "workload_plan_versions",
        "workload_planned_items", "workload_daily_logs", "workload_actual_entries", "export_jobs",
    }
    assert expected <= set(Base.metadata.tables)
    assert "permissions" not in Base.metadata.tables
    assert "role_permissions" not in Base.metadata.tables
    assert "survey_export_jobs" not in Base.metadata.tables
    assert "survey_ml_labels" not in Base.metadata.tables
    assert "survey_consents" not in Base.metadata.tables


def test_school_assignment_does_not_duplicate_role_or_teacher_link():
    columns = set(Base.metadata.tables["user_school_access"].columns.keys())
    assert "role" not in columns
    assert "teacher_id" not in columns
    assert {"user_id", "school_id"} <= columns
    assert "can_read_comments" not in columns
    assert "can_export_research" not in columns


def test_role_codes_match_specification():
    assert {role.value for role in RoleCode} == {
        "teacher", "director", "head", "group_head", "system_admin",
    }


def test_workload_import_contract_is_derived_from_enums():
    assert DAY_TYPES == frozenset(item.value for item in DayType)
    assert WORK_TYPE_CODES == tuple(item.value for item in WorkloadTemplateWorkTypeCode)


def test_work_type_has_no_persistence_unit_fields():
    columns = set(Base.metadata.tables["workload_types"].columns)
    assert "default_unit" not in columns
    assert "allowed_units" not in columns
    work_type = WorkTypeCreate(
        code="lessons",
        name="Проведение уроков",
        category_group="teaching",
    )
    assert "default_unit" not in work_type.model_dump()
    assert "allowed_units" not in work_type.model_dump()


def test_daily_actual_total_cannot_exceed_24_hours():
    entries = [
        ActualWorkEntryCreate(
            work_type_id="work-type-id", duration=Decimal("20"),
            unit=WorkUnit.CLOCK_HOUR, location=WorkLocation.SCHOOL,
        ),
        ActualWorkEntryCreate(
            work_type_id="work-type-id", duration=Decimal("5"),
            unit=WorkUnit.CLOCK_HOUR, location=WorkLocation.HOME,
        ),
    ]
    with pytest.raises(ValidationError):
        DailyWorkLogCreate(
            teacher_id="teacher-id", work_date=date(2026, 11, 6),
            day_type=DayType.SCHOOL_DAY, entries=entries,
        )


def test_daily_actual_accepts_explicit_mixed_units():
    log = DailyWorkLogCreate(
        teacher_id="teacher-id",
        work_date=date(2026, 11, 6),
        day_type=DayType.SCHOOL_DAY,
        entries=[
            ActualWorkEntryCreate(
                work_type_id="lessons", duration=Decimal("8"),
                unit=WorkUnit.TEACHING_HOUR, location=WorkLocation.SCHOOL,
            ),
            ActualWorkEntryCreate(
                work_type_id="preparation", duration=Decimal("2"),
                unit=WorkUnit.CLOCK_HOUR, location=WorkLocation.HOME,
            ),
        ],
    )
    assert [entry.duration_hours for entry in log.entries] == [Decimal("6.00"), Decimal("2")]
    assert all("unit" not in entry.model_dump() for entry in log.entries)


def test_survey_creation_requires_embedded_consent():
    with pytest.raises(ValidationError):
        SurveyResponseRequest(
            survey_code="daily_checkin",
            assessment_date=date(2026, 11, 18),
            period_start=date(2026, 11, 18),
            period_end=date(2026, 11, 18),
            consent_given=False,
            answers={"fatigue_score": 3},
        )
