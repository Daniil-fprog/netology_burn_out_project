"""Teacher directory and the optional link to a user account."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid


class TeacherModel(TimestampMixin, Base):
    """A teacher belonging to exactly one school record."""

    __tablename__ = "teachers"
    __table_args__ = (
        UniqueConstraint("school_id", "external_id", name="uq_teacher_school_external"),
        UniqueConstraint("user_id", name="uq_teacher_user"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(
        String(36),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_id = Column(String(80), nullable=False)
    full_name = Column(String(255))
    subject = Column(String(150), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    school = relationship("SchoolModel")
    user = relationship("UserModel")
