from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.teacher_domain import TeacherModel, UserSchoolAccessModel


MANAGER_ROLES = {"admin", "analyst", "survey_manager", "researcher", "privacy_officer"}


def require_school_access(db: Session, user_id: int, school_id: str, roles: set[str] | None = None) -> UserSchoolAccessModel:
    access = db.query(UserSchoolAccessModel).filter_by(user_id=user_id, school_id=school_id).first()
    if access is None or (roles is not None and access.role not in roles):
        raise HTTPException(status_code=403, detail="Нет доступа к этой школе")
    return access


def require_teacher_scope(access: UserSchoolAccessModel, teacher_id: str) -> None:
    if access.role == "teacher" and access.teacher_id != teacher_id:
        raise HTTPException(status_code=404, detail="Педагог не найден")


def get_teacher_in_school(db: Session, school_id: str, teacher_id: str) -> TeacherModel:
    teacher = db.query(TeacherModel).filter_by(id=teacher_id, school_id=school_id).first()
    if teacher is None:
        raise HTTPException(status_code=404, detail="Педагог не найден")
    return teacher
