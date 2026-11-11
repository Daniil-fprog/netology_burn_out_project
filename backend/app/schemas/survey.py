"""Schemas for versioned surveys, answers, consent and NLP processing."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.core.enum import SurveyCadence, SurveyResponseStatus
from app.schemas.common import ORMModel


class SurveyConsentRequest(BaseModel):
    policy_version: str = Field(min_length=1, max_length=50)
    purpose: str = Field(pattern="^(survey_storage|research_processing|external_nlp)$")
    method: str = Field(min_length=1, max_length=30)
    proof_reference: str | None = None


class SurveyResponseRequest(BaseModel):
    survey_code: str
    survey_version: str | None = None
    assessment_date: date
    period_start: date
    period_end: date
    comment_reference_date: date | None = None
    source: str = Field(default="web_form", pattern="^(web_form|mobile|api|legacy_excel)$")
    status: str = Field(default="draft", pattern="^(draft|submitted)$")
    client_request_id: str | None = None
    consent_record_id: str | None = None
    answers: dict[str, Any] = Field(default_factory=dict)


class SurveyDraftPatch(BaseModel):
    answers: dict[str, Any]


class SurveyCorrectionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    answers: dict[str, Any]


class SurveyQuestionDefinition(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1)
    type: str = Field(pattern="^(integer_scale|single_choice|long_text)$")
    position: int = Field(ge=1)
    required: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)


class SurveyTemplateCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=250)
    cadence: SurveyCadence
    locale: str = Field(default="ru-RU", max_length=12)
    questions: list[SurveyQuestionDefinition] = Field(min_length=1)


class SurveyTemplateOut(ORMModel):
    id: str
    code: str
    version: str
    title: str
    cadence: SurveyCadence
    locale: str
    definition_jsonb: dict[str, Any]
    content_hash: str
    status: str
    is_current: bool | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SurveyQuestionOut(ORMModel):
    id: str
    template_id: str
    code: str
    title: str
    type: str
    position: int
    required: bool
    settings_jsonb: dict[str, Any]
    created_at: datetime


class SurveyConsentCreate(BaseModel):
    school_id: str
    teacher_id: str
    policy_version: str = Field(min_length=1, max_length=50)
    purpose: str = Field(min_length=1, max_length=40)
    method: str = Field(min_length=1, max_length=30)
    proof_reference: str | None = None


class SurveyConsentOut(SurveyConsentCreate, ORMModel):
    id: str
    granted_at: datetime
    withdrawn_at: datetime | None
    created_at: datetime


class SurveyResponseCreate(BaseModel):
    school_id: str
    teacher_id: str
    template_id: str
    cadence: SurveyCadence
    assessment_date: date
    period_start: date
    period_end: date
    comment_reference_date: date
    status: SurveyResponseStatus = SurveyResponseStatus.DRAFT
    source: str = Field(default="web", max_length=30)
    consent_record_id: str | None = None
    client_request_id: str | None = None
    answers: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must not be earlier than period_start")
        if not self.period_start <= self.assessment_date <= self.period_end:
            raise ValueError("assessment_date must belong to the response period")
        if self.comment_reference_date != self.assessment_date:
            raise ValueError("comment_reference_date must equal assessment_date")
        return self


class SurveyAnswerOut(ORMModel):
    id: str
    response_id: str
    question_id: str
    value_jsonb: Any
    created_at: datetime
    updated_at: datetime


class SurveyResponseOut(ORMModel):
    id: str
    school_id: str
    teacher_id: str
    template_id: str
    cadence: SurveyCadence
    assessment_date: date
    period_start: date
    period_end: date
    comment_reference_date: date
    status: SurveyResponseStatus
    source: str
    consent_record_id: str | None
    submitted_at: datetime | None
    client_request_id: str | None
    lock_version: int
    answers: list[SurveyAnswerOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SurveyResponseRevisionOut(ORMModel):
    id: str
    response_id: str
    revision_no: int
    actor_id: int | None
    reason: str | None
    previous_answers_jsonb: dict[str, Any]
    changed_at: datetime
    change_type: str


class SurveyNLPAnalysisOut(ORMModel):
    id: str
    response_id: str
    answer_id: str
    status: str
    model_name: str | None
    model_version: str | None
    preprocessing_version: str | None
    schema_version: str | None
    result_jsonb: Any | None
    error_code: str | None
    attempt_count: int
    stale: bool
    analyzed_at: datetime | None
    created_at: datetime
    updated_at: datetime
