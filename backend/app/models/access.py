"""Organizational assignments used together with user roles."""

from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid


class UserSchoolAccessModel(TimestampMixin, Base):
    """Assign a user to a school."""

    __tablename__ = "user_school_access"
    __table_args__ = (UniqueConstraint("user_id", "school_id", name="uq_user_school_access"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)


class UserSchoolGroupAssignmentModel(TimestampMixin, Base):
    """Assign a group head to a school group."""

    __tablename__ = "user_school_group_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "school_group_id", name="uq_user_school_group_assignment"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    school_group_id = Column(
        String(36),
        ForeignKey("school_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
