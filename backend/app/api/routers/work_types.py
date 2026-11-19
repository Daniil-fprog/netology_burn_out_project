"""Work-type directory endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.access import user_role_codes
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.user import UserModel
from app.schemas.work_type import WorkTypeCreate, WorkTypeOut, WorkTypeUpdate
from app.services.work_type_service import (
    archive_work_type,
    create_work_type,
    list_work_types,
    update_work_type,
)


router = APIRouter(tags=["Work types"])
WORK_TYPE_EDITOR_ROLES = {"system_admin"}


@router.get("/work-types", response_model=list[WorkTypeOut])
def list_work_type_directory(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    return list_work_types(db, include_archived=include_archived)


@router.post("/work-types", response_model=WorkTypeOut, status_code=201)
def create_work_type_endpoint(
    data: WorkTypeCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if user_role_codes(db, user.id).isdisjoint(WORK_TYPE_EDITOR_ROLES):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    return create_work_type(db, data, user.id)


@router.patch("/work-types/{work_type_id}", response_model=WorkTypeOut)
def update_work_type_endpoint(
    work_type_id: str,
    data: WorkTypeUpdate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if user_role_codes(db, user.id).isdisjoint(WORK_TYPE_EDITOR_ROLES):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
        
    return update_work_type(db, work_type_id, data, user.id)


@router.post("/work-types/{work_type_id}/archive", response_model=WorkTypeOut)
def archive_work_type_endpoint(
    work_type_id: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    if user_role_codes(db, user.id).isdisjoint(WORK_TYPE_EDITOR_ROLES):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return archive_work_type(db, work_type_id, user.id)
