import csv
import hashlib
import hmac
import io
import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import PSEUDONYM_SECRET
from app.core.enum import RoleCode
from app.core.security import get_current_user
from app.core.access import (
    SURVEY_ROLES,
    get_teacher_in_school,
    require_own_teacher,
    require_school_access,
    require_teacher_access,
    find_user_teacher_in_school,
    get_teacher_id_filter,
)
from app.db.database import get_db
from app.models.audit import AuditEventModel
from app.models.survey import (
    SurveyAnswerModel,
    SurveyConsentModel, SurveyNLPAnalysisModel, SurveyQuestionModel, SurveyResponseModel,
    SurveyResponseRevisionModel, SurveyTemplateModel,
)
from app.models.teacher import TeacherModel
from app.models.user import UserModel
from app.models.workload import DailyWorkLogModel, PlannedWorkItemModel, WorkloadPlanVersionModel
from app.services.survey_service import active_consent, response_dict, seed_surveys, validate_answers, validate_period
from app.services.workload_service import total


router = APIRouter(prefix="/api/v1", tags=["Teacher surveys"])


class ConsentCreate(BaseModel):
    policy_version: str = Field(min_length=1, max_length=50)
    purpose: str = Field(pattern="^(survey_storage|research_processing|external_nlp)$")
    method: str = Field(min_length=1, max_length=30)
    proof_reference: str | None = None


class ResponseCreate(BaseModel):
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


class DraftPatch(BaseModel):
    answers: dict[str, Any]


class Correction(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    answers: dict[str, Any]


def pagination(items: list, page: int, size: int) -> dict:
    start = (page - 1) * size
    return {"page": page, "page_size": size, "total": len(items), "items": items[start:start + size]}


def get_template(db: Session, code: str, version: str | None = None) -> SurveyTemplateModel:
    q = db.query(SurveyTemplateModel).filter_by(code=code, status="published")
    q = q.filter_by(version=version) if version else q.filter_by(is_current=True)
    item = q.first()
    if not item: raise HTTPException(status_code=404, detail="Опрос не найден")
    return item


def get_response(db: Session, school_id: str, response_id: str) -> SurveyResponseModel:
    item = db.query(SurveyResponseModel).filter_by(id=response_id, school_id=school_id).first()
    if not item: raise HTTPException(status_code=404, detail="Ответ не найден")
    return item


@router.get("/schools/{school_id}/surveys")
def list_surveys(school_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    rows = db.query(SurveyTemplateModel).filter_by(status="published", is_current=True).order_by(SurveyTemplateModel.code).all()
    return [{"code": x.code, "version": x.version, "title": x.title, "cadence": x.cadence, "estimated_minutes": x.definition_jsonb.get("estimated_minutes")} for x in rows]


@router.get("/schools/{school_id}/surveys/{code}")
def survey(school_id: str, code: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    return get_template(db, code).definition_jsonb


@router.get("/schools/{school_id}/surveys/{code}/versions/{version}")
def survey_version(school_id: str, code: str, version: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    return get_template(db, code, version).definition_jsonb


@router.post("/schools/{school_id}/surveys/templates/import")
async def import_templates(
    school_id: str,
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    require_school_access(db, user.id, school_id, {RoleCode.SYSTEM_ADMIN})
    try:
        catalog = json.loads((await file.read(2_000_001)).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Неверный JSON: {exc}") from exc
    if dry_run:
        surveys = catalog.get("surveys", [])
        return {
            "valid": bool(surveys),
            "templates": len(surveys),
            "questions": sum(len(item.get("questions", [])) for item in surveys),
        }
    return seed_surveys(db, catalog)


@router.post("/schools/{school_id}/teachers/{teacher_id}/survey-consents", status_code=201)
def grant_consent(school_id: str, teacher_id: str, data: ConsentCreate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"teacher"})
    own_teacher = require_own_teacher(db, user.id, school_id)
    if own_teacher.id != teacher_id: raise HTTPException(status_code=404, detail="Педагог не найден")
    item = SurveyConsentModel(school_id=school_id, teacher_id=teacher_id, **data.model_dump())
    db.add(item); db.add(AuditEventModel(actor_id=user.id, action="create", entity_type="survey_consent", entity_id=item.id, school_id=school_id, purpose=data.purpose, changes={"policy_version": data.policy_version, "method": data.method})); db.commit(); db.refresh(item)
    return {"id": item.id, "teacher_id": item.teacher_id, "purpose": item.purpose, "granted_at": item.granted_at}


@router.post("/schools/{school_id}/survey-consents/{consent_id}/withdraw")
def withdraw_consent(school_id: str, consent_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"teacher"})
    own_teacher = require_own_teacher(db, user.id, school_id)
    item = db.query(SurveyConsentModel).filter_by(id=consent_id, school_id=school_id).first()
    if not item: raise HTTPException(status_code=404, detail="Согласие не найдено")
    if item.teacher_id != own_teacher.id: raise HTTPException(status_code=404, detail="Согласие не найдено")
    item.withdrawn_at = datetime.now(timezone.utc); db.commit()
    return {"id": item.id, "withdrawn_at": item.withdrawn_at}


@router.post("/schools/{school_id}/survey-responses", status_code=201)
def create_response(school_id: str, data: ResponseCreate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"teacher"})
    teacher = require_own_teacher(db, user.id, school_id)
    teacher_id = teacher.id
    template = get_template(db, data.survey_code, data.survey_version)
    comment_date = data.comment_reference_date or data.assessment_date
    validate_period(template.cadence, data.assessment_date, data.period_start, data.period_end, comment_date)
    if data.client_request_id:
        existing = db.query(SurveyResponseModel).filter_by(teacher_id=teacher_id, client_request_id=data.client_request_id).first()
        if existing:
            incoming = data.answers
            saved = {a.question.code: a.value_jsonb for a in existing.answers}
            if incoming != saved: raise HTTPException(status_code=409, detail="client_request_id уже использован с другими данными")
            return {**response_dict(existing, True), "answers_saved": len(existing.answers), "nlp_status": "pending"}
    conflict = db.query(SurveyResponseModel).filter_by(teacher_id=teacher_id, cadence=template.cadence, period_start=data.period_start, period_end=data.period_end).filter(SurveyResponseModel.status.in_(["draft", "submitted"])).first()
    if conflict: raise HTTPException(status_code=409, detail="Активный ответ на этот период уже существует")
    questions = db.query(SurveyQuestionModel).filter_by(template_id=template.id).order_by(SurveyQuestionModel.position).all()
    values = validate_answers(questions, data.answers, data.status == "submitted")
    consent = active_consent(db, school_id, teacher_id, data.consent_record_id)
    if data.status == "submitted" and not consent: raise HTTPException(status_code=403, detail="Нет действующего согласия survey_storage")
    item = SurveyResponseModel(school_id=school_id, teacher_id=teacher_id, template_id=template.id, cadence=template.cadence, assessment_date=data.assessment_date, period_start=data.period_start, period_end=data.period_end, comment_reference_date=comment_date, status=data.status, source=data.source, consent_record_id=consent.id if consent else None, submitted_at=datetime.now(timezone.utc) if data.status == "submitted" else None, client_request_id=data.client_request_id)
    db.add(item); db.flush()
    for question, value in values.items():
        answer = SurveyAnswerModel(response_id=item.id, question_id=question.id, value_jsonb=value); db.add(answer); db.flush()
        if data.status == "submitted" and question.code == "today_workload_feeling": db.add(SurveyNLPAnalysisModel(response_id=item.id, answer_id=answer.id, status="pending"))
    db.commit(); db.refresh(item)
    return {**response_dict(item, True), "answers_saved": len(values), "nlp_status": "pending" if data.status == "submitted" else None}


@router.patch("/schools/{school_id}/survey-responses/{response_id}")
def patch_draft(school_id: str, response_id: str, data: DraftPatch, if_match: str | None = Header(default=None, alias="If-Match"), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"teacher"}); own_teacher = require_own_teacher(db, user.id, school_id); item = get_response(db, school_id, response_id)
    if item.teacher_id != own_teacher.id: raise HTTPException(status_code=404, detail="Ответ не найден")
    if item.status != "draft": raise HTTPException(status_code=409, detail="Можно менять только черновик")
    if if_match and if_match.strip('"') != str(item.lock_version): raise HTTPException(status_code=409, detail="Версия черновика изменилась")
    questions = db.query(SurveyQuestionModel).filter_by(template_id=item.template_id).all(); values = validate_answers(questions, data.answers, False)
    by_q = {a.question_id: a for a in item.answers}
    for q, value in values.items():
        if q.id in by_q: by_q[q.id].value_jsonb = value
        else: db.add(SurveyAnswerModel(response_id=item.id, question_id=q.id, value_jsonb=value))
    item.lock_version += 1; db.commit(); db.refresh(item); return response_dict(item, True)


@router.post("/schools/{school_id}/survey-responses/{response_id}/submit")
def submit_draft(school_id: str, response_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"teacher"}); own_teacher = require_own_teacher(db, user.id, school_id); item = get_response(db, school_id, response_id)
    if item.teacher_id != own_teacher.id: raise HTTPException(status_code=404, detail="Ответ не найден")
    if item.status != "draft": raise HTTPException(status_code=409, detail="Ответ уже отправлен")
    consent = active_consent(db, school_id, item.teacher_id, item.consent_record_id)
    if not consent: raise HTTPException(status_code=403, detail="Нет действующего согласия survey_storage")
    questions = db.query(SurveyQuestionModel).filter_by(template_id=item.template_id).all(); answers = {a.question.code: a.value_jsonb for a in item.answers}; validate_answers(questions, answers, True)
    item.status = "submitted"; item.submitted_at = datetime.now(timezone.utc)
    for answer in item.answers:
        if answer.question.code == "today_workload_feeling": db.add(SurveyNLPAnalysisModel(response_id=item.id, answer_id=answer.id, status="pending"))
    db.commit(); db.refresh(item); return response_dict(item, True)


@router.post("/schools/{school_id}/survey-responses/{response_id}/corrections")
def correct_response(school_id: str, response_id: str, data: Correction, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"teacher"}); own_teacher = require_own_teacher(db, user.id, school_id); item = get_response(db, school_id, response_id)
    if item.teacher_id != own_teacher.id: raise HTTPException(status_code=404, detail="Ответ не найден")
    if item.status != "submitted": raise HTTPException(status_code=409, detail="Исправлять можно только submitted")
    questions = db.query(SurveyQuestionModel).filter_by(template_id=item.template_id).all(); current = {a.question.code: a.value_jsonb for a in item.answers}; merged = {**current, **data.answers}; values = validate_answers(questions, merged, True)
    revision_no = db.query(SurveyResponseRevisionModel).filter_by(response_id=item.id).count() + 1
    db.add(SurveyResponseRevisionModel(response_id=item.id, revision_no=revision_no, actor_id=user.id, reason=data.reason, previous_answers_jsonb=current, change_type="correct"))
    by_q = {a.question_id: a for a in item.answers}
    for q, value in values.items():
        if q.id in by_q: by_q[q.id].value_jsonb = value
        else: db.add(SurveyAnswerModel(response_id=item.id, question_id=q.id, value_jsonb=value))
    db.query(SurveyNLPAnalysisModel).filter_by(response_id=item.id).update({"stale": True}); item.lock_version += 1; db.commit(); db.refresh(item)
    return response_dict(item, True)


@router.post("/schools/{school_id}/survey-responses/{response_id}/withdraw")
def withdraw_response(school_id: str, response_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"teacher"}); own_teacher = require_own_teacher(db, user.id, school_id); item = get_response(db, school_id, response_id)
    if item.teacher_id != own_teacher.id: raise HTTPException(status_code=404, detail="Ответ не найден")
    if item.status == "withdrawn": return response_dict(item, True)
    previous = {a.question.code: a.value_jsonb for a in item.answers}; revision_no = db.query(SurveyResponseRevisionModel).filter_by(response_id=item.id).count() + 1
    db.add(SurveyResponseRevisionModel(response_id=item.id, revision_no=revision_no, actor_id=user.id, previous_answers_jsonb=previous, change_type="withdraw")); item.status = "withdrawn"; db.query(SurveyNLPAnalysisModel).filter_by(response_id=item.id).update({"stale": True, "status": "cancelled"}); db.commit(); db.refresh(item)
    return response_dict(item, True)


@router.get("/schools/{school_id}/survey-responses")
def responses(school_id: str, teacher_id: str | None = None, survey_code: str | None = None, status: str | None = None, date_from: date | None = None, date_to: date | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, SURVEY_ROLES); q = db.query(SurveyResponseModel).filter_by(school_id=school_id)
    own_teacher_id = get_teacher_id_filter(db, user.id, school_id)
    teacher_id = own_teacher_id or teacher_id
    if teacher_id: q = q.filter_by(teacher_id=teacher_id)
    if survey_code: q = q.join(SurveyTemplateModel).filter(SurveyTemplateModel.code == survey_code)
    if status: q = q.filter(SurveyResponseModel.status == status)
    if date_from: q = q.filter(SurveyResponseModel.assessment_date >= date_from)
    if date_to: q = q.filter(SurveyResponseModel.assessment_date <= date_to)
    rows = q.order_by(SurveyResponseModel.assessment_date.desc()).all()
    return pagination([response_dict(x, own_teacher_id == x.teacher_id) for x in rows], page, page_size)


@router.get("/schools/{school_id}/survey-responses/{response_id}")
def response(school_id: str, response_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, SURVEY_ROLES); item = get_response(db, school_id, response_id); require_teacher_access(db, user.id, school_id, item.teacher_id); own_teacher = find_user_teacher_in_school(db, user.id, school_id); return response_dict(item, own_teacher is not None and own_teacher.id == item.teacher_id)


@router.get("/schools/{school_id}/teachers/{teacher_id}/survey-history")
def history(school_id: str, teacher_id: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, SURVEY_ROLES); require_teacher_access(db, user.id, school_id, teacher_id); get_teacher_in_school(db, school_id, teacher_id)
    rows = db.query(SurveyResponseModel).filter_by(school_id=school_id, teacher_id=teacher_id).order_by(SurveyResponseModel.assessment_date.desc()).all()
    own_teacher = find_user_teacher_in_school(db, user.id, school_id)
    return pagination([response_dict(x, own_teacher is not None and own_teacher.id == x.teacher_id) for x in rows], page, page_size)


@router.get("/schools/{school_id}/survey-analytics/completion")
def completion(school_id: str, date_from: date, date_to: date, teacher_id: str | None = None, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    if date_from > date_to: raise HTTPException(status_code=422, detail="date_from позже date_to")
    teacher_id = get_teacher_id_filter(db, user.id, school_id) or teacher_id
    teacher_query = db.query(TeacherModel).filter_by(school_id=school_id, is_active=True)
    if teacher_id: teacher_query = teacher_query.filter_by(id=teacher_id)
    teachers = teacher_query.all()
    days = (date_to - date_from).days + 1
    expected_per_teacher = {
        "daily": days,
        "weekly": len({(date_from + timedelta(days=i)) - timedelta(days=(date_from + timedelta(days=i)).weekday()) for i in range(days)}),
        "monthly": len({((date_from + timedelta(days=i)).year, (date_from + timedelta(days=i)).month) for i in range(days)}),
    }
    items = []
    for teacher in teachers:
        counts = {"daily": 0, "weekly": 0, "monthly": 0}
        rows = db.query(SurveyResponseModel).filter(SurveyResponseModel.teacher_id == teacher.id, SurveyResponseModel.status == "submitted", SurveyResponseModel.assessment_date.between(date_from, date_to)).all()
        for item in rows: counts[item.cadence] += 1
        expected = sum(expected_per_teacher.values()); completed = sum(counts.values())
        items.append({"teacher_id": teacher.id, "teacher_key": pseudo(teacher.id), "completed": completed, "expected": expected, "completion_rate": completed / expected if expected else None, "by_cadence": {key: {"completed": counts[key], "expected": expected_per_teacher[key]} for key in counts}, "denominator_policy": "calendar_periods_v1"})
    return {"date_from": date_from, "date_to": date_to, "items": items}


def pseudo(teacher_id: str) -> str:
    return hmac.new(PSEUDONYM_SECRET.encode(), teacher_id.encode(), hashlib.sha256).hexdigest()[:24]


def safe_cell(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip("\x00\t\r\n ").startswith(("=", "+", "-", "@")): return "'" + value
    return value


@router.get("/schools/{school_id}/surveys/exports")
def export_surveys(school_id: str, format: str = Query("xlsx", pattern="^(xlsx|csv|json)$"), report: str = Query("responses", pattern="^(responses|summary)$"), date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"head", "group_head"})
    q = db.query(SurveyResponseModel).filter_by(school_id=school_id, status="submitted")
    if date_from: q = q.filter(SurveyResponseModel.assessment_date >= date_from)
    if date_to: q = q.filter(SurveyResponseModel.assessment_date <= date_to)
    rows = []
    for item in q.order_by(SurveyResponseModel.assessment_date).all():
        data = response_dict(item, False); rows.append({"response_id": item.id, "teacher_key": pseudo(item.teacher_id), "survey_code": item.template.code, "survey_version": item.template.version, "assessment_date": str(item.assessment_date), "period_start": str(item.period_start), "period_end": str(item.period_end), **{k: safe_cell(v) for k, v in data["answers"].items()}})
    db.add(AuditEventModel(actor_id=user.id, action="export", entity_type="surveys", school_id=school_id, purpose=report, changes={"format": format, "rows": len(rows)})); db.commit()
    columns = sorted({k for row in rows for k in row}) if rows else ["response_id", "teacher_key", "survey_code", "survey_version", "assessment_date", "period_start", "period_end"]
    if format == "json": return StreamingResponse(io.BytesIO(json.dumps(rows, ensure_ascii=False).encode()), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="survey_responses.json"'})
    if format == "csv":
        output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)
        return StreamingResponse(iter([output.getvalue().encode("utf-8-sig")]), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="survey_responses.csv"'})
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "Ответы_значения"; ws.append(columns)
    for row in rows: ws.append([row.get(c) for c in columns])
    meta = wb.create_sheet("Метаданные"); meta.append(["exported_at", datetime.now(timezone.utc).isoformat()]); meta.append(["anonymization_mode", "pseudonymized"]); meta.append(["data_dictionary_version", "1.0"])
    output = io.BytesIO(); wb.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="survey_responses.xlsx"'})


@router.get("/schools/{school_id}/ml/teacher-wellbeing/dataset")
def ml_dataset(school_id: str, date_from: date, date_to: date, feature_version: str = Query("v1", pattern="^v1$"), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"head", "group_head"})
    teachers = db.query(TeacherModel).filter_by(school_id=school_id).all(); result = []
    day = date_from
    while day <= date_to:
        cutoff = datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone.utc)
        for teacher in teachers:
            start7, start14, start28 = day - timedelta(days=6), day - timedelta(days=13), day - timedelta(days=27)
            responses = db.query(SurveyResponseModel).join(SurveyTemplateModel).filter(SurveyResponseModel.teacher_id == teacher.id, SurveyResponseModel.status == "submitted", SurveyResponseModel.submitted_at < cutoff, SurveyResponseModel.assessment_date >= start28, SurveyResponseModel.assessment_date <= day).all()
            values = []
            for r in responses:
                values.append((r, {a.question.code: a.value_jsonb for a in r.answers}))
            def mean(code, since):
                nums = [a[code] for r, a in values if r.assessment_date >= since and code in a and isinstance(a[code], (int, float))]
                return sum(nums) / len(nums) if nums else None
            actual_logs = db.query(DailyWorkLogModel).filter(
                DailyWorkLogModel.teacher_id == teacher.id,
                DailyWorkLogModel.work_date.between(start7, day),
            ).all()
            actual_totals = [float(total(list(log.entries))) for log in actual_logs]
            plan_items = (
                db.query(PlannedWorkItemModel)
                .join(WorkloadPlanVersionModel)
                .filter(
                    WorkloadPlanVersionModel.school_id == school_id,
                    WorkloadPlanVersionModel.status == "published",
                    PlannedWorkItemModel.teacher_id == teacher.id,
                    PlannedWorkItemModel.work_date.between(start7, day),
                )
                .order_by(WorkloadPlanVersionModel.version)
                .all()
            )
            latest_plan_by_day = {}
            for plan_item in plan_items:
                current = latest_plan_by_day.get(plan_item.work_date)
                version = plan_item.plan_version.version
                if current is None or version > current[0]:
                    latest_plan_by_day[plan_item.work_date] = (version, [])
                if version == latest_plan_by_day[plan_item.work_date][0]:
                    latest_plan_by_day[plan_item.work_date][1].append(plan_item)
            plan_totals = [float(total(items)) for _, items in latest_plan_by_day.values()]
            latest_weekly = next((a for r, a in sorted(values, key=lambda x: x[0].assessment_date, reverse=True) if r.cadence == "weekly"), {})
            latest_monthly = next((a for r, a in sorted(values, key=lambda x: x[0].assessment_date, reverse=True) if r.cadence == "monthly"), {})
            result.append({"teacher_key": pseudo(teacher.id), "as_of_date": str(day), "feature_version": feature_version, "daily_fatigue_mean_7d": mean("fatigue_score", start7), "daily_stress_mean_7d": mean("stress_score", start7), "emotional_exhaustion_mean_14d": mean("emotional_exhaustion_today", start14), "recovery_capacity_mean_7d": mean("recovery_capacity", start7), "survey_response_count_7d": sum(1 for r, _ in values if r.assessment_date >= start7), "survey_missing_days_7d": None, "workload_actual_hours_7d": sum(actual_totals) if actual_totals else None, "workload_plan_hours_7d": sum(plan_totals) if plan_totals else None, "workload_delta_hours_7d": sum(actual_totals) - sum(plan_totals) if actual_totals and plan_totals else None, "weekly_sleep_disruption_latest": latest_weekly.get("sleep_disruption"), "monthly_persistent_exhaustion_latest": latest_monthly.get("persistent_exhaustion"), "target_label": None, "target_assessment_date": None})
        day += timedelta(days=1)
    columns = list(result[0]) if result else ["teacher_key", "as_of_date", "feature_version"]
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=columns); writer.writeheader(); writer.writerows(result)
    return StreamingResponse(iter([output.getvalue().encode("utf-8-sig")]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="teacher_wellbeing_ml_{feature_version}_{date.today():%Y%m%d}.csv"'})


@router.get("/schools/{school_id}/survey-responses/{response_id}/nlp")
def nlp_results(school_id: str, response_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, SURVEY_ROLES); item = get_response(db, school_id, response_id); require_teacher_access(db, user.id, school_id, item.teacher_id)
    return [{"id": x.id, "status": x.status, "model_name": x.model_name, "model_version": x.model_version, "schema_version": x.schema_version, "result": x.result_jsonb, "stale": x.stale, "analyzed_at": x.analyzed_at} for x in db.query(SurveyNLPAnalysisModel).filter_by(response_id=response_id).order_by(SurveyNLPAnalysisModel.created_at.desc())]


@router.post("/schools/{school_id}/survey-responses/{response_id}/nlp/reprocess", status_code=202)
def reprocess_nlp(school_id: str, response_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"teacher"})
    own_teacher = require_own_teacher(db, user.id, school_id)
    item = get_response(db, school_id, response_id)
    if item.teacher_id != own_teacher.id: raise HTTPException(status_code=404, detail="Ответ не найден")
    consent = db.query(SurveyConsentModel).filter_by(school_id=school_id, teacher_id=item.teacher_id, purpose="research_processing", withdrawn_at=None).first()
    if not consent: raise HTTPException(status_code=403, detail="Нет действующего согласия research_processing")
    answer = next((x for x in item.answers if x.question.code == "today_workload_feeling"), None)
    if not answer: raise HTTPException(status_code=422, detail="Нет текста для NLP")
    job = SurveyNLPAnalysisModel(response_id=item.id, answer_id=answer.id, status="pending")
    db.add(job); db.commit(); db.refresh(job)
    return {"id": job.id, "status": job.status}


@router.get("/schools/{school_id}/teachers/{teacher_id}/workload-and-wellbeing")
def workload_and_wellbeing(school_id: str, teacher_id: str, date_from: date, date_to: date, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, SURVEY_ROLES); require_teacher_access(db, user.id, school_id, teacher_id); get_teacher_in_school(db, school_id, teacher_id)
    actual_logs = db.query(DailyWorkLogModel).filter(
        DailyWorkLogModel.teacher_id == teacher_id,
        DailyWorkLogModel.work_date.between(date_from, date_to),
    ).all()
    responses = db.query(SurveyResponseModel).filter(SurveyResponseModel.teacher_id == teacher_id, SurveyResponseModel.assessment_date.between(date_from, date_to), SurveyResponseModel.status == "submitted").all()
    by_date = {}
    for log in actual_logs:
        by_date.setdefault(
            str(log.work_date),
            {"date": log.work_date, "workload": None, "surveys": []},
        )["workload"] = {
            "actual_total_hours": float(total(list(log.entries))),
            "status": log.status,
            "source": "daily_work_logs",
        }
    own_teacher = find_user_teacher_in_school(db, user.id, school_id)
    for item in responses: by_date.setdefault(str(item.assessment_date), {"date": item.assessment_date, "workload": None, "surveys": []})["surveys"].append(response_dict(item, own_teacher is not None and own_teacher.id == item.teacher_id))
    return [by_date[k] for k in sorted(by_date)]


# Starlette resolves equal-method routes in declaration order. Static endpoints
# such as /surveys/exports must precede the /surveys/{code} catalog route.
router.routes.sort(key=lambda route: route.path.count("{"))
