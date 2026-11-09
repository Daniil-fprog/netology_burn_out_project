"""Schools and school groups used to limit the organizational data scope."""

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid


class SchoolModel(TimestampMixin, Base):
    """A school whose teachers and workload records form one access scope."""

    __tablename__ = "schools"

    id = Column(String(36), primary_key=True, default=new_uuid)
    name = Column(String(255), nullable=False)
    external_code = Column(String(80), unique=True)


class SchoolGroupModel(TimestampMixin, Base):
    """A named group of schools assigned to a group head."""

    __tablename__ = "school_groups"

    id = Column(String(36), primary_key=True, default=new_uuid)
    name = Column(String(255), nullable=False)
    external_code = Column(String(80), unique=True)

    schools = relationship(
        "SchoolGroupSchoolModel",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class SchoolGroupSchoolModel(Base):
    """Membership of a school in a school group."""

    __tablename__ = "school_group_schools"
    __table_args__ = (
        UniqueConstraint("group_id", "school_id", name="uq_school_group_school"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    group_id = Column(
        String(36),
        ForeignKey("school_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    school_id = Column(
        String(36),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    group = relationship("SchoolGroupModel", back_populates="schools")
    school = relationship("SchoolModel")
