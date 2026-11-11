"""Import batches and original-file metadata."""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid


class ImportBatchModel(TimestampMixin, Base):
    """A validated workload import and its row-level result summary."""

    __tablename__ = "import_batches"
    __table_args__ = (UniqueConstraint("school_id", "sha256", name="uq_import_school_sha256"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_file_key = Column(Text)
    sha256 = Column(String(64), nullable=False)
    template_version = Column(String(20), nullable=False, default="1.0")
    status = Column(String(20), nullable=False)
    mode = Column(String(20), nullable=False)
    effective_from = Column(Date, nullable=False)
    rows_total = Column(Integer, nullable=False, default=0)
    rows_created = Column(Integer, nullable=False, default=0)
    rows_updated = Column(Integer, nullable=False, default=0)
    rows_skipped = Column(Integer, nullable=False, default=0)
    validation_report = Column(JSON, nullable=False, default=dict)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    imported_at = Column(DateTime(timezone=True))
