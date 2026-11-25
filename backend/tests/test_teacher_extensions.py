from io import BytesIO
from decimal import Decimal
from types import SimpleNamespace

from openpyxl import Workbook

from app.models import (
    AuditEventModel,
    RoleModel,
    SchoolModel,
    TeacherModel,
    UserRoleModel,
    UserSchoolAccessModel,
    WorkTypeModel,
)
from app.models.survey import (
    SurveyQuestionModel,
    SurveyResponseModel,
    SurveyResponseRevisionModel,
    SurveyTemplateModel,
)
from app.services.survey_service import seed_surveys, validate_answers
from app.core.workload_import_contract import ACTUAL_HEADERS, NORM_HEADERS, PLAN_HEADERS
from app.services.workload_service import parse_workbook, total


def test_seed_is_idempotent_and_has_31_questions(db_session):
    assert seed_surveys(db_session)["created"] == 3
    assert seed_surveys(db_session)["created"] == 0
    assert db_session.query(SurveyTemplateModel).count() == 3
    assert db_session.query(SurveyQuestionModel).count() == 31


def test_workload_total_keeps_missingness():
    entries = [
        SimpleNamespace(duration_hours=Decimal("4.15")),
        SimpleNamespace(duration_hours=Decimal("1.06")),
        SimpleNamespace(duration_hours=Decimal("0.69")),
    ]
    assert total(entries) == Decimal("5.90")


def test_realistic_workbook_contract_is_parsed():
    wb = Workbook(); wb.remove(wb.active)
    for name, mapping in (("Учителя_нормы", NORM_HEADERS), ("План_дня", PLAN_HEADERS), ("Ежедневный_учет", ACTUAL_HEADERS)):
        ws = wb.create_sheet(name); ws.append([]); ws.append([]); ws.append([]); ws.append(list(mapping))
        if name == "Учителя_нормы": ws.append(["T001", "Математика", 24, 18, None, None])
        elif name == "План_дня": ws.append(["2026-10-19", "T001", "Учебный день", 5, 0, 1, .6, .4, .25, .35, .15, .2])
        else: ws.append(["2026-10-19", "T001", "Учебный день", 5, 0, 1.06, .69, .39, .25, .35, .15, .2, 5.29, 1.55, "ok"])
    output = BytesIO(); wb.save(output)
    parsed = parse_workbook(output.getvalue())
    assert parsed["errors"] == []
    assert (len(parsed["norms"]), len(parsed["plans"]), len(parsed["actuals"])) == (1, 1, 0)
    assert parsed["plans"][0]["planned_lessons_hours"] == Decimal("3.75")
    assert any("не импортируется" in warning["message"] for warning in parsed["warnings"])


def test_survey_response_approve_and_admin_deactivate(
    client, db_session, test_user, auth_headers
):
    role = RoleModel(code="teacher", name="teacher")
    school = SchoolModel(name="Школа с опросами")
    db_session.add_all([role, school])
    db_session.flush()
    db_session.add_all(
        [
            UserRoleModel(user_id=test_user.id, role_id=role.id),
            UserSchoolAccessModel(user_id=test_user.id, school_id=school.id),
        ]
    )
    teacher = TeacherModel(
        school_id=school.id,
        user_id=test_user.id,
        external_id="survey-teacher",
        full_name=test_user.name,
        subject="Математика",
    )
    db_session.add(teacher)
    db_session.commit()
    seed_surveys(db_session)

    template = db_session.query(SurveyTemplateModel).filter_by(
        code="daily_checkin", version="1.0.0"
    ).one()
    questions = (
        db_session.query(SurveyQuestionModel)
        .filter_by(template_id=template.id)
        .order_by(SurveyQuestionModel.position)
        .all()
    )
    answers = {}
    for question in questions:
        if question.type == "integer_scale":
            answers[question.code] = question.settings_jsonb.get("min", 1)
        elif question.type == "single_choice":
            answers[question.code] = question.settings_jsonb["options"][0]["value"]
        elif question.type == "long_text":
            minimum = question.settings_jsonb.get("min_length", 1)
            answers[question.code] = "Т" * max(minimum, 1)

    payload = {
        "survey_code": "daily_checkin",
        "survey_version": "1.0.0",
        "assessment_date": "2026-11-18",
        "period_start": "2026-11-18",
        "period_end": "2026-11-18",
        "comment_reference_date": "2026-11-18",
        "consent_given": True,
        "answers": {"fatigue_score": 3},
    }
    create_with_incomplete_answers = client.post(
        f"/api/v1/schools/{school.id}/survey-responses",
        headers=auth_headers,
        json=payload,
    )
    assert create_with_incomplete_answers.status_code == 422

    payload["answers"] = answers
    payload["consent_given"] = False
    create_without_consent = client.post(
        f"/api/v1/schools/{school.id}/survey-responses",
        headers=auth_headers,
        json=payload,
    )
    assert create_without_consent.status_code == 422

    payload["consent_given"] = True
    create_response = client.post(
        f"/api/v1/schools/{school.id}/survey-responses",
        headers=auth_headers,
        json=payload,
    )
    assert create_response.status_code == 201
    response_id = create_response.json()["id"]
    assert create_response.json()["status"] == "draft"
    assert create_response.json()["consent_given"] is True
    assert create_response.json()["consented_at"] is not None
    assert create_response.json()["approved_at"] is None
    assert create_response.json()["lock_version"] == 1
    original_updated_at = create_response.json()["updated_at"]

    corrected_answers = {**answers, "fatigue_score": 2}
    correction_response = client.post(
        f"/api/v1/schools/{school.id}/survey-responses/{response_id}/corrections",
        headers=auth_headers,
        json={
            "description": "Исправлена оценка усталости",
            "answers": {"fatigue_score": 2},
        },
    )
    assert correction_response.status_code == 200
    corrected = correction_response.json()
    assert corrected["answers"] == corrected_answers
    assert corrected["lock_version"] == 2
    assert corrected["updated_at"] != original_updated_at

    revision = db_session.query(SurveyResponseRevisionModel).filter_by(
        response_id=response_id
    ).one()
    assert revision.revision_no == 1
    assert revision.reason == "Исправлена оценка усталости"
    assert revision.previous_answers_jsonb == answers

    # Approve only changes the status; answers were saved atomically during creation.
    approve_response = client.post(
        f"/api/v1/schools/{school.id}/survey-responses/{response_id}/approve",
        headers=auth_headers,
        json={"status": "approved"},
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()
    assert approved["status"] == "approved"
    assert approved["consent_given"] is True
    assert approved["approved_at"] is not None
    assert approved["answers"] == corrected_answers

    forbidden_correction = client.post(
        f"/api/v1/schools/{school.id}/survey-responses/{response_id}/corrections",
        headers=auth_headers,
        json={
            "description": "Попытка изменить подтверждённый опрос",
            "answers": {"fatigue_score": 3},
        },
    )
    assert forbidden_correction.status_code == 409

    forbidden_deactivation = client.post(
        f"/api/v1/schools/{school.id}/survey-responses/{response_id}/approve",
        headers=auth_headers,
        json={"status": "deactivated"},
    )
    assert forbidden_deactivation.status_code == 403

    admin_role = RoleModel(code="system_admin", name="system_admin")
    db_session.add(admin_role)
    db_session.flush()
    db_session.add(UserRoleModel(user_id=test_user.id, role_id=admin_role.id))
    db_session.commit()

    deactivate_response = client.post(
        f"/api/v1/schools/{school.id}/survey-responses/{response_id}/approve",
        headers=auth_headers,
        json={"status": "deactivated"},
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["status"] == "deactivated"

    stored = db_session.query(SurveyResponseModel).filter_by(id=response_id).one()
    assert stored.status == "deactivated"
    audit = db_session.query(AuditEventModel).filter_by(
        entity_type="survey_response", entity_id=response_id, action="deactivate"
    ).one()
    assert audit.changes["status"] == "deactivated"


def test_daily_workload_returns_one_date_or_period_report(
    client, db_session, test_user, auth_headers
):
    role = RoleModel(code="teacher", name="teacher")
    school = SchoolModel(name="Школа с дневной нагрузкой")
    work_type = WorkTypeModel(
        code="lessons",
        name="Уроки",
        category_group="teaching",
        complexity_weight=0.5,
    )
    db_session.add_all([role, school, work_type])
    db_session.flush()
    db_session.add_all(
        [
            UserRoleModel(user_id=test_user.id, role_id=role.id),
            UserSchoolAccessModel(user_id=test_user.id, school_id=school.id),
        ]
    )
    teacher = TeacherModel(
        school_id=school.id,
        user_id=test_user.id,
        external_id="workload-teacher",
        full_name=test_user.name,
        subject="Математика",
    )
    db_session.add(teacher)
    db_session.commit()

    create_response = client.post(
        f"/api/v1/schools/{school.id}/workload/daily",
        headers=auth_headers,
        json={
            "teacher_id": teacher.id,
            "work_date": "2026-11-21",
            "day_type": "Учебный день",
            "status": "completed",
            "entries": [
                {
                    "duration_hours": 3,
                    "work_type_id": work_type.id,
                    "location": "school",
                }
            ],
        },
    )
    assert create_response.status_code == 201

    one_day = client.get(
        f"/api/v1/schools/{school.id}/workload/daily",
        headers=auth_headers,
        params={"date_from": "2026-11-21"},
    )
    assert one_day.status_code == 200
    report = one_day.json()
    assert report["date_from"] == "2026-11-21"
    assert report["date_to"] == "2026-11-21"
    assert report["summary"] == {
        "actual_hours": 3.0,
        "weekend_hours": 3.0,
        "observed_days": 1,
        "completed_days": 1,
    }
    assert len(report["items"]) == 1

    reversed_period = client.get(
        f"/api/v1/schools/{school.id}/workload/daily",
        headers=auth_headers,
        params={"date_from": "2026-11-22", "date_to": "2026-11-21"},
    )
    assert reversed_period.status_code == 422
