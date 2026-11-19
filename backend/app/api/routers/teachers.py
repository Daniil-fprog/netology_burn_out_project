"""Teacher profiles within schools."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.access import (
    PLAN_MANAGER_ROLES,
    get_teacher_id_filter,
    require_school_access,
)
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.audit import AuditEventModel
from app.models.teacher import TeacherModel
from app.models.user import UserModel
from app.schemas.teacher import TeacherCreate
from app.utils.pagination import paginate


router = APIRouter(tags=["Teachers"])


@router.post("/schools/{school_id}/teachers", status_code=201)
def create_teacher(
    school_id: str,
    data: TeacherCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    require_school_access(db, user.id, school_id, {"system_admin"})

    if (
        db.query(TeacherModel)
        .filter_by(school_id=school_id, external_id=data.external_id)
        .first()
    ):
        raise HTTPException(status_code=409, detail="Такой external_id уже есть")

    if (
        data.user_id is not None
        and not db.query(UserModel).filter_by(id=data.user_id).first()
    ):
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if (
        data.user_id is not None
        and db.query(TeacherModel).filter_by(user_id=data.user_id).first()
    ):
        raise HTTPException(
            status_code=409, detail="У пользователя уже есть профиль преподавателя"
        )

    teacher = TeacherModel(school_id=school_id, **data.model_dump())

    db.add(teacher)
    db.flush()

    db.add(
        AuditEventModel(
            actor_id=user.id,
            action="create",
            entity_type="teacher",
            entity_id=teacher.id,
            school_id=school_id,
            changes={
                "user_id": teacher.user_id,
                "external_id": teacher.external_id,
                "full_name": teacher.full_name,
                "subject": teacher.subject,
            },
        )
    )

    db.commit()
    db.refresh(teacher)

    return {
        "id": teacher.id,
        "external_id": teacher.external_id,
        "subject": teacher.subject,
        "is_active": teacher.is_active,
    }


@router.get("/schools/{school_id}/teachers")
def list_teachers(
    school_id: str,
    subject: str | None = None,
    page_no: int = Query(1, alias="page", ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES | {"teacher"})

    query = db.query(TeacherModel).filter_by(school_id=school_id)
    own_teacher_id = get_teacher_id_filter(db, user.id, school_id)

    if own_teacher_id:
        query = query.filter_by(id=own_teacher_id)

    if subject:
        query = query.filter(TeacherModel.subject == subject)

    teachers = [
        {
            "id": teacher.id,
            "user_id": teacher.user_id,
            "external_id": teacher.external_id,
            "full_name": teacher.full_name,
            "subject": teacher.subject,
            "is_active": teacher.is_active,
        }
        for teacher in query.order_by(TeacherModel.external_id).all()
    ]

    return paginate(teachers, page_no, page_size)
