"""Configurable directory of planned and actual work types."""

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Numeric, String, Text

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid


class WorkTypeModel(TimestampMixin, Base):
    """A work category shared by plan items and actual work entries.

    Categories are archived rather than physically deleted so historical
    workload records always keep a valid reference.
    """

    __tablename__ = "work_types"
    __table_args__ = (
        CheckConstraint(
            "complexity_weight BETWEEN 0 AND 1",
            name="ck_work_type_complexity_weight",
        ),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    category_group = Column(String(120), nullable=False)
    complexity_weight = Column(Numeric(5, 4), nullable=False, default=0)
    requires_comment = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    description = Column(Text)
    archived_at = Column(DateTime(timezone=True))
