import io
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import MAX_UPLOAD_BYTES, PRIVATE_UPLOAD_DIR
from app.core.security import get_current_user
from app.core.work_duration import to_teaching_hours
from app.core.workload_import_contract import (
    ACADEMIC_HOUR_FIELDS,
    ACTUAL_HEADERS,
    NORM_HEADERS,
    PLAN_HEADERS,
)
from app.core.access import (
    FACT_ROLES,
    PLAN_MANAGER_ROLES,
    get_teacher_in_school,
    require_school_access,
    require_teacher_access,
    require_own_teacher,
    get_teacher_id_filter,
    user_role_codes,
)
from app.db.database import get_db
from app.models.audit import AuditEventModel
from app.models.import_batch import ImportBatchModel
from app.models.teacher import TeacherModel
from app.models.user import UserModel
from app.models.work_type import WorkTypeModel
from app.models.workload import (
    ActualWorkEntryModel,
    DailyWorkLogModel,
    PlannedWorkItemModel,
    TeacherWorkloadNormModel,
    WorkloadPlanVersionModel,
)
from app.schemas.analytics import PlannedDashboardOut
from app.schemas.workload import ActualPatch, DailyWorkLogCreate
from app.services.analytics_service import get_planned_dashboard
from app.services.workload_service import (
    daily_dict,
    import_workbook,
    parse_workbook,
    validation_report,
)
from app.utils.pagination import paginate


router = APIRouter(tags=["Teacher workload"])
# MVP 2 FUTURE: preserved endpoints for plans, norms and XLSX import/export.
# This router is intentionally not included in app.api.v1.
future_router = APIRouter(tags=["MVP 2: planned workload"])


def batch_dict(item: ImportBatchModel) -> dict:
    return {
        "id": item.id,
        "school_id": item.school_id,
        "original_filename": item.original_filename,
        "sha256": item.sha256,
        "status": item.status,
        "mode": item.mode,
        "effective_from": item.effective_from,
        "rows_total": item.rows_total,
        "rows_created": item.rows_created,
        "rows_updated": item.rows_updated,
        "rows_skipped": item.rows_skipped,
        "validation_report": item.validation_report,
        "imported_at": item.imported_at,
    }


@future_router.get("/dashboard/planned", response_model=PlannedDashboardOut)
def planned_dashboard(
    school_id: str,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает сводную аналитику плановой нагрузки; маршрут зарезервирован для MVP 2."""

    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    try:
        return get_planned_dashboard(db, {school_id}, date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def read_xlsx(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Допустим только .xlsx")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    if not data.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="Файл не является XLSX")
    return data


@future_router.post("/schools/{school_id}/workload/imports/validate")
async def validate_import(
    school_id: str,
    file: UploadFile = File(...),
    effective_from: date = Form(...),
    mode: str = Form("insert_only"),
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Проверяет XLSX нагрузки без сохранения данных; маршрут зарезервирован для MVP 2."""

    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    if mode not in {"insert_only", "upsert"}:
        raise HTTPException(
            status_code=422, detail="replace_period ещё не поддерживается"
        )
    content = await read_xlsx(file)
    return validation_report(
        db, school_id, parse_workbook(content), mode, effective_from
    )


@future_router.post("/schools/{school_id}/workload/imports", status_code=201)
async def create_import(
    school_id: str,
    file: UploadFile = File(...),
    effective_from: date = Form(...),
    mode: str = Form("insert_only"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Сохраняет XLSX и импортирует нормы и плановую нагрузку в рамках MVP 2."""

    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    if mode not in {"insert_only", "upsert"}:
        raise HTTPException(
            status_code=422, detail="replace_period ещё не поддерживается"
        )
    content = await read_xlsx(file)
    PRIVATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha256(content).hexdigest()
    path = PRIVATE_UPLOAD_DIR / f"{school_id}_{digest}.xlsx"
    path.write_bytes(content)
    try:
        item = import_workbook(
            db,
            school_id,
            content,
            file.filename or "upload.xlsx",
            mode,
            effective_from,
            user.id,
            path.name,
        )
    except Exception:
        db.rollback()
        if (
            not db.query(ImportBatchModel)
            .filter_by(school_id=school_id, sha256=digest)
            .first()
            and path.exists()
        ):
            path.unlink()
        raise
    return batch_dict(item)


@future_router.get("/schools/{school_id}/workload/imports")
def list_imports(
    school_id: str,
    page_no: int = Query(1, alias="page", ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает историю импортов нагрузки школы; маршрут зарезервирован для MVP 2."""

    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    rows = (
        db.query(ImportBatchModel)
        .filter_by(school_id=school_id)
        .order_by(ImportBatchModel.created_at.desc())
        .all()
    )
    return paginate([batch_dict(x) for x in rows], page_no, page_size)


@future_router.get("/schools/{school_id}/workload/imports/{import_id}")
def get_import(
    school_id: str,
    import_id: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает сведения и отчёт валидации выбранного импорта нагрузки MVP 2."""

    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    item = (
        db.query(ImportBatchModel).filter_by(id=import_id, school_id=school_id).first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Импорт не найден")
    return batch_dict(item)


@future_router.get("/schools/{school_id}/workload/imports/{import_id}/file")
def download_import(
    school_id: str,
    import_id: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Скачивает исходный XLSX выбранного импорта; маршрут зарезервирован для MVP 2."""

    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    item = (
        db.query(ImportBatchModel).filter_by(id=import_id, school_id=school_id).first()
    )
    if not item or not item.stored_file_key:
        raise HTTPException(status_code=404, detail="Файл не найден")
    path = (PRIVATE_UPLOAD_DIR / item.stored_file_key).resolve()
    if path.parent != PRIVATE_UPLOAD_DIR.resolve() or not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(
        path,
        filename=item.original_filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@future_router.get("/schools/{school_id}/teachers/{teacher_id}/norms")
def norms(
    school_id: str,
    teacher_id: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает историю нормативов преподавателя; маршрут зарезервирован для MVP 2."""

    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES | {"teacher"})
    require_teacher_access(db, user.id, school_id, teacher_id)
    get_teacher_in_school(db, school_id, teacher_id)
    return [
        {
            "id": n.id,
            "effective_from": n.effective_from,
            "effective_to": n.effective_to,
            "contract_teaching_hours_per_week": float(
                n.contract_teaching_hours_per_week
            ),
            "standard_teaching_hours_per_rate": float(
                n.standard_teaching_hours_per_rate
            ),
            "rate_fraction": float(
                n.contract_teaching_hours_per_week / n.standard_teaching_hours_per_rate
            ),
            "comment": n.comment,
            "plan_source": n.plan_source,
        }
        for n in db.query(TeacherWorkloadNormModel)
        .filter_by(teacher_id=teacher_id)
        .order_by(TeacherWorkloadNormModel.effective_from.desc())
    ]


def daily_rows_mvp2(
    db: Session,
    school_id: str,
    teacher_id: str | None,
    date_from: date | None,
    date_to: date | None,
    comments: bool,
) -> list[dict]:
    """MVP 2 FUTURE: combined plan/fact representation."""
    tq = db.query(TeacherModel).filter_by(school_id=school_id)
    if teacher_id:
        tq = tq.filter_by(id=teacher_id)
    teachers_by_id = {x.id: x for x in tq.all()}
    pq = (
        db.query(PlannedWorkItemModel)
        .join(WorkloadPlanVersionModel)
        .filter(
            WorkloadPlanVersionModel.school_id == school_id,
            WorkloadPlanVersionModel.status == "published",
            PlannedWorkItemModel.teacher_id.in_(teachers_by_id or [""]),
        )
    )
    aq = db.query(DailyWorkLogModel).filter(
        DailyWorkLogModel.teacher_id.in_(teachers_by_id or [""])
    )
    if date_from:
        pq = pq.filter(PlannedWorkItemModel.work_date >= date_from)
        aq = aq.filter(DailyWorkLogModel.work_date >= date_from)
    if date_to:
        pq = pq.filter(PlannedWorkItemModel.work_date <= date_to)
        aq = aq.filter(DailyWorkLogModel.work_date <= date_to)
    keyed = defaultdict(lambda: {"plan_items": [], "plan_version": -1, "actual": None})
    for item in pq.order_by(WorkloadPlanVersionModel.version).all():
        key = (item.teacher_id, item.work_date)
        version = item.plan_version.version
        if version > keyed[key]["plan_version"]:
            keyed[key]["plan_items"] = []
            keyed[key]["plan_version"] = version
        keyed[key]["plan_items"].append(item)
    for log in aq.all():
        keyed[(log.teacher_id, log.work_date)]["actual"] = log
    rows = []
    for (tid, _), values in keyed.items():
        from app.services.workload_service import daily_dict_mvp2

        row = daily_dict_mvp2(
            teachers_by_id[tid], values["plan_items"], values["actual"]
        )
        if row["actual"] and not comments:
            row["actual"].pop("comment", None)
        rows.append(row)
    return rows


def daily_rows(
    db: Session,
    school_id: str,
    teacher_id: str | None,
    date_from: date | None,
    date_to: date | None,
    comments: bool,
) -> list[dict]:
    """Return actual workload rows using MVP tables only."""
    teachers_query = db.query(TeacherModel).filter_by(school_id=school_id)
    if teacher_id:
        teachers_query = teachers_query.filter_by(id=teacher_id)
    teachers_by_id = {item.id: item for item in teachers_query.all()}
    logs = db.query(DailyWorkLogModel).filter(
        DailyWorkLogModel.teacher_id.in_(teachers_by_id or [""])
    )
    if date_from:
        logs = logs.filter(DailyWorkLogModel.work_date >= date_from)
    if date_to:
        logs = logs.filter(DailyWorkLogModel.work_date <= date_to)
    rows = [daily_dict(teachers_by_id[log.teacher_id], log) for log in logs.all()]
    if not comments:
        for row in rows:
            row["actual"].pop("comment", None)
    return rows


@router.post("/schools/{school_id}/workload/daily", status_code=201)
def create_daily_log(
    school_id: str,
    data: DailyWorkLogCreate,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Создаёт дневной журнал фактической нагрузки текущего преподавателя."""

    require_school_access(db, user.id, school_id, {"teacher"})
    teacher = require_own_teacher(db, user.id, school_id)

    if data.teacher_id != teacher.id:
        raise HTTPException(
            status_code=403, detail="Можно создавать нагрузку только для себя"
        )

    if (
        db.query(DailyWorkLogModel)
        .filter_by(teacher_id=teacher.id, work_date=data.work_date)
        .first()
    ):
        raise HTTPException(status_code=409, detail="Запись за эту дату уже существует")

    work_type_ids = {entry.work_type_id for entry in data.entries}

    valid_ids = {
        item.id
        for item in db.query(WorkTypeModel).filter(
            WorkTypeModel.id.in_(work_type_ids or [""]),
            WorkTypeModel.is_active.is_(True),
        )
    }

    if work_type_ids != valid_ids:
        raise HTTPException(
            status_code=422, detail="Неизвестный или архивный тип работы"
        )

    log = DailyWorkLogModel(
        teacher_id=teacher.id,
        work_date=data.work_date,
        day_type=data.day_type,
        status=data.status,
        comment=data.comment,
        completed_at=datetime.now(timezone.utc) if data.status == "completed" else None,
        completed_by=user.id if data.status == "completed" else None,
    )
    db.add(log)
    db.flush()

    for entry in data.entries:
        db.add(
            ActualWorkEntryModel(
                daily_log_id=log.id,
                created_by=user.id,
                updated_by=user.id,
                **entry.model_dump(),
            )
        )

    db.add(
        AuditEventModel(
            actor_id=user.id,
            action="create",
            entity_type="workload_daily_logs",
            entity_id=log.id,
            school_id=school_id,
            changes={"work_date": str(log.work_date), "entries": len(data.entries)},
        )
    )
    db.commit()
    db.refresh(log)

    return daily_dict(teacher, log)


@router.get("/schools/{school_id}/workload/daily")
def daily(
    school_id: str,
    teacher_id: str | None = None,
    date_from: date = Query(..., description="Дата отчёта или начало периода"),
    date_to: date | None = None,
    sort: str = "date_desc",
    page_no: int = Query(1, alias="page", ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает дневные записи и итоговый отчёт за выбранную дату или период."""

    require_school_access(db, user.id, school_id, FACT_ROLES)

    own_teacher_id = get_teacher_id_filter(db, user.id, school_id)

    teacher_id = own_teacher_id or teacher_id

    if teacher_id:
        get_teacher_in_school(db, school_id, teacher_id)

    if sort not in {"date_asc", "date_desc"}:
        raise HTTPException(status_code=422, detail="Недопустимая сортировка")

    report_date_to = date_to or date_from
    if date_from > report_date_to:
        raise HTTPException(status_code=422, detail="date_from позже date_to")

    rows = daily_rows(
        db,
        school_id,
        teacher_id,
        date_from,
        report_date_to,
        own_teacher_id is not None,
    )

    rows.sort(key=lambda x: x["work_date"], reverse=sort == "date_desc")

    result = paginate(rows, page_no, page_size)
    result.update(
        {
            "date_from": date_from,
            "date_to": report_date_to,
            "summary": {
                "actual_hours": sum(row["actual"]["total_hours"] or 0 for row in rows),
                "weekend_hours": sum(
                    row["actual"]["total_hours"] or 0
                    for row in rows
                    if date.fromisoformat(row["work_date"]).weekday() >= 5
                ),
                "observed_days": len(rows),
                "completed_days": sum(
                    1 for row in rows if row["actual"]["status"] == "completed"
                ),
            },
        }
    )
    return result


@router.patch("/schools/{school_id}/workload/daily/{record_id}")
def patch_actual(
    school_id: str,
    record_id: str,
    data: ActualPatch,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Изменяет собственный дневной журнал, его работы и состояние завершения."""

    require_school_access(db, user.id, school_id, {"teacher"})

    own_teacher = require_own_teacher(db, user.id, school_id)

    log = (
        db.query(DailyWorkLogModel)
        .join(TeacherModel)
        .filter(
            DailyWorkLogModel.id == record_id,
            TeacherModel.school_id == school_id,
        )
        .first()
    )

    if not log or log.teacher_id != own_teacher.id:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    if if_match and if_match.strip('"') != str(log.updated_at.timestamp()):
        raise HTTPException(status_code=409, detail="Запись изменилась")

    changes = data.model_dump(exclude_unset=True, exclude={"entries"})

    old = {key: str(getattr(log, key)) for key in changes}

    for key, value in changes.items():
        setattr(log, key, value)

    if data.entries is not None:
        work_type_ids = {entry.work_type_id for entry in data.entries}

        valid_ids = {
            item.id
            for item in db.query(WorkTypeModel).filter(
                WorkTypeModel.id.in_(work_type_ids or [""]),
                WorkTypeModel.is_active.is_(True),
            )
        }

        if work_type_ids != valid_ids:
            raise HTTPException(
                status_code=422, detail="Неизвестный или архивный тип работы"
            )

        db.query(ActualWorkEntryModel).filter_by(daily_log_id=log.id).delete(
            synchronize_session=False
        )

        for entry in data.entries:
            values = entry.model_dump()
            db.add(
                ActualWorkEntryModel(
                    daily_log_id=log.id,
                    created_by=user.id,
                    updated_by=user.id,
                    **values,
                )
            )

    if log.status == "completed":
        log.completed_at = datetime.now(timezone.utc)
        log.completed_by = user.id
    else:
        log.completed_at = None
        log.completed_by = None

    db.add(
        AuditEventModel(
            actor_id=user.id,
            action="update",
            entity_type="workload_daily_logs",
            entity_id=log.id,
            school_id=school_id,
            changes={"old": old, "fields": list(data.model_fields_set)},
        )
    )
    db.commit()

    rows = daily_rows(db, school_id, log.teacher_id, log.work_date, log.work_date, True)

    return rows[0]


def make_workbook(
    db: Session,
    school_id: str,
    teacher_id: str | None,
    date_from: date | None,
    date_to: date | None,
    include_data: bool = True,
    include_actual: bool = True,
):
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    sheets = [
        ("Учителя_нормы", NORM_HEADERS),
        ("План_дня", PLAN_HEADERS),
        ("Ежедневный_учет", ACTUAL_HEADERS),
    ]
    if not include_actual:
        sheets = sheets[:2]
    for name, mapping in sheets:
        ws = wb.create_sheet(name)
        ws.append(["Шаблон нагрузки 1.0"])
        ws.append([])
        ws.append([])
        ws.append(list(mapping.keys()))
    if include_data:
        teachers_q = db.query(TeacherModel).filter_by(school_id=school_id)
        if teacher_id:
            teachers_q = teachers_q.filter_by(id=teacher_id)
        teachers = teachers_q.all()
        for teacher in teachers:
            norm = (
                db.query(TeacherWorkloadNormModel)
                .filter_by(teacher_id=teacher.id)
                .order_by(TeacherWorkloadNormModel.effective_from.desc())
                .first()
            )
            if norm:
                values = {
                    "external_id": teacher.external_id,
                    "subject": teacher.subject,
                    "contract_teaching_hours_per_week": norm.contract_teaching_hours_per_week,
                    "standard_teaching_hours_per_rate": norm.standard_teaching_hours_per_rate,
                    "comment": norm.comment,
                    "plan_source": norm.plan_source,
                }
                wb["Учителя_нормы"].append(
                    [values.get(field) for field in NORM_HEADERS.values()]
                )
        rows = daily_rows_mvp2(db, school_id, teacher_id, date_from, date_to, True)
        workload_sources = [("План_дня", PLAN_HEADERS, "plan")]
        if include_actual:
            workload_sources.append(("Ежедневный_учет", ACTUAL_HEADERS, "actual"))
        for name, mapping, section in workload_sources:
            for item in rows:
                if item[section] is None:
                    continue
                values = {
                    "external_id": item["external_teacher_id"],
                    "work_date": item["work_date"],
                    "day_type": item["day_type"],
                    **item[section],
                }
                row = []
                for field in mapping.values():
                    value = values.get(field)
                    if field in ACADEMIC_HOUR_FIELDS and value is not None:
                        value = to_teaching_hours(Decimal(value))
                    if isinstance(value, Decimal):
                        value = float(value)
                    if isinstance(value, str) and value.lstrip().startswith(
                        ("=", "+", "-", "@")
                    ):
                        value = "'" + value
                    row.append(value)
                wb[name].append(row)
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


@future_router.get("/schools/{school_id}/workload/exports")
def export_workload(
    school_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
    teacher_id: str | None = None,
    report: str = "full",
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Выгружает разрешённые данные нагрузки в XLSX; маршрут зарезервирован для MVP 2."""

    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES | {"teacher"})
    teacher_id = get_teacher_id_filter(db, user.id, school_id) or teacher_id
    roles = user_role_codes(db, user.id)
    include_actual = not roles.isdisjoint({"teacher", "head", "group_head"})
    output = make_workbook(
        db, school_id, teacher_id, date_from, date_to, include_actual=include_actual
    )
    db.add(
        AuditEventModel(
            actor_id=user.id,
            action="export",
            entity_type="workload",
            school_id=school_id,
            purpose=report,
            changes={"date_from": str(date_from), "date_to": str(date_to)},
        )
    )
    db.commit()
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="teacher_workload_{date.today():%Y%m%d}.xlsx"'
        },
    )


@future_router.get("/schools/{school_id}/workload/template")
def workload_template(
    school_id: str,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Возвращает пустой XLSX-шаблон нагрузки; маршрут зарезервирован для MVP 2."""

    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    return StreamingResponse(
        make_workbook(db, school_id, None, None, None, False),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="teacher_workload_template_1.0.xlsx"'
        },
    )
