"""Security and data-change audit events."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String

from app.db.database import Base
from app.models.base import new_uuid, utcnow


class AuditEventModel(Base):
    """An immutable record of an access, change, import or export event."""

    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=new_uuid)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(30), nullable=False)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(String(36))
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="SET NULL"), index=True)
    import_batch_id = Column(String(36), ForeignKey("import_batches.id", ondelete="SET NULL"))
    purpose = Column(String(80))
    changed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    changes = Column(JSON, nullable=False, default=dict)
