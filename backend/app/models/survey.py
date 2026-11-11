"""Versioned wellbeing surveys, consent, revisions and NLP results."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.base import TimestampMixin, new_uuid, utcnow


class SurveyTemplateModel(TimestampMixin, Base):
    """An immutable version of a daily, weekly or monthly survey."""

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
    """A stable question identifier within a survey template version."""

    __tablename__ = "survey_questions"
    __table_args__ = (
        UniqueConstraint("template_id", "code", name="uq_question_template_code"),
        UniqueConstraint(
            "template_id", "position", name="uq_question_template_position"
        ),
    )
    id = Column(String(36), primary_key=True, default=new_uuid)
    template_id = Column(
        String(36),
        ForeignKey("survey_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code = Column(String(100), nullable=False)
    title = Column(Text, nullable=False)
    type = Column(String(30), nullable=False)
    position = Column(SmallInteger, nullable=False)
    required = Column(Boolean, nullable=False)
    settings_jsonb = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class SurveyConsentModel(Base):
    """A teacher's revocable consent for a declared processing purpose."""

    __tablename__ = "survey_consents"
    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(
        String(36),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    teacher_id = Column(
        String(36),
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    policy_version = Column(String(50), nullable=False)
    purpose = Column(String(40), nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    withdrawn_at = Column(DateTime(timezone=True))
    method = Column(String(30), nullable=False)
    proof_reference = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class SurveyResponseModel(TimestampMixin, Base):
    """A draft, submitted or withdrawn response for one assessment period."""

    __tablename__ = "survey_responses"
    __table_args__ = (
        CheckConstraint("period_start <= period_end", name="ck_response_period"),
        UniqueConstraint(
            "teacher_id", "client_request_id", name="uq_response_client_request"
        ),
        Index("ix_response_teacher_period", "teacher_id", "period_start", "period_end"),
        Index(
            "uq_survey_active_response_period",
            "teacher_id",
            "cadence",
            "period_start",
            "period_end",
            unique=True,
            sqlite_where=text("status IN ('draft', 'submitted')"),
            postgresql_where=text("status IN ('draft', 'submitted')"),
        ),
    )
    id = Column(String(36), primary_key=True, default=new_uuid)
    school_id = Column(
        String(36),
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    teacher_id = Column(
        String(36),
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    template_id = Column(
        String(36),
        ForeignKey("survey_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cadence = Column(String(20), nullable=False)
    assessment_date = Column(Date, nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    comment_reference_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)
    source = Column(String(30), nullable=False)
    consent_record_id = Column(
        String(36), ForeignKey("survey_consents.id", ondelete="RESTRICT")
    )
    submitted_at = Column(DateTime(timezone=True))
    client_request_id = Column(String(36))
    lock_version = Column(Integer, nullable=False, default=1)
    template = relationship("SurveyTemplateModel")
    answers = relationship(
        "SurveyAnswerModel", cascade="all, delete-orphan", lazy="selectin"
    )


class SurveyAnswerModel(TimestampMixin, Base):
    """One typed answer; long-text answers remain separately addressable."""

    __tablename__ = "survey_answers"
    __table_args__ = (
        UniqueConstraint("response_id", "question_id", name="uq_response_question"),
    )
    id = Column(String(36), primary_key=True, default=new_uuid)
    response_id = Column(
        String(36),
        ForeignKey("survey_responses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    question_id = Column(
        String(36),
        ForeignKey("survey_questions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    value_jsonb = Column(JSON, nullable=False)
    question = relationship("SurveyQuestionModel")


class SurveyResponseRevisionModel(Base):
    """An immutable snapshot retained when a submitted response changes."""

    __tablename__ = "survey_response_revisions"
    __table_args__ = (
        UniqueConstraint("response_id", "revision_no", name="uq_response_revision"),
    )
    id = Column(String(36), primary_key=True, default=new_uuid)
    response_id = Column(
        String(36),
        ForeignKey("survey_responses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision_no = Column(Integer, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    reason = Column(Text)
    previous_answers_jsonb = Column(JSON, nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    change_type = Column(String(20), nullable=False)


class SurveyNLPAnalysisModel(Base):
    """A non-blocking NLP processing job and its versioned result."""

    __tablename__ = "survey_nlp_analyses"
    id = Column(String(36), primary_key=True, default=new_uuid)
    response_id = Column(
        String(36),
        ForeignKey("survey_responses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    answer_id = Column(
        String(36), ForeignKey("survey_answers.id", ondelete="RESTRICT"), nullable=False
    )
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
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
