import io
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import MAX_UPLOAD_BYTES, PRIVATE_UPLOAD_DIR
from app.core.security import get_current_user
from app.core.work_duration import to_teaching_hours
from app.core.access import (
    FACT_ROLES,
    PLAN_MANAGER_ROLES,
    assign_role,
    get_teacher_in_school,
    require_school_access,
    require_teacher_access,
    require_own_teacher,
    find_user_teacher_in_school,
    get_teacher_id_filter,
    user_role_codes,
)
from app.db.database import get_db
from app.models.access import UserSchoolAccessModel
from app.models.audit import AuditEventModel
from app.models.import_batch import ImportBatchModel
from app.models.organization import SchoolModel
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
from app.schemas.access import AccessCreate
from app.schemas.analytics import PlannedDashboardOut
from app.schemas.organization import SchoolCreate
from app.schemas.teacher import TeacherCreate
from app.schemas.work_type import WorkTypeCreate, WorkTypeOut, WorkTypeUpdate
from app.schemas.workload import ActualPatch
from app.services.analytics_service import get_planned_dashboard
from app.services.work_type_service import archive_work_type, create_work_type, list_work_types, update_work_type
from app.services.workload_service import (
    ACADEMIC_HOUR_FIELDS, ACTUAL_HEADERS, NORM_HEADERS, PLAN_HEADERS,
    daily_dict, import_workbook, parse_workbook, validation_report,
)


router = APIRouter(prefix="/api/v1", tags=["Teacher workload"])
WORK_TYPE_EDITOR_ROLES = {"head", "group_head", "system_admin"}


def page(items: list, page_no: int, page_size: int) -> dict:
    start = (page_no - 1) * page_size
    return {"page": page_no, "page_size": page_size, "total": len(items), "items": items[start:start + page_size]}


def batch_dict(item: ImportBatchModel) -> dict:
    return {"id": item.id, "school_id": item.school_id, "original_filename": item.original_filename, "sha256": item.sha256, "status": item.status, "mode": item.mode, "effective_from": item.effective_from, "rows_total": item.rows_total, "rows_created": item.rows_created, "rows_updated": item.rows_updated, "rows_skipped": item.rows_skipped, "validation_report": item.validation_report, "imported_at": item.imported_at}


@router.get("/dashboard/planned", response_model=PlannedDashboardOut)
def planned_dashboard(
    school_id: str,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    try:
        return get_planned_dashboard(db, {school_id}, date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/work-types", response_model=list[WorkTypeOut])
def work_types(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    roles = user_role_codes(db, user.id)
    if roles.isdisjoint({"teacher", "director", "head", "group_head", "system_admin"}):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    if include_archived and roles.isdisjoint(WORK_TYPE_EDITOR_ROLES):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return list_work_types(db, include_archived=include_archived)


@router.post("/work-types", response_model=WorkTypeOut, status_code=201)
def add_work_type(data: WorkTypeCreate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    if user_role_codes(db, user.id).isdisjoint(WORK_TYPE_EDITOR_ROLES):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return create_work_type(db, data, user.id)


@router.patch("/work-types/{work_type_id}", response_model=WorkTypeOut)
def edit_work_type(work_type_id: str, data: WorkTypeUpdate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    if user_role_codes(db, user.id).isdisjoint(WORK_TYPE_EDITOR_ROLES):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return update_work_type(db, work_type_id, data, user.id)


@router.post("/work-types/{work_type_id}/archive", response_model=WorkTypeOut)
def remove_work_type(work_type_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    if user_role_codes(db, user.id).isdisjoint(WORK_TYPE_EDITOR_ROLES):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return archive_work_type(db, work_type_id, user.id)


@router.post("/schools", status_code=201)
def create_school(data: SchoolCreate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    school = SchoolModel(name=data.name.strip(), external_code=data.external_code)
    db.add(school); db.flush()
    db.add(UserSchoolAccessModel(user_id=user.id, school_id=school.id))
    assign_role(db, user.id, "director")
    db.commit(); db.refresh(school)
    return {"id": school.id, "name": school.name, "external_code": school.external_code}


@router.post("/schools/{school_id}/teachers", status_code=201)
def create_teacher(school_id: str, data: TeacherCreate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"system_admin"})
    if db.query(TeacherModel).filter_by(school_id=school_id, external_id=data.external_id).first(): raise HTTPException(status_code=409, detail="Такой external_id уже есть")
    if data.user_id is not None and not db.query(UserModel).filter_by(id=data.user_id).first(): raise HTTPException(status_code=404, detail="Пользователь не найден")
    item = TeacherModel(school_id=school_id, **data.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "external_id": item.external_id, "subject": item.subject, "is_active": item.is_active}


@router.post("/schools/{school_id}/access", status_code=201)
def create_access(school_id: str, data: AccessCreate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"system_admin"})
    if not db.query(UserModel).filter_by(id=data.user_id).first(): raise HTTPException(status_code=404, detail="Пользователь не найден")
    if data.role == "teacher" and find_user_teacher_in_school(db, data.user_id, school_id) is None:
        raise HTTPException(status_code=422, detail="Сначала свяжите учётную запись с педагогом через teachers.user_id")
    if db.query(UserSchoolAccessModel).filter_by(user_id=data.user_id, school_id=school_id).first(): raise HTTPException(status_code=409, detail="Доступ уже настроен")
    values = data.model_dump(exclude={"role"})
    item = UserSchoolAccessModel(school_id=school_id, **values)
    db.add(item); assign_role(db, data.user_id, data.role); db.commit(); db.refresh(item)
    return {"id": item.id, "user_id": item.user_id, "school_id": item.school_id, "role": data.role}


async def read_xlsx(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Допустим только .xlsx")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES: raise HTTPException(status_code=413, detail="Файл слишком большой")
    if not data.startswith(b"PK"): raise HTTPException(status_code=400, detail="Файл не является XLSX")
    return data


@router.post("/schools/{school_id}/workload/imports/validate")
async def validate_import(school_id: str, file: UploadFile = File(...), effective_from: date = Form(...), mode: str = Form("insert_only"), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    if mode not in {"insert_only", "upsert"}: raise HTTPException(status_code=422, detail="replace_period ещё не поддерживается")
    content = await read_xlsx(file)
    return validation_report(db, school_id, parse_workbook(content), mode, effective_from)


@router.post("/schools/{school_id}/workload/imports", status_code=201)
async def create_import(school_id: str, file: UploadFile = File(...), effective_from: date = Form(...), mode: str = Form("insert_only"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    if mode not in {"insert_only", "upsert"}: raise HTTPException(status_code=422, detail="replace_period ещё не поддерживается")
    content = await read_xlsx(file)
    PRIVATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    import hashlib
    digest = hashlib.sha256(content).hexdigest()
    path = PRIVATE_UPLOAD_DIR / f"{school_id}_{digest}.xlsx"
    path.write_bytes(content)
    try:
        item = import_workbook(db, school_id, content, file.filename or "upload.xlsx", mode, effective_from, user.id, path.name)
    except Exception:
        db.rollback()
        if not db.query(ImportBatchModel).filter_by(school_id=school_id, sha256=digest).first() and path.exists(): path.unlink()
        raise
    return batch_dict(item)


@router.get("/schools/{school_id}/workload/imports")
def list_imports(school_id: str, page_no: int = Query(1, alias="page", ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    rows = db.query(ImportBatchModel).filter_by(school_id=school_id).order_by(ImportBatchModel.created_at.desc()).all()
    return page([batch_dict(x) for x in rows], page_no, page_size)


@router.get("/schools/{school_id}/workload/imports/{import_id}")
def get_import(school_id: str, import_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    item = db.query(ImportBatchModel).filter_by(id=import_id, school_id=school_id).first()
    if not item: raise HTTPException(status_code=404, detail="Импорт не найден")
    return batch_dict(item)


@router.get("/schools/{school_id}/workload/imports/{import_id}/file")
def download_import(school_id: str, import_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    item = db.query(ImportBatchModel).filter_by(id=import_id, school_id=school_id).first()
    if not item or not item.stored_file_key: raise HTTPException(status_code=404, detail="Файл не найден")
    path = (PRIVATE_UPLOAD_DIR / item.stored_file_key).resolve()
    if path.parent != PRIVATE_UPLOAD_DIR.resolve() or not path.exists(): raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=item.original_filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/schools/{school_id}/teachers")
def teachers(school_id: str, subject: str | None = None, page_no: int = Query(1, alias="page", ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES | {"teacher"})
    query = db.query(TeacherModel).filter_by(school_id=school_id)
    own_teacher_id = get_teacher_id_filter(db, user.id, school_id)
    if own_teacher_id: query = query.filter_by(id=own_teacher_id)
    if subject: query = query.filter(TeacherModel.subject == subject)
    result = []
    for teacher in query.order_by(TeacherModel.external_id).all():
        norm = db.query(TeacherWorkloadNormModel).filter_by(teacher_id=teacher.id).filter(TeacherWorkloadNormModel.effective_to.is_(None)).first()
        result.append({"id": teacher.id, "external_id": teacher.external_id, "subject": teacher.subject, "is_active": teacher.is_active, "current_norm": None if not norm else {"effective_from": norm.effective_from, "contract_teaching_hours_per_week": float(norm.contract_teaching_hours_per_week), "standard_teaching_hours_per_rate": float(norm.standard_teaching_hours_per_rate), "rate_fraction": float(norm.contract_teaching_hours_per_week / norm.standard_teaching_hours_per_rate)}})
    return page(result, page_no, page_size)


@router.get("/schools/{school_id}/teachers/{teacher_id}/norms")
def norms(school_id: str, teacher_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES | {"teacher"}); require_teacher_access(db, user.id, school_id, teacher_id); get_teacher_in_school(db, school_id, teacher_id)
    return [{"id": n.id, "effective_from": n.effective_from, "effective_to": n.effective_to, "contract_teaching_hours_per_week": float(n.contract_teaching_hours_per_week), "standard_teaching_hours_per_rate": float(n.standard_teaching_hours_per_rate), "rate_fraction": float(n.contract_teaching_hours_per_week / n.standard_teaching_hours_per_rate), "comment": n.comment, "plan_source": n.plan_source} for n in db.query(TeacherWorkloadNormModel).filter_by(teacher_id=teacher_id).order_by(TeacherWorkloadNormModel.effective_from.desc())]


def daily_rows(db: Session, school_id: str, teacher_id: str | None, date_from: date | None, date_to: date | None, comments: bool) -> list[dict]:
    tq = db.query(TeacherModel).filter_by(school_id=school_id)
    if teacher_id: tq = tq.filter_by(id=teacher_id)
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
    aq = db.query(DailyWorkLogModel).filter(DailyWorkLogModel.teacher_id.in_(teachers_by_id or [""]))
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
        row = daily_dict(teachers_by_id[tid], values["plan_items"], values["actual"])
        if row["actual"] and not comments: row["actual"].pop("comment", None)
        rows.append(row)
    return rows


@router.get("/schools/{school_id}/workload/daily")
def daily(school_id: str, teacher_id: str | None = None, date_from: date | None = None, date_to: date | None = None, sort: str = "date_desc", page_no: int = Query(1, alias="page", ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, FACT_ROLES)
    own_teacher_id = get_teacher_id_filter(db, user.id, school_id)
    teacher_id = own_teacher_id or teacher_id
    if teacher_id: get_teacher_in_school(db, school_id, teacher_id)
    if sort not in {"date_asc", "date_desc"}: raise HTTPException(status_code=422, detail="Недопустимая сортировка")
    rows = daily_rows(db, school_id, teacher_id, date_from, date_to, own_teacher_id is not None)
    rows.sort(key=lambda x: x["work_date"], reverse=sort == "date_desc")
    return page(rows, page_no, page_size)


@router.get("/schools/{school_id}/workload/weekly")
def weekly(school_id: str, teacher_id: str | None = None, week_from: date | None = None, week_to: date | None = None, page_no: int = Query(1, alias="page", ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, FACT_ROLES)
    teacher_id = get_teacher_id_filter(db, user.id, school_id) or teacher_id
    rows = daily_rows(db, school_id, teacher_id, week_from, week_to, False)
    grouped = defaultdict(list)
    for row in rows: grouped[(row["teacher_id"], row["metrics"]["week_start"])].append(row)
    result = []
    for (tid, week), group in grouped.items():
        plans = [r["plan"]["total_hours"] for r in group if r["plan"] and r["plan"]["total_hours"] is not None]
        actuals = [r["actual"]["total_hours"] for r in group if r["actual"] and r["actual"]["total_hours"] is not None]
        p, a = (sum(plans) if plans else None), (sum(actuals) if actuals else None)
        weekend = sum(r["actual"]["total_hours"] or 0 for r in group if r["actual"] and date.fromisoformat(r["work_date"]).weekday() >= 5)
        result.append({"teacher_id": tid, "week_start": week, "planned_hours": p, "actual_hours": a, "deviation_hours": a - p if a is not None and p is not None else None, "actual_to_plan_ratio": a / p if a is not None and p else None, "weekend_hours": weekend, "observed_days": len(actuals), "expected_days": None, "completion_rate": None, "completion_status": "not_assessed", "has_missing_plan": len(plans) < len(group), "has_missing_actual": len(actuals) < len(group)})
    result.sort(key=lambda x: x["week_start"], reverse=True)
    return page(result, page_no, page_size)


@router.patch("/schools/{school_id}/workload/daily/{record_id}")
def patch_actual(school_id: str, record_id: str, data: ActualPatch, if_match: str | None = Header(default=None, alias="If-Match"), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"teacher"})
    own_teacher = require_own_teacher(db, user.id, school_id)
    log = db.query(DailyWorkLogModel).join(TeacherModel).filter(
        DailyWorkLogModel.id == record_id,
        TeacherModel.school_id == school_id,
    ).first()
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
            raise HTTPException(status_code=422, detail="Неизвестный или архивный тип работы")
        db.query(ActualWorkEntryModel).filter_by(daily_log_id=log.id).delete(synchronize_session=False)
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
    db.add(AuditEventModel(actor_id=user.id, action="update", entity_type="daily_work_logs", entity_id=log.id, school_id=school_id, changes={"old": old, "fields": list(data.model_fields_set)}))
    db.commit()
    rows = daily_rows(db, school_id, log.teacher_id, log.work_date, log.work_date, True)
    return rows[0]


def make_workbook(db: Session, school_id: str, teacher_id: str | None, date_from: date | None, date_to: date | None, include_data: bool = True, include_actual: bool = True):
    from openpyxl import Workbook
    wb = Workbook(); wb.remove(wb.active)
    sheets = [("Учителя_нормы", NORM_HEADERS), ("План_дня", PLAN_HEADERS), ("Ежедневный_учет", ACTUAL_HEADERS)]
    if not include_actual:
        sheets = sheets[:2]
    for name, mapping in sheets:
        ws = wb.create_sheet(name); ws.append(["Шаблон нагрузки 1.0"]); ws.append([]); ws.append([]); ws.append(list(mapping.keys()))
    if include_data:
        teachers_q = db.query(TeacherModel).filter_by(school_id=school_id)
        if teacher_id: teachers_q = teachers_q.filter_by(id=teacher_id)
        teachers = teachers_q.all()
        for teacher in teachers:
            norm = db.query(TeacherWorkloadNormModel).filter_by(teacher_id=teacher.id).order_by(TeacherWorkloadNormModel.effective_from.desc()).first()
            if norm:
                values = {"external_id": teacher.external_id, "subject": teacher.subject, "contract_teaching_hours_per_week": norm.contract_teaching_hours_per_week, "standard_teaching_hours_per_rate": norm.standard_teaching_hours_per_rate, "comment": norm.comment, "plan_source": norm.plan_source}
                wb["Учителя_нормы"].append([values.get(field) for field in NORM_HEADERS.values()])
        rows = daily_rows(db, school_id, teacher_id, date_from, date_to, True)
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
                    if isinstance(value, Decimal): value = float(value)
                    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")): value = "'" + value
                    row.append(value)
                wb[name].append(row)
    output = io.BytesIO(); wb.save(output); output.seek(0); return output


@router.get("/schools/{school_id}/workload/exports")
def export_workload(school_id: str, date_from: date | None = None, date_to: date | None = None, teacher_id: str | None = None, report: str = "full", db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES | {"teacher"})
    teacher_id = get_teacher_id_filter(db, user.id, school_id) or teacher_id
    roles = user_role_codes(db, user.id)
    include_actual = not roles.isdisjoint({"teacher", "head", "group_head"})
    output = make_workbook(db, school_id, teacher_id, date_from, date_to, include_actual=include_actual)
    db.add(AuditEventModel(actor_id=user.id, action="export", entity_type="workload", school_id=school_id, purpose=report, changes={"date_from": str(date_from), "date_to": str(date_to)})); db.commit()
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="teacher_workload_{date.today():%Y%m%d}.xlsx"'})


@router.get("/schools/{school_id}/workload/template")
def workload_template(school_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, PLAN_MANAGER_ROLES)
    return StreamingResponse(make_workbook(db, school_id, None, None, None, False), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="teacher_workload_template_1.0.xlsx"'})
