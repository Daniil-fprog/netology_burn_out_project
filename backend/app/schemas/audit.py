"""Read schemas for immutable audit events."""

from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class AuditEventOut(ORMModel):
    id: str
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    school_id: str | None
    import_batch_id: str | None
    purpose: str | None
    changed_at: datetime
    changes: dict[str, Any]
