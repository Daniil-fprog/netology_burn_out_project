"""Configurable directory of planned and actual work types."""

from sqlalchemy import Boolean, Column, DateTime, String, Text

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid


class WorkTypeModel(TimestampMixin, Base):
    """A work category shared by plan items and actual work entries.

    Categories are archived rather than physically deleted so historical
    workload records always keep a valid reference.
    """

    __tablename__ = "work_types"
    id = Column(String(36), primary_key=True, default=new_uuid)
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    category_group = Column(String(120), nullable=False)
    requires_comment = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    description = Column(Text)
    archived_at = Column(DateTime(timezone=True))
