from collections.abc import Set

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enum import RoleCode
from app.models.access import UserSchoolAccessModel
from app.models.role import RoleModel, UserRoleModel
from app.models.teacher import TeacherModel


MANAGER_ROLES = frozenset(
    {
        RoleCode.DIRECTOR,
        RoleCode.HEAD,
        RoleCode.GROUP_HEAD,
        RoleCode.SYSTEM_ADMIN,
    }
)
PLAN_MANAGER_ROLES = frozenset(
    {
        RoleCode.DIRECTOR,
        RoleCode.HEAD,
        RoleCode.GROUP_HEAD,
    }
)
FACT_ROLES = frozenset(
    {
        RoleCode.TEACHER,
        RoleCode.HEAD,
        RoleCode.GROUP_HEAD,
    }
)
SURVEY_ROLES = frozenset(
    {
        RoleCode.TEACHER,
        RoleCode.HEAD,
        RoleCode.GROUP_HEAD,
    }
)


def user_role_codes(db: Session, user_id: int) -> set[str]:
    """Return role codes assigned to an account."""
    rows = (
        db.query(RoleModel.code)
        .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
        .filter(UserRoleModel.user_id == user_id)
        .all()
    )
    return {code for (code,) in rows}


def assign_role(db: Session, user_id: int, role_code: RoleCode | str) -> None:
    """Add a role to the current transaction, without committing it."""
    code = role_code.value if isinstance(role_code, RoleCode) else role_code
    role = db.query(RoleModel).filter_by(code=code).first()
    if role is None:
        raise HTTPException(status_code=422, detail="Неизвестная роль")
    exists = db.query(UserRoleModel).filter_by(user_id=user_id, role_id=role.id).first()
    if exists is None:
        db.add(UserRoleModel(user_id=user_id, role_id=role.id))


def find_user_teacher_in_school(db: Session, user_id: int, school_id: str) -> TeacherModel | None:
    """Find the teacher profile linked to a user in a specific school."""
    return db.query(TeacherModel).filter_by(user_id=user_id, school_id=school_id).first()


def require_own_teacher(db: Session, user_id: int, school_id: str) -> TeacherModel:
    """Resolve a teacher profile for self-service operations only."""
    if RoleCode.TEACHER not in user_role_codes(db, user_id):
        raise HTTPException(status_code=403, detail="Действие доступно только преподавателю")
    teacher = find_user_teacher_in_school(db, user_id, school_id)
    if teacher is None:
        raise HTTPException(status_code=403, detail="Учётная запись не связана с педагогом")
    return teacher


def get_teacher_id_filter(db: Session, user_id: int, school_id: str) -> str | None:
    """Return the teacher ID that must be applied to a data query, if any."""
    roles = user_role_codes(db, user_id)
    if not roles.isdisjoint(MANAGER_ROLES):
        return None
    if RoleCode.TEACHER not in roles:
        return None
    teacher = find_user_teacher_in_school(db, user_id, school_id)
    if teacher is None:
        raise HTTPException(status_code=403, detail="Учётная запись не связана с педагогом")
    return teacher.id


def require_school_access(
    db: Session,
    user_id: int,
    school_id: str,
    roles: Set[RoleCode | str] | None = None,
) -> UserSchoolAccessModel:
    access = db.query(UserSchoolAccessModel).filter_by(user_id=user_id, school_id=school_id).first()
    if access is None or (roles is not None and user_role_codes(db, user_id).isdisjoint(roles)):
        raise HTTPException(status_code=403, detail="Нет доступа к этой школе")
    return access


def require_teacher_access(db: Session, user_id: int, school_id: str, teacher_id: str) -> None:
    """Require permission to access a specific teacher in a school."""
    roles = user_role_codes(db, user_id)
    if not roles.isdisjoint(MANAGER_ROLES):
        return
    teacher = find_user_teacher_in_school(db, user_id, school_id)
    if RoleCode.TEACHER not in roles or teacher is None or teacher.id != teacher_id:
        raise HTTPException(status_code=404, detail="Педагог не найден")


def get_teacher_in_school(db: Session, school_id: str, teacher_id: str) -> TeacherModel:
    teacher = db.query(TeacherModel).filter_by(id=teacher_id, school_id=school_id).first()
    if teacher is None:
        raise HTTPException(status_code=404, detail="Педагог не найден")
    return teacher
