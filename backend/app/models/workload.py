"""Normalized teacher workload models required by the product specification."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid


class TeacherWorkloadNormModel(TimestampMixin, Base):
    """An individual weekly teaching norm valid for a date interval."""

    __tablename__ = "teacher_workload_norms"
    __table_args__ = (
        CheckConstraint("contract_teaching_hours_per_week >= 0", name="ck_norm_contract_nonnegative"),
        CheckConstraint("standard_teaching_hours_per_rate > 0", name="ck_norm_standard_positive"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_norm_period"),
        UniqueConstraint("teacher_id", "effective_from", name="uq_norm_teacher_from"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    contract_teaching_hours_per_week = Column(Numeric(6, 2), nullable=False)
    standard_teaching_hours_per_rate = Column(Numeric(6, 2), nullable=False)
    comment = Column(Text)
    plan_source = Column(String(255))
    source_import_id = Column(String(36), ForeignKey("import_batches.id", ondelete="SET NULL"))


class WorkloadPlanVersionModel(TimestampMixin, Base):
    """An immutable/versioned plan header for one school and validity period."""

    __tablename__ = "workload_plan_versions"
    __table_args__ = (
        CheckConstraint("effective_to >= effective_from", name="ck_plan_version_period"),
        UniqueConstraint("school_id", "version", name="uq_school_plan_version"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=False)
    source_import_id = Column(String(36), ForeignKey("import_batches.id", ondelete="SET NULL"))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    published_at = Column(DateTime(timezone=True))
    change_comment = Column(Text)

    items = relationship("PlannedWorkItemModel", back_populates="plan_version", cascade="all, delete-orphan")


class PlannedWorkItemModel(TimestampMixin, Base):
    """One planned work item, suitable for linking an actual entry to it."""

    __tablename__ = "planned_work_items"
    __table_args__ = (
        CheckConstraint("duration_hours > 0", name="ck_planned_work_duration_hours_positive"),
        UniqueConstraint(
            "plan_version_id",
            "teacher_id",
            "work_date",
            "work_type_id",
            "sequence_no",
            name="uq_planned_work_item_sequence",
        ),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    plan_version_id = Column(
        String(36),
        ForeignKey("workload_plan_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_type_id = Column(String(36), ForeignKey("work_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    day_type = Column(String(40), nullable=False)
    subject = Column(String(150))
    duration_hours = Column(Numeric(10, 4), nullable=False)
    sequence_no = Column(Integer, nullable=False, default=1)
    comment = Column(Text)

    plan_version = relationship("WorkloadPlanVersionModel", back_populates="items")
    work_type = relationship("WorkTypeModel")


class DailyWorkLogModel(TimestampMixin, Base):
    """Status and ownership of a teacher's daily time sheet."""

    __tablename__ = "daily_work_logs"
    __table_args__ = (
        CheckConstraint("status IN ('not_started', 'draft', 'completed')", name="ck_daily_work_log_status"),
        UniqueConstraint("teacher_id", "work_date", name="uq_daily_work_log_teacher_date"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    day_type = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="not_started")
    comment = Column(Text)
    completed_at = Column(DateTime(timezone=True))
    completed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    entries = relationship("ActualWorkEntryModel", back_populates="daily_log", cascade="all, delete-orphan")


class ActualWorkEntryModel(TimestampMixin, Base):
    """One actual time entry, optionally linked to one planned work item."""

    __tablename__ = "actual_work_entries"
    __table_args__ = (
        CheckConstraint(
            "duration_hours > 0 AND duration_hours <= 24",
            name="ck_actual_work_duration_hours_daily_bound",
        ),
        CheckConstraint("location IN ('school', 'home', 'other')", name="ck_actual_work_location"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    daily_log_id = Column(
        String(36),
        ForeignKey("daily_work_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planned_work_item_id = Column(
        String(36),
        ForeignKey("planned_work_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    work_type_id = Column(String(36), ForeignKey("work_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    duration_hours = Column(Numeric(10, 4), nullable=False)
    location = Column(String(20), nullable=False)
    comment = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    daily_log = relationship("DailyWorkLogModel", back_populates="entries")
    planned_work_item = relationship("PlannedWorkItemModel")
    work_type = relationship("WorkTypeModel")
