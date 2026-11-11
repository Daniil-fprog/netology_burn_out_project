"""Asynchronous report and research dataset export jobs."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid


class ExportJobModel(TimestampMixin, Base):
    """A generated export with scope, filters and a limited download lifetime."""

    __tablename__ = "export_jobs"
    __table_args__ = (
        CheckConstraint("format IN ('xlsx', 'csv', 'json')", name="ck_export_job_format"),
        CheckConstraint("download_count >= 0", name="ck_export_download_count"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="RESTRICT"), index=True)
    school_group_id = Column(String(36), ForeignKey("school_groups.id", ondelete="RESTRICT"), index=True)
    report_type = Column(String(50), nullable=False)
    format = Column(String(20), nullable=False)
    filters_jsonb = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="pending")
    row_count = Column(Integer)
    stored_file_key = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    downloaded_at = Column(DateTime(timezone=True))
    download_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text)
