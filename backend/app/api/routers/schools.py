"""School directory and membership administration endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.access import assign_role, find_user_teacher_in_school, require_roles, require_school_access, user_role_codes
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.access import UserSchoolAccessModel
from app.models.audit import AuditEventModel
from app.models.organization import SchoolModel
from app.models.user import UserModel
from app.schemas.access import AccessCreate
from app.schemas.organization import SchoolCreate


router = APIRouter(tags=["Schools"])


@router.post("/schools", status_code=201)
def create_school(
    data: SchoolCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    require_roles(db, user.id, {"system_admin"})
    school = SchoolModel(name=data.name.strip(), external_code=data.external_code)
    db.add(school)
    db.flush()
    db.add(AuditEventModel(
        actor_id=user.id,
        action="create",
        entity_type="school",
        entity_id=school.id,
        school_id=school.id,
        changes={"name": school.name, "external_code": school.external_code},
    ))
    db.commit()
    db.refresh(school)
    return {"id": school.id, "name": school.name, "external_code": school.external_code}


@router.get("/schools")
def list_schools(
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """List schools explicitly available to the current user."""
    query = db.query(SchoolModel)
    if "system_admin" not in user_role_codes(db, user.id):
        query = query.join(
            UserSchoolAccessModel,
            UserSchoolAccessModel.school_id == SchoolModel.id,
        ).filter(UserSchoolAccessModel.user_id == user.id)
    rows = query.order_by(SchoolModel.name).all()
    return [
        {"id": item.id, "name": item.name, "external_code": item.external_code}
        for item in rows
    ]


@router.post("/schools/{school_id}/members", status_code=201)
def add_school_member(
    school_id: str,
    data: AccessCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Grant a user a role and membership in a school."""
    require_school_access(db, user.id, school_id, {"system_admin"})
    if not db.query(UserModel).filter_by(id=data.user_id).first():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if data.role == "teacher" and find_user_teacher_in_school(db, data.user_id, school_id) is None:
        raise HTTPException(status_code=422, detail="Сначала свяжите учётную запись с педагогом через teachers.user_id")
    if db.query(UserSchoolAccessModel).filter_by(user_id=data.user_id, school_id=school_id).first():
        raise HTTPException(status_code=409, detail="Пользователь уже добавлен в школу")

    values = data.model_dump(exclude={"role"})
    member = UserSchoolAccessModel(school_id=school_id, **values)
    db.add(member)
    assign_role(db, data.user_id, data.role)
    db.flush()
    db.add(AuditEventModel(
        actor_id=user.id,
        action="grant",
        entity_type="user_school_access",
        entity_id=member.id,
        school_id=school_id,
        changes={"user_id": data.user_id, "role": data.role.value},
    ))
    db.commit()
    db.refresh(member)
    return {"id": member.id, "user_id": member.user_id, "school_id": member.school_id, "role": data.role}
