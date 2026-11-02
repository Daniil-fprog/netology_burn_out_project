import hashlib
import json
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.teacher_domain import (
    SurveyAnswerModel, SurveyConsentModel, SurveyNLPAnalysisModel, SurveyQuestionModel,
    SurveyResponseModel, SurveyResponseRevisionModel, SurveyTemplateModel,
)


CATALOG_FILE = Path(__file__).resolve().parent.parent / "data" / "teacher_wellbeing_surveys.json"


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def seed_surveys(db: Session, catalog: dict | None = None) -> dict:
    if catalog is None:
        catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    created = 0
    for definition in catalog.get("surveys", []):
        code, version = definition.get("code"), definition.get("version")
        if not code or not version or not isinstance(definition.get("questions"), list):
            raise HTTPException(status_code=422, detail="Неверный каталог опросов")
        digest = canonical_hash(definition)
        existing = db.query(SurveyTemplateModel).filter_by(code=code, version=version).first()
        if existing:
            if existing.content_hash != digest: raise HTTPException(status_code=409, detail=f"Опубликованная версия {code}/{version} имеет другой hash")
            continue
        db.query(SurveyTemplateModel).filter_by(code=code, is_current=True).update({"is_current": None})
        template = SurveyTemplateModel(code=code, version=version, title=definition["title"], cadence=definition["cadence"], locale=definition.get("locale", "ru-RU"), definition_jsonb=definition, content_hash=digest, status="published", is_current=True, published_at=datetime.now(timezone.utc))
        db.add(template); db.flush()
        for position, question in enumerate(definition["questions"], 1):
            settings = {k: v for k, v in question.items() if k not in {"id", "title", "type", "required"}}
            db.add(SurveyQuestionModel(template_id=template.id, code=question["id"], title=question["title"], type=question["type"], position=position, required=question.get("required", False), settings_jsonb=settings))
        created += 1
    db.commit()
    return {"created": created, "templates": len(catalog.get("surveys", []))}


def validate_period(cadence: str, assessment: date, start: date, end: date, comment_date: date) -> None:
    if comment_date != assessment: raise HTTPException(status_code=422, detail="comment_reference_date должна равняться assessment_date")
    if start > end or assessment < start: raise HTTPException(status_code=422, detail="Неверный период опроса")
    if cadence == "daily" and (start != assessment or end != assessment): raise HTTPException(status_code=422, detail="Дневной период должен равняться assessment_date")
    if cadence == "weekly" and (start.weekday() != 0 or end != start + timedelta(days=6)): raise HTTPException(status_code=422, detail="Недельный период: понедельник–воскресенье")
    if cadence == "monthly" and (start.day != 1 or end != date(start.year, start.month, monthrange(start.year, start.month)[1])): raise HTTPException(status_code=422, detail="Месячный период должен охватывать календарный месяц")


def validate_answers(questions: list[SurveyQuestionModel], answers: dict[str, Any], submitted: bool) -> dict[SurveyQuestionModel, Any]:
    by_code = {q.code: q for q in questions}
    unknown = set(answers) - set(by_code)
    if unknown: raise HTTPException(status_code=422, detail=f"Неизвестные question_code: {', '.join(sorted(unknown))}")
    if submitted:
        missing = [q.code for q in questions if q.required and q.code not in answers]
        if missing: raise HTTPException(status_code=422, detail=f"Нет обязательных ответов: {', '.join(missing)}")
    result = {}
    for code, value in answers.items():
        q, settings = by_code[code], by_code[code].settings_jsonb
        if q.type == "integer_scale":
            if isinstance(value, bool) or not isinstance(value, int): raise HTTPException(status_code=422, detail=f"{code}: ожидается целое число")
            if value < settings.get("min", 1) or value > settings.get("max", 5) or (value - settings.get("min", 1)) % settings.get("step", 1): raise HTTPException(status_code=422, detail=f"{code}: значение вне шкалы")
        elif q.type == "single_choice":
            allowed = {o["value"] for o in settings.get("options", [])}
            if not isinstance(value, str) or value not in allowed: raise HTTPException(status_code=422, detail=f"{code}: недопустимый вариант")
        elif q.type == "long_text":
            if not isinstance(value, str): raise HTTPException(status_code=422, detail=f"{code}: ожидается строка")
            value = value.strip()
            if len(value) < settings.get("min_length", 0) or len(value) > settings.get("max_length", 3000): raise HTTPException(status_code=422, detail=f"{code}: неверная длина текста")
        else: raise HTTPException(status_code=422, detail=f"{code}: неподдерживаемый тип")
        result[q] = value
    return result


def active_consent(db: Session, school_id: str, teacher_id: str, consent_id: str | None) -> SurveyConsentModel | None:
    if not consent_id: return None
    return db.query(SurveyConsentModel).filter_by(id=consent_id, school_id=school_id, teacher_id=teacher_id, purpose="survey_storage", withdrawn_at=None).first()


def response_dict(response: SurveyResponseModel, include_comments: bool = True) -> dict:
    answers = {}
    for item in response.answers:
        if not include_comments and item.question.type == "long_text": continue
        answers[item.question.code] = item.value_jsonb
    return {"id": response.id, "school_id": response.school_id, "teacher_id": response.teacher_id, "survey_code": response.template.code, "survey_version": response.template.version, "cadence": response.cadence, "assessment_date": response.assessment_date, "period_start": response.period_start, "period_end": response.period_end, "comment_reference_date": response.comment_reference_date, "status": response.status, "source": response.source, "submitted_at": response.submitted_at, "lock_version": response.lock_version, "answers": answers}
