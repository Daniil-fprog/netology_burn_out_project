"""Service-level acceptance checks derived from the pages/functions specification."""

from datetime import date
from decimal import Decimal

from app.models.organization import SchoolModel
from app.models.teacher import TeacherModel
from app.models.user import UserModel
from app.models.work_type import WorkTypeModel
from app.models.workload import PlannedWorkItemModel, TeacherWorkloadNormModel, WorkloadPlanVersionModel
from app.schemas.work_type import WorkTypeCreate
from app.services.analytics_service import get_planned_dashboard
from app.services.work_type_service import archive_work_type, create_work_type, list_work_types


def test_planned_dashboard_contains_only_plan_and_norm_data(db_session):
    school = SchoolModel(name="Школа №1")
    db_session.add(school)
    db_session.flush()
    teacher = TeacherModel(school_id=school.id, external_id="T-1", full_name="Иванова И.И.", subject="Математика")
    work_type = WorkTypeModel(code="lessons-test", name="Уроки", category_group="teaching", complexity_weight=Decimal("0"))
    db_session.add_all([teacher, work_type])
    db_session.flush()
    plan = WorkloadPlanVersionModel(school_id=school.id, version=1, status="published", effective_from=date(2026, 11, 1), effective_to=date(2026, 11, 30))
    norm = TeacherWorkloadNormModel(teacher_id=teacher.id, effective_from=date(2026, 9, 1), contract_teaching_hours_per_week=Decimal("18"), standard_teaching_hours_per_rate=Decimal("18"))
    db_session.add_all([plan, norm])
    db_session.flush()
    db_session.add(PlannedWorkItemModel(plan_version_id=plan.id, teacher_id=teacher.id, work_type_id=work_type.id, work_date=date(2026, 11, 9), day_type="Учебный день", duration_hours=Decimal("6")))
    db_session.commit()

    result = get_planned_dashboard(db_session, {school.id}, date(2026, 11, 9), date(2026, 11, 15))

    assert result["kpi"]["planned_teaching_hours"] == 6.0
    assert result["teachers"][0]["individual_norm_hours"] == 18.0
    assert "actual_hours" not in result["teachers"][0]
    assert "surveys" not in result


def test_work_type_is_archived_instead_of_deleted(db_session):
    actor = UserModel(name="Администратор", login="admin-service-test", password_hash="hash")
    db_session.add(actor)
    db_session.commit()
    item = create_work_type(db_session, WorkTypeCreate(code="mentoring", name="Наставничество", category_group="support"), actor.id)

    archive_work_type(db_session, item.id, actor.id)

    assert db_session.query(WorkTypeModel).filter_by(id=item.id).first() is not None
    assert list_work_types(db_session) == []
    assert list_work_types(db_session, include_archived=True)[0].is_active is False
