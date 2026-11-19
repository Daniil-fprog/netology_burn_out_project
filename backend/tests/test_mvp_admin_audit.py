"""RBAC and audit coverage for MVP 1 administrative operations."""

from app.models import (
    AuditEventModel,
    RoleModel,
    SchoolModel,
    SurveyConsentModel,
    TeacherModel,
    UserRoleModel,
    UserSchoolAccessModel,
)


def assign_role(db, user_id: int, code: str) -> None:
    role = RoleModel(code=code, name=code)
    db.add(role)
    db.flush()
    db.add(UserRoleModel(user_id=user_id, role_id=role.id))
    db.commit()


def test_system_admin_has_global_school_access_and_actions_are_audited(
    client,
    db_session,
    test_user,
    other_user,
    auth_headers,
):
    assign_role(db_session, test_user.id, "system_admin")
    db_session.add(RoleModel(code="teacher", name="teacher"))
    db_session.commit()

    school_response = client.post(
        "/api/v1/schools",
        headers=auth_headers,
        json={"name": "Школа № 1", "external_code": "school-1"},
    )
    assert school_response.status_code == 201
    school_id = school_response.json()["id"]

    schools_response = client.get("/api/v1/schools", headers=auth_headers)
    assert schools_response.status_code == 200
    assert [item["id"] for item in schools_response.json()] == [school_id]

    # No user_school_access row is required for a global system administrator.
    assert db_session.query(UserSchoolAccessModel).filter_by(
        user_id=test_user.id,
        school_id=school_id,
    ).first() is None

    teacher_response = client.post(
        f"/api/v1/schools/{school_id}/teachers",
        headers=auth_headers,
        json={
            "user_id": other_user.id,
            "external_id": "teacher-1",
            "full_name": "Иванова Анна",
            "subject": "Математика",
        },
    )
    assert teacher_response.status_code == 201

    duplicate_teacher_response = client.post(
        f"/api/v1/schools/{school_id}/teachers",
        headers=auth_headers,
        json={
            "user_id": other_user.id,
            "external_id": "teacher-duplicate",
            "full_name": "Иванова Анна",
            "subject": "Математика",
        },
    )
    assert duplicate_teacher_response.status_code == 409
    assert duplicate_teacher_response.json() == {
        "detail": "У пользователя уже есть профиль преподавателя"
    }

    access_response = client.post(
        f"/api/v1/schools/{school_id}/members",
        headers=auth_headers,
        json={"user_id": other_user.id, "role": "teacher"},
    )
    assert access_response.status_code == 201

    events = db_session.query(AuditEventModel).order_by(AuditEventModel.changed_at).all()
    assert [(event.action, event.entity_type) for event in events] == [
        ("create", "school"),
        ("create", "teacher"),
        ("grant", "user_school_access"),
    ]
    assert all(event.actor_id == test_user.id for event in events)
    assert all(event.school_id == school_id for event in events)


def test_regular_user_cannot_create_school(client, auth_headers):
    response = client.post(
        "/api/v1/schools",
        headers=auth_headers,
        json={"name": "Запрещённая школа"},
    )

    assert response.status_code == 403


def test_consent_withdrawal_is_audited(
    client,
    db_session,
    test_user,
    auth_headers,
):
    assign_role(db_session, test_user.id, "teacher")
    school = SchoolModel(name="Школа № 2")
    db_session.add(school)
    db_session.flush()
    db_session.add(UserSchoolAccessModel(user_id=test_user.id, school_id=school.id))
    teacher = TeacherModel(
        school_id=school.id,
        user_id=test_user.id,
        external_id="teacher-self",
        full_name=test_user.name,
        subject="Русский язык",
    )
    db_session.add(teacher)
    db_session.flush()
    consent = SurveyConsentModel(
        school_id=school.id,
        teacher_id=teacher.id,
        purpose="survey_storage",
        policy_version="1.0",
        method="web",
    )
    db_session.add(consent)
    db_session.commit()

    response = client.post(
        f"/api/v1/schools/{school.id}/survey-consents/{consent.id}/withdraw",
        headers=auth_headers,
    )

    assert response.status_code == 200
    event = db_session.query(AuditEventModel).filter_by(
        action="withdraw",
        entity_type="survey_consent",
        entity_id=consent.id,
    ).one()
    assert event.actor_id == test_user.id
    assert event.school_id == school.id
    assert event.purpose == "survey_storage"
