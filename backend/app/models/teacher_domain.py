"""Relational model for teacher workload and wellbeing surveys.

UUIDs are stored as 36-character strings so the same model works with the
project's SQLite development database and PostgreSQL in production.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, SmallInteger, String, Text, UniqueConstraint, Index, text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def new_uuid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SchoolModel(TimestampMixin, Base):
    __tablename__ = "schools"
    id = Column(String(36), primary_key=True, default=new_uuid)
    name = Column(String(255), nullable=False)
    external_code = Column(String(80), unique=True)


class TeacherModel(TimestampMixin, Base):
    __tablename__ = "teachers"
    __table_args__ = (UniqueConstraint("school_id", "external_id", name="uq_teacher_school_external"),)
    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    external_id = Column(String(80), nullable=False)
    full_name = Column(String(255))
    subject = Column(String(150), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    school = relationship("SchoolModel")


class UserSchoolAccessModel(Base):
    __tablename__ = "user_school_access"
    __table_args__ = (UniqueConstraint("user_id", "school_id", name="uq_user_school_access"),)
    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    role = Column(String(30), nullable=False, default="teacher")
    can_read_comments = Column(Boolean, nullable=False, default=False)
    can_export_research = Column(Boolean, nullable=False, default=False)


class ImportBatchModel(TimestampMixin, Base):
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


class TeacherWorkloadNormModel(TimestampMixin, Base):
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


PLAN_FIELDS = (
    "teaching_block", "preparation", "grading", "documentation",
    "parent_communication", "class_management", "meetings_methodology", "other",
)


class DailyWorkloadPlanModel(TimestampMixin, Base):
    __tablename__ = "daily_workload_plans"
    __table_args__ = (UniqueConstraint("teacher_id", "work_date", name="uq_plan_teacher_date"),)
    id = Column(String(36), primary_key=True, default=new_uuid)
    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    day_type = Column(String(40), nullable=False)
    planned_lessons_teaching_hours = Column(Numeric(6, 2))
    planned_substitutions_teaching_hours = Column(Numeric(6, 2))
    planned_teaching_block_hours = Column(Numeric(7, 2))
    planned_preparation_hours = Column(Numeric(7, 2))
    planned_grading_hours = Column(Numeric(7, 2))
    planned_documentation_hours = Column(Numeric(7, 2))
    planned_parent_communication_hours = Column(Numeric(7, 2))
    planned_class_management_hours = Column(Numeric(7, 2))
    planned_meetings_methodology_hours = Column(Numeric(7, 2))
    planned_other_hours = Column(Numeric(7, 2))
    source_import_id = Column(String(36), ForeignKey("import_batches.id", ondelete="SET NULL"))


class DailyWorkloadActualModel(TimestampMixin, Base):
    __tablename__ = "daily_workload_actuals"
    __table_args__ = (
        UniqueConstraint("teacher_id", "work_date", name="uq_actual_teacher_date"),
        CheckConstraint("fatigue_score IS NULL OR fatigue_score BETWEEN 1 AND 5", name="ck_actual_fatigue"),
        CheckConstraint("stress_score IS NULL OR stress_score BETWEEN 1 AND 5", name="ck_actual_stress"),
    )
    id = Column(String(36), primary_key=True, default=new_uuid)
    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    day_type = Column(String(40), nullable=False)
    actual_lessons_teaching_hours = Column(Numeric(6, 2))
    actual_substitutions_teaching_hours = Column(Numeric(6, 2))
    actual_teaching_block_hours = Column(Numeric(7, 2))
    actual_preparation_hours = Column(Numeric(7, 2))
    actual_grading_hours = Column(Numeric(7, 2))
    actual_documentation_hours = Column(Numeric(7, 2))
    actual_parent_communication_hours = Column(Numeric(7, 2))
    actual_class_management_hours = Column(Numeric(7, 2))
    actual_meetings_methodology_hours = Column(Numeric(7, 2))
    actual_other_hours = Column(Numeric(7, 2))
    at_school_hours = Column(Numeric(7, 2))
    at_home_hours = Column(Numeric(7, 2))
    fatigue_score = Column(SmallInteger)
    stress_score = Column(SmallInteger)
    comment = Column(Text)
    source_import_id = Column(String(36), ForeignKey("import_batches.id", ondelete="SET NULL"))


class AuditEventModel(Base):
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


class SurveyTemplateModel(TimestampMixin, Base):
    __tablename__ = "survey_templates"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_survey_template_version"),
        Index("ix_survey_template_current", "code", "is_current", unique=True),
    )
    id = Column(String(36), primary_key=True, default=new_uuid)
    code = Column(String(80), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    title = Column(String(250), nullable=False)
    cadence = Column(String(20), nullable=False)
    locale = Column(String(12), nullable=False, default="ru-RU")
    definition_jsonb = Column(JSON, nullable=False)
    content_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    is_current = Column(Boolean, nullable=True)
    published_at = Column(DateTime(timezone=True))


class SurveyQuestionModel(Base):
    __tablename__ = "survey_questions"
    __table_args__ = (
        UniqueConstraint("template_id", "code", name="uq_question_template_code"),
        UniqueConstraint("template_id", "position", name="uq_question_template_position"),
    )
    id = Column(String(36), primary_key=True, default=new_uuid)
    template_id = Column(String(36), ForeignKey("survey_templates.id", ondelete="RESTRICT"), nullable=False, index=True)
    code = Column(String(100), nullable=False)
    title = Column(Text, nullable=False)
    type = Column(String(30), nullable=False)
    position = Column(SmallInteger, nullable=False)
    required = Column(Boolean, nullable=False)
    settings_jsonb = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class SurveyConsentModel(Base):
    __tablename__ = "survey_consents"
    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True)
    policy_version = Column(String(50), nullable=False)
    purpose = Column(String(40), nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    withdrawn_at = Column(DateTime(timezone=True))
    method = Column(String(30), nullable=False)
    proof_reference = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class SurveyResponseModel(TimestampMixin, Base):
    __tablename__ = "survey_responses"
    __table_args__ = (
        CheckConstraint("period_start <= period_end", name="ck_response_period"),
        UniqueConstraint("teacher_id", "client_request_id", name="uq_response_client_request"),
        Index("ix_response_teacher_period", "teacher_id", "period_start", "period_end"),
        Index(
            "uq_survey_active_response_period", "teacher_id", "cadence", "period_start", "period_end",
            unique=True,
            sqlite_where=text("status IN ('draft', 'submitted')"),
            postgresql_where=text("status IN ('draft', 'submitted')"),
        ),
    )
    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False, index=True)
    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True)
    template_id = Column(String(36), ForeignKey("survey_templates.id", ondelete="RESTRICT"), nullable=False)
    cadence = Column(String(20), nullable=False)
    assessment_date = Column(Date, nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    comment_reference_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)
    source = Column(String(30), nullable=False)
    consent_record_id = Column(String(36), ForeignKey("survey_consents.id", ondelete="RESTRICT"))
    submitted_at = Column(DateTime(timezone=True))
    client_request_id = Column(String(36))
    lock_version = Column(Integer, nullable=False, default=1)
    template = relationship("SurveyTemplateModel")
    answers = relationship("SurveyAnswerModel", cascade="all, delete-orphan", lazy="selectin")


class SurveyAnswerModel(TimestampMixin, Base):
    __tablename__ = "survey_answers"
    __table_args__ = (UniqueConstraint("response_id", "question_id", name="uq_response_question"),)
    id = Column(String(36), primary_key=True, default=new_uuid)
    response_id = Column(String(36), ForeignKey("survey_responses.id", ondelete="RESTRICT"), nullable=False, index=True)
    question_id = Column(String(36), ForeignKey("survey_questions.id", ondelete="RESTRICT"), nullable=False, index=True)
    value_jsonb = Column(JSON, nullable=False)
    question = relationship("SurveyQuestionModel")


class SurveyResponseRevisionModel(Base):
    __tablename__ = "survey_response_revisions"
    __table_args__ = (UniqueConstraint("response_id", "revision_no", name="uq_response_revision"),)
    id = Column(String(36), primary_key=True, default=new_uuid)
    response_id = Column(String(36), ForeignKey("survey_responses.id", ondelete="RESTRICT"), nullable=False)
    revision_no = Column(Integer, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    reason = Column(Text)
    previous_answers_jsonb = Column(JSON, nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    change_type = Column(String(20), nullable=False)


class SurveyNLPAnalysisModel(Base):
    __tablename__ = "survey_nlp_analyses"
    id = Column(String(36), primary_key=True, default=new_uuid)
    response_id = Column(String(36), ForeignKey("survey_responses.id", ondelete="RESTRICT"), nullable=False, index=True)
    answer_id = Column(String(36), ForeignKey("survey_answers.id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    model_name = Column(String(100))
    model_version = Column(String(50))
    preprocessing_version = Column(String(50))
    schema_version = Column(String(50))
    result_jsonb = Column(JSON)
    error_code = Column(String(80))
    attempt_count = Column(Integer, nullable=False, default=0)
    stale = Column(Boolean, nullable=False, default=False)
    analyzed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SurveyExportJobModel(TimestampMixin, Base):
    __tablename__ = "survey_export_jobs"
    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False)
    requested_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    format = Column(String(20), nullable=False)
    report = Column(String(30), nullable=False)
    filters_jsonb = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="pending")
    row_count = Column(Integer)
    stored_file_key = Column(Text)
    expires_at = Column(DateTime(timezone=True))


class SurveyMLLabelModel(TimestampMixin, Base):
    __tablename__ = "survey_ml_labels"
    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(String(36), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False)
    teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False)
    label_definition_version = Column(String(50), nullable=False)
    assessment_date = Column(Date, nullable=False)
    value_jsonb = Column(JSON, nullable=False)
    source = Column(String(80), nullable=False)
