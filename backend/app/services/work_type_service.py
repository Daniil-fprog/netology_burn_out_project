"""Manage the work-type directory without physical deletion."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit import AuditEventModel
from app.models.base import utcnow
from app.models.work_type import WorkTypeModel
from app.schemas.work_type import WorkTypeCreate, WorkTypeUpdate


def list_work_types(db: Session, *, include_archived: bool = False) -> list[WorkTypeModel]:
    query = db.query(WorkTypeModel)
    if not include_archived:
        query = query.filter(WorkTypeModel.is_active.is_(True))
    return query.order_by(WorkTypeModel.category_group, WorkTypeModel.name).all()


def create_work_type(db: Session, data: WorkTypeCreate, actor_id: int) -> WorkTypeModel:
    if db.query(WorkTypeModel).filter_by(code=data.code).first():
        raise HTTPException(status_code=409, detail="Тип работы с таким кодом уже существует")
    item = WorkTypeModel(**data.model_dump())
    db.add(item)
    db.flush()
    db.add(AuditEventModel(actor_id=actor_id, action="create", entity_type="work_type", entity_id=item.id, changes=data.model_dump(mode="json")))
    db.commit()
    db.refresh(item)
    return item


def update_work_type(db: Session, work_type_id: str, data: WorkTypeUpdate, actor_id: int) -> WorkTypeModel:
    item = db.query(WorkTypeModel).filter_by(id=work_type_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Тип работы не найден")
    changes = data.model_dump(exclude_unset=True)
    before = {field: str(getattr(item, field)) for field in changes}
    for field, value in changes.items():
        setattr(item, field, value)
    db.add(AuditEventModel(actor_id=actor_id, action="update", entity_type="work_type", entity_id=item.id, changes={"before": before, "after": data.model_dump(exclude_unset=True, mode="json")}))
    db.commit()
    db.refresh(item)
    return item


def archive_work_type(db: Session, work_type_id: str, actor_id: int) -> WorkTypeModel:
    item = db.query(WorkTypeModel).filter_by(id=work_type_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Тип работы не найден")
    item.is_active = False
    item.archived_at = utcnow()
    db.add(AuditEventModel(actor_id=actor_id, action="archive", entity_type="work_type", entity_id=item.id, changes={"is_active": False}))
    db.commit()
    db.refresh(item)
    return item
