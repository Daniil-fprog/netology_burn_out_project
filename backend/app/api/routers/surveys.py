import csv
import io
import json
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.enum import RoleCode
from app.core.security import get_current_user
from app.core.access import (
    SURVEY_ROLES,
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
    SurveyNLPAnalysisModel,
    SurveyQuestionModel,
    SurveyResponseModel,
    SurveyResponseRevisionModel,
    SurveyTemplateModel,
)
from app.models.teacher import TeacherModel
from app.models.user import UserModel
from app.models.workload import (
    DailyWorkLogModel,
    PlannedWorkItemModel,
    WorkloadPlanVersionModel,
)
from app.schemas.survey import (
    SurveyCorrectionRequest,
    SurveyResponseRequest,
    SurveyStatusUpdate,
)
from app.services.survey_service import (
    get_response,
    get_template,
    response_dict,
    seed_surveys,
    validate_answers,
    validate_period,
)
from app.services.workload_analytic_service import pseudo, safe_cell
from app.services.workload_service import total
from app.utils.pagination import paginate


router = APIRouter(tags=["Teacher surveys"])
# MVP 2 FUTURE: response revisions, NLP and ML dataset endpoints are preserved
# on this router but intentionally not included in app.api.v1.
future_router = APIRouter(tags=["MVP 2: survey processing"])


@router.get("/schools/{school_id}/surveys")
def list_surveys(
    school_id: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает актуальные опубликованные опросы, доступные пользователю в школе."""

    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    rows = (
        db.query(SurveyTemplateModel)
        .filter_by(status="published", is_current=True)
        .order_by(SurveyTemplateModel.code)
        .all()
    )
    return [
        {
            "code": x.code,
            "version": x.version,
            "title": x.title,
            "cadence": x.cadence,
            "estimated_minutes": x.definition_jsonb.get("estimated_minutes"),
        }
        for x in rows
    ]


@router.get("/schools/{school_id}/surveys/{code}")
def survey(
    school_id: str,
    code: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает полное описание текущей опубликованной версии опроса."""

    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    return get_template(db, code).definition_jsonb


@router.get("/schools/{school_id}/surveys/{code}/versions/{version}")
def survey_version(
    school_id: str,
    code: str,
    version: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает полное описание конкретной опубликованной версии опроса."""

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
    """Проверяет JSON-каталог опросов или импортирует его новые версии и вопросы."""

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


@router.post("/schools/{school_id}/survey-responses", status_code=201)
def create_response(
    school_id: str,
    data: SurveyResponseRequest,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Одним запросом создаёт черновик прохождения и сохраняет все его ответы."""

    require_school_access(db, user.id, school_id, {"teacher"})
    teacher = require_own_teacher(db, user.id, school_id)
    teacher_id = teacher.id
    template = get_template(db, data.survey_code, data.survey_version)
    comment_date = data.comment_reference_date or data.assessment_date
    validate_period(
        template.cadence,
        data.assessment_date,
        data.period_start,
        data.period_end,
        comment_date,
    )
    if data.client_request_id:
        existing = (
            db.query(SurveyResponseModel)
            .filter_by(teacher_id=teacher_id, client_request_id=data.client_request_id)
            .first()
        )
        if existing:
            incoming = data.answers
            saved = {a.question.code: a.value_jsonb for a in existing.answers}
            if incoming != saved or data.consent_given != existing.consent_given:
                raise HTTPException(
                    status_code=409,
                    detail="client_request_id уже использован с другими данными",
                )
            return {
                **response_dict(existing, True),
                "answers_saved": len(existing.answers),
            }
    conflict = (
        db.query(SurveyResponseModel)
        .filter_by(
            teacher_id=teacher_id,
            cadence=template.cadence,
            period_start=data.period_start,
            period_end=data.period_end,
        )
        .filter(SurveyResponseModel.status.in_(["draft", "approved"]))
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=409, detail="Активный ответ на этот период уже существует"
        )
    questions = (
        db.query(SurveyQuestionModel)
        .filter_by(template_id=template.id)
        .order_by(SurveyQuestionModel.position)
        .all()
    )
    values = validate_answers(questions, data.answers, True)
    consented_at = datetime.now(timezone.utc)
    item = SurveyResponseModel(
        school_id=school_id,
        teacher_id=teacher_id,
        template_id=template.id,
        cadence=template.cadence,
        assessment_date=data.assessment_date,
        period_start=data.period_start,
        period_end=data.period_end,
        comment_reference_date=comment_date,
        status="draft",
        source=data.source,
        consent_given=True,
        consented_at=consented_at,
        approved_at=None,
        client_request_id=data.client_request_id,
    )
    db.add(item)
    db.flush()
    for question, value in values.items():
        answer = SurveyAnswerModel(
            response_id=item.id, question_id=question.id, value_jsonb=value
        )
        db.add(answer)
        db.flush()
        # MVP 2 FUTURE: enqueue SurveyNLPAnalysisModel for long-text answers.
    db.commit()
    db.refresh(item)
    return {**response_dict(item, True), "answers_saved": len(values)}

@router.post("/schools/{school_id}/survey-responses/{response_id}/approve")
def approve_response(
    school_id: str,
    response_id: str,
    data: SurveyStatusUpdate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Меняет статус на approved для владельца или на deactivated для администратора."""

    if data.status == "approved":
        require_school_access(db, user.id, school_id, {RoleCode.TEACHER})
        own_teacher = require_own_teacher(db, user.id, school_id)
        item = get_response(db, school_id, response_id)
        if item.teacher_id != own_teacher.id:
            raise HTTPException(status_code=404, detail="Ответ не найден")
        if item.status != "draft":
            raise HTTPException(
                status_code=409,
                detail="Подтвердить можно только черновик",
            )
        item.status = "approved"
        item.approved_at = datetime.now(timezone.utc)
        action = "approve"
    else:
        require_school_access(db, user.id, school_id, {RoleCode.SYSTEM_ADMIN})
        item = get_response(db, school_id, response_id)
        if item.status == "deactivated":
            return response_dict(item, True)
        item.status = "deactivated"
        action = "deactivate"

    db.add(
        AuditEventModel(
            actor_id=user.id,
            action=action,
            entity_type="survey_response",
            entity_id=item.id,
            school_id=school_id,
            changes={"status": data.status},
        )
    )
    db.commit()
    db.refresh(item)
    return response_dict(item, True)


@router.post("/schools/{school_id}/survey-responses/{response_id}/corrections")
def correct_response(
    school_id: str,
    response_id: str,
    data: SurveyCorrectionRequest,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Изменяет ответы непринятого опроса и сохраняет предыдущую версию в истории."""

    require_school_access(db, user.id, school_id, {"teacher"})
    own_teacher = require_own_teacher(db, user.id, school_id)
    item = get_response(db, school_id, response_id)
    if item.teacher_id != own_teacher.id:
        raise HTTPException(status_code=404, detail="Ответ не найден")
    if item.status == "approved":
        raise HTTPException(status_code=409, detail="Нельзя исправлять approved опрос")
    questions = (
        db.query(SurveyQuestionModel).filter_by(template_id=item.template_id).all()
    )
    current = {a.question.code: a.value_jsonb for a in item.answers}
    merged = {**current, **data.answers}
    values = validate_answers(questions, merged, True)
    revision_no = (
        db.query(SurveyResponseRevisionModel).filter_by(response_id=item.id).count() + 1
    )
    db.add(
        SurveyResponseRevisionModel(
            response_id=item.id,
            revision_no=revision_no,
            actor_id=user.id,
            reason=data.description,
            previous_answers_jsonb=current,
            change_type="correct",
        )
    )
    by_q = {a.question_id: a for a in item.answers}
    for q, value in values.items():
        if q.id in by_q:
            by_q[q.id].value_jsonb = value
        else:
            db.add(
                SurveyAnswerModel(
                    response_id=item.id, question_id=q.id, value_jsonb=value
                )
            )
    db.query(SurveyNLPAnalysisModel).filter_by(response_id=item.id).update(
        {"stale": True}
    )
    item.lock_version += 1
    db.commit()
    db.refresh(item)
    return response_dict(item, True)


@router.get("/schools/{school_id}/survey-responses")
def responses(
    school_id: str,
    teacher_id: str | None = None,
    survey_code: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает доступные ответы с фильтрами по педагогу, опросу, статусу и датам."""

    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    q = db.query(SurveyResponseModel).filter_by(school_id=school_id)
    own_teacher_id = get_teacher_id_filter(db, user.id, school_id)
    teacher_id = own_teacher_id or teacher_id
    if teacher_id:
        q = q.filter_by(teacher_id=teacher_id)
    if survey_code:
        q = q.join(SurveyTemplateModel).filter(SurveyTemplateModel.code == survey_code)
    if status:
        q = q.filter(SurveyResponseModel.status == status)
    if date_from:
        q = q.filter(SurveyResponseModel.assessment_date >= date_from)
    if date_to:
        q = q.filter(SurveyResponseModel.assessment_date <= date_to)
    rows = q.order_by(SurveyResponseModel.assessment_date.desc()).all()
    return paginate(
        [response_dict(x, own_teacher_id == x.teacher_id) for x in rows],
        page,
        page_size,
    )


@router.get("/schools/{school_id}/survey-responses/{response_id}")
def response(
    school_id: str,
    response_id: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает один доступный ответ; исходный текст видит только его автор."""

    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    item = get_response(db, school_id, response_id)
    require_teacher_access(db, user.id, school_id, item.teacher_id)
    own_teacher = find_user_teacher_in_school(db, user.id, school_id)
    return response_dict(
        item, own_teacher is not None and own_teacher.id == item.teacher_id
    )


@router.get("/schools/{school_id}/surveys/exports")
def export_surveys(
    school_id: str,
    format: str = Query("xlsx", pattern="^(xlsx|csv|json)$"),
    report: str = Query("responses", pattern="^(responses|summary)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Выгружает псевдонимизированные ответы и встроенное согласие в JSON, CSV или XLSX."""

    require_school_access(db, user.id, school_id, {"head", "group_head"})
    q = db.query(SurveyResponseModel).filter_by(school_id=school_id, status="approved")
    if date_from:
        q = q.filter(SurveyResponseModel.assessment_date >= date_from)
    if date_to:
        q = q.filter(SurveyResponseModel.assessment_date <= date_to)
    rows = []
    for item in q.order_by(SurveyResponseModel.assessment_date).all():
        data = response_dict(item, False)
        rows.append(
            {
                "response_id": item.id,
                "teacher_key": pseudo(item.teacher_id),
                "survey_code": item.template.code,
                "survey_version": item.template.version,
                "assessment_date": str(item.assessment_date),
                "period_start": str(item.period_start),
                "period_end": str(item.period_end),
                "consent_given": item.consent_given,
                "consented_at": item.consented_at.isoformat()
                if item.consented_at
                else None,
                **{k: safe_cell(v) for k, v in data["answers"].items()},
            }
        )
    db.add(
        AuditEventModel(
            actor_id=user.id,
            action="export",
            entity_type="surveys",
            school_id=school_id,
            purpose=report,
            changes={"format": format, "rows": len(rows)},
        )
    )
    db.commit()
    columns = (
        sorted({k for row in rows for k in row})
        if rows
        else [
            "response_id",
            "teacher_key",
            "survey_code",
            "survey_version",
            "assessment_date",
            "period_start",
            "period_end",
            "consent_given",
            "consented_at",
        ]
    )
    if format == "json":
        return StreamingResponse(
            io.BytesIO(json.dumps(rows, ensure_ascii=False).encode()),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="survey_responses.json"'
            },
        )
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return StreamingResponse(
            iter([output.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="survey_responses.csv"'
            },
        )
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Ответы_значения"
    ws.append(columns)
    for row in rows:
        ws.append([row.get(c) for c in columns])
    meta = wb.create_sheet("Метаданные")
    meta.append(["exported_at", datetime.now(timezone.utc).isoformat()])
    meta.append(["anonymization_mode", "pseudonymized"])
    meta.append(["data_dictionary_version", "1.0"])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="survey_responses.xlsx"'},
    )


@future_router.get("/schools/{school_id}/ml/teacher-wellbeing/dataset")
def ml_dataset(
    school_id: str,
    date_from: date,
    date_to: date,
    feature_version: str = Query("v1", pattern="^v1$"),
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Формирует псевдонимизированный набор признаков для ML; маршрут зарезервирован для MVP 2."""

    require_school_access(db, user.id, school_id, {"head", "group_head"})
    teachers = db.query(TeacherModel).filter_by(school_id=school_id).all()
    result = []
    day = date_from
    while day <= date_to:
        cutoff = datetime.combine(
            day + timedelta(days=1), time.min, tzinfo=timezone.utc
        )
        for teacher in teachers:
            start7, start14, start28 = (
                day - timedelta(days=6),
                day - timedelta(days=13),
                day - timedelta(days=27),
            )
            responses = (
                db.query(SurveyResponseModel)
                .join(SurveyTemplateModel)
                .filter(
                    SurveyResponseModel.teacher_id == teacher.id,
                    SurveyResponseModel.status == "approved",
                    SurveyResponseModel.approved_at < cutoff,
                    SurveyResponseModel.assessment_date >= start28,
                    SurveyResponseModel.assessment_date <= day,
                )
                .all()
            )
            values = []
            for r in responses:
                values.append((r, {a.question.code: a.value_jsonb for a in r.answers}))

            def mean(code, since):
                nums = [
                    a[code]
                    for r, a in values
                    if r.assessment_date >= since
                    and code in a
                    and isinstance(a[code], (int, float))
                ]
                return sum(nums) / len(nums) if nums else None

            actual_logs = (
                db.query(DailyWorkLogModel)
                .filter(
                    DailyWorkLogModel.teacher_id == teacher.id,
                    DailyWorkLogModel.work_date.between(start7, day),
                )
                .all()
            )
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
            plan_totals = [
                float(total(items)) for _, items in latest_plan_by_day.values()
            ]
            latest_weekly = next(
                (
                    a
                    for r, a in sorted(
                        values, key=lambda x: x[0].assessment_date, reverse=True
                    )
                    if r.cadence == "weekly"
                ),
                {},
            )
            latest_monthly = next(
                (
                    a
                    for r, a in sorted(
                        values, key=lambda x: x[0].assessment_date, reverse=True
                    )
                    if r.cadence == "monthly"
                ),
                {},
            )
            result.append(
                {
                    "teacher_key": pseudo(teacher.id),
                    "as_of_date": str(day),
                    "feature_version": feature_version,
                    "daily_fatigue_mean_7d": mean("fatigue_score", start7),
                    "daily_stress_mean_7d": mean("stress_score", start7),
                    "emotional_exhaustion_mean_14d": mean(
                        "emotional_exhaustion_today", start14
                    ),
                    "recovery_capacity_mean_7d": mean("recovery_capacity", start7),
                    "survey_response_count_7d": sum(
                        1 for r, _ in values if r.assessment_date >= start7
                    ),
                    "survey_missing_days_7d": None,
                    "workload_actual_hours_7d": sum(actual_totals)
                    if actual_totals
                    else None,
                    "workload_plan_hours_7d": sum(plan_totals) if plan_totals else None,
                    "workload_delta_hours_7d": sum(actual_totals) - sum(plan_totals)
                    if actual_totals and plan_totals
                    else None,
                    "weekly_sleep_disruption_latest": latest_weekly.get(
                        "sleep_disruption"
                    ),
                    "monthly_persistent_exhaustion_latest": latest_monthly.get(
                        "persistent_exhaustion"
                    ),
                    "target_label": None,
                    "target_assessment_date": None,
                }
            )
        day += timedelta(days=1)
    columns = (
        list(result[0]) if result else ["teacher_key", "as_of_date", "feature_version"]
    )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(result)
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="teacher_wellbeing_ml_{feature_version}_{date.today():%Y%m%d}.csv"'
        },
    )


@future_router.post(
    "/schools/{school_id}/survey-responses/{response_id}/nlp/reprocess", status_code=202
)
def reprocess_nlp(
    school_id: str,
    response_id: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Создаёт повторное NLP-задание для текста согласованного опроса в MVP 2."""

    require_school_access(db, user.id, school_id, {"teacher"})
    own_teacher = require_own_teacher(db, user.id, school_id)
    item = get_response(db, school_id, response_id)
    if item.teacher_id != own_teacher.id:
        raise HTTPException(status_code=404, detail="Ответ не найден")
    if not item.consent_given or item.status != "approved":
        raise HTTPException(
            status_code=403, detail="Нет согласия в отправленном опросе"
        )
    answer = next(
        (x for x in item.answers if x.question.code == "today_workload_feeling"), None
    )
    if not answer:
        raise HTTPException(status_code=422, detail="Нет текста для NLP")
    job = SurveyNLPAnalysisModel(
        response_id=item.id, answer_id=answer.id, status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"id": job.id, "status": job.status}


@future_router.get("/schools/{school_id}/survey-responses/{response_id}/nlp")
def nlp_results(
    school_id: str,
    response_id: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает результаты NLP-обработки ответа; маршрут зарезервирован для MVP 2."""

    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    item = get_response(db, school_id, response_id)
    require_teacher_access(db, user.id, school_id, item.teacher_id)
    return [
        {
            "id": x.id,
            "status": x.status,
            "model_name": x.model_name,
            "model_version": x.model_version,
            "schema_version": x.schema_version,
            "result": x.result_jsonb,
            "stale": x.stale,
            "analyzed_at": x.analyzed_at,
        }
        for x in db.query(SurveyNLPAnalysisModel)
        .filter_by(response_id=response_id)
        .order_by(SurveyNLPAnalysisModel.created_at.desc())
    ]


# Starlette resolves equal-method routes in declaration order. Static endpoints
# such as /surveys/exports must precede the /surveys/{code} catalog route.
router.routes.sort(key=lambda route: route.path.count("{"))
