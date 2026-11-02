import io
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import MAX_UPLOAD_BYTES, PRIVATE_UPLOAD_DIR
from app.core.security import get_current_user
from app.core.teacher_access import MANAGER_ROLES, get_teacher_in_school, require_school_access, require_teacher_scope
from app.db.database import get_db
from app.models.teacher_domain import (
    AuditEventModel, DailyWorkloadActualModel, DailyWorkloadPlanModel, ImportBatchModel,
    SchoolModel, TeacherModel, TeacherWorkloadNormModel, UserSchoolAccessModel,
)
from app.models.user import UserModel
from app.services.workload_service import (
    ACTUAL_HEADERS, ASTRO, NORM_HEADERS, PLAN_HEADERS, daily_dict, import_workbook,
    parse_workbook, total, validation_report,
)


router = APIRouter(prefix="/api/v1", tags=["Teacher workload"])


class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    external_code: str | None = Field(default=None, max_length=80)


class ActualPatch(BaseModel):
    day_type: str | None = None
    actual_lessons_teaching_hours: Decimal | None = Field(default=None, ge=0)
    actual_substitutions_teaching_hours: Decimal | None = Field(default=None, ge=0)
    actual_teaching_block_hours: Decimal | None = Field(default=None, ge=0)
    actual_preparation_hours: Decimal | None = Field(default=None, ge=0)
    actual_grading_hours: Decimal | None = Field(default=None, ge=0)
    actual_documentation_hours: Decimal | None = Field(default=None, ge=0)
    actual_parent_communication_hours: Decimal | None = Field(default=None, ge=0)
    actual_class_management_hours: Decimal | None = Field(default=None, ge=0)
    actual_meetings_methodology_hours: Decimal | None = Field(default=None, ge=0)
    actual_other_hours: Decimal | None = Field(default=None, ge=0)
    at_school_hours: Decimal | None = Field(default=None, ge=0)
    at_home_hours: Decimal | None = Field(default=None, ge=0)
    fatigue_score: int | None = Field(default=None, ge=1, le=5)
    stress_score: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=3000)


class TeacherCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=80)
    subject: str = Field(min_length=1, max_length=150)
    full_name: str | None = Field(default=None, max_length=255)


class AccessCreate(BaseModel):
    user_id: int
    role: str = Field(pattern="^(admin|analyst|teacher|survey_manager|researcher|privacy_officer)$")
    teacher_id: str | None = None
    can_read_comments: bool = False
    can_export_research: bool = False


def page(items: list, page_no: int, page_size: int) -> dict:
    start = (page_no - 1) * page_size
    return {"page": page_no, "page_size": page_size, "total": len(items), "items": items[start:start + page_size]}


def batch_dict(item: ImportBatchModel) -> dict:
    return {"id": item.id, "school_id": item.school_id, "original_filename": item.original_filename, "sha256": item.sha256, "status": item.status, "mode": item.mode, "effective_from": item.effective_from, "rows_total": item.rows_total, "rows_created": item.rows_created, "rows_updated": item.rows_updated, "rows_skipped": item.rows_skipped, "validation_report": item.validation_report, "imported_at": item.imported_at}


@router.post("/schools", status_code=201)
def create_school(data: SchoolCreate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    school = SchoolModel(name=data.name.strip(), external_code=data.external_code)
    db.add(school); db.flush()
    db.add(UserSchoolAccessModel(user_id=user.id, school_id=school.id, role="admin", can_read_comments=False, can_export_research=False))
    db.commit(); db.refresh(school)
    return {"id": school.id, "name": school.name, "external_code": school.external_code}


@router.post("/schools/{school_id}/teachers", status_code=201)
def create_teacher(school_id: str, data: TeacherCreate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"admin"})
    if db.query(TeacherModel).filter_by(school_id=school_id, external_id=data.external_id).first(): raise HTTPException(status_code=409, detail="Такой external_id уже есть")
    item = TeacherModel(school_id=school_id, **data.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "external_id": item.external_id, "subject": item.subject, "is_active": item.is_active}


@router.post("/schools/{school_id}/access", status_code=201)
def create_access(school_id: str, data: AccessCreate, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"admin"})
    if not db.query(UserModel).filter_by(id=data.user_id).first(): raise HTTPException(status_code=404, detail="Пользователь не найден")
    if data.role == "teacher":
        if not data.teacher_id: raise HTTPException(status_code=422, detail="teacher_id обязателен")
        get_teacher_in_school(db, school_id, data.teacher_id)
    if db.query(UserSchoolAccessModel).filter_by(user_id=data.user_id, school_id=school_id).first(): raise HTTPException(status_code=409, detail="Доступ уже настроен")
    item = UserSchoolAccessModel(school_id=school_id, **data.model_dump()); db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "user_id": item.user_id, "school_id": item.school_id, "role": item.role, "teacher_id": item.teacher_id}


async def read_xlsx(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Допустим только .xlsx")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES: raise HTTPException(status_code=413, detail="Файл слишком большой")
    if not data.startswith(b"PK"): raise HTTPException(status_code=400, detail="Файл не является XLSX")
    return data


@router.post("/schools/{school_id}/workload/imports/validate")
async def validate_import(school_id: str, file: UploadFile = File(...), effective_from: date = Form(...), mode: str = Form("insert_only"), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"admin"})
    if mode not in {"insert_only", "upsert"}: raise HTTPException(status_code=422, detail="replace_period ещё не поддерживается")
    content = await read_xlsx(file)
    return validation_report(db, school_id, parse_workbook(content), mode, effective_from)


@router.post("/schools/{school_id}/workload/imports", status_code=201)
async def create_import(school_id: str, file: UploadFile = File(...), effective_from: date = Form(...), mode: str = Form("insert_only"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"admin"})
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
    require_school_access(db, user.id, school_id, MANAGER_ROLES)
    rows = db.query(ImportBatchModel).filter_by(school_id=school_id).order_by(ImportBatchModel.created_at.desc()).all()
    return page([batch_dict(x) for x in rows], page_no, page_size)


@router.get("/schools/{school_id}/workload/imports/{import_id}")
def get_import(school_id: str, import_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, MANAGER_ROLES)
    item = db.query(ImportBatchModel).filter_by(id=import_id, school_id=school_id).first()
    if not item: raise HTTPException(status_code=404, detail="Импорт не найден")
    return batch_dict(item)


@router.get("/schools/{school_id}/workload/imports/{import_id}/file")
def download_import(school_id: str, import_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"admin"})
    item = db.query(ImportBatchModel).filter_by(id=import_id, school_id=school_id).first()
    if not item or not item.stored_file_key: raise HTTPException(status_code=404, detail="Файл не найден")
    path = (PRIVATE_UPLOAD_DIR / item.stored_file_key).resolve()
    if path.parent != PRIVATE_UPLOAD_DIR.resolve() or not path.exists(): raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, filename=item.original_filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/schools/{school_id}/teachers")
def teachers(school_id: str, subject: str | None = None, page_no: int = Query(1, alias="page", ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    access = require_school_access(db, user.id, school_id)
    query = db.query(TeacherModel).filter_by(school_id=school_id)
    if access.role == "teacher": query = query.filter_by(id=access.teacher_id)
    if subject: query = query.filter(TeacherModel.subject == subject)
    result = []
    for teacher in query.order_by(TeacherModel.external_id).all():
        norm = db.query(TeacherWorkloadNormModel).filter_by(teacher_id=teacher.id).filter(TeacherWorkloadNormModel.effective_to.is_(None)).first()
        result.append({"id": teacher.id, "external_id": teacher.external_id, "subject": teacher.subject, "is_active": teacher.is_active, "current_norm": None if not norm else {"effective_from": norm.effective_from, "contract_teaching_hours_per_week": float(norm.contract_teaching_hours_per_week), "standard_teaching_hours_per_rate": float(norm.standard_teaching_hours_per_rate), "rate_fraction": float(norm.contract_teaching_hours_per_week / norm.standard_teaching_hours_per_rate)}})
    return page(result, page_no, page_size)


@router.get("/schools/{school_id}/teachers/{teacher_id}/norms")
def norms(school_id: str, teacher_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    access = require_school_access(db, user.id, school_id); require_teacher_scope(access, teacher_id); get_teacher_in_school(db, school_id, teacher_id)
    return [{"id": n.id, "effective_from": n.effective_from, "effective_to": n.effective_to, "contract_teaching_hours_per_week": float(n.contract_teaching_hours_per_week), "standard_teaching_hours_per_rate": float(n.standard_teaching_hours_per_rate), "rate_fraction": float(n.contract_teaching_hours_per_week / n.standard_teaching_hours_per_rate), "comment": n.comment, "plan_source": n.plan_source} for n in db.query(TeacherWorkloadNormModel).filter_by(teacher_id=teacher_id).order_by(TeacherWorkloadNormModel.effective_from.desc())]


def daily_rows(db: Session, school_id: str, teacher_id: str | None, date_from: date | None, date_to: date | None, comments: bool) -> list[dict]:
    tq = db.query(TeacherModel).filter_by(school_id=school_id)
    if teacher_id: tq = tq.filter_by(id=teacher_id)
    teachers_by_id = {x.id: x for x in tq.all()}
    pq = db.query(DailyWorkloadPlanModel).filter(DailyWorkloadPlanModel.teacher_id.in_(teachers_by_id or [""]))
    aq = db.query(DailyWorkloadActualModel).filter(DailyWorkloadActualModel.teacher_id.in_(teachers_by_id or [""]))
    for q in (pq, aq):
        pass
    if date_from: pq = pq.filter(DailyWorkloadPlanModel.work_date >= date_from); aq = aq.filter(DailyWorkloadActualModel.work_date >= date_from)
    if date_to: pq = pq.filter(DailyWorkloadPlanModel.work_date <= date_to); aq = aq.filter(DailyWorkloadActualModel.work_date <= date_to)
    keyed = defaultdict(dict)
    for p in pq.all(): keyed[(p.teacher_id, p.work_date)]["plan"] = p
    for a in aq.all(): keyed[(a.teacher_id, a.work_date)]["actual"] = a
    rows = []
    for (tid, _), values in keyed.items():
        row = daily_dict(teachers_by_id[tid], values.get("plan"), values.get("actual"))
        if row["actual"] and not comments: row["actual"].pop("comment", None)
        rows.append(row)
    return rows


@router.get("/schools/{school_id}/workload/daily")
def daily(school_id: str, teacher_id: str | None = None, date_from: date | None = None, date_to: date | None = None, sort: str = "date_desc", page_no: int = Query(1, alias="page", ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    access = require_school_access(db, user.id, school_id)
    if access.role == "teacher": teacher_id = access.teacher_id
    if teacher_id: get_teacher_in_school(db, school_id, teacher_id)
    if sort not in {"date_asc", "date_desc"}: raise HTTPException(status_code=422, detail="Недопустимая сортировка")
    rows = daily_rows(db, school_id, teacher_id, date_from, date_to, access.can_read_comments)
    rows.sort(key=lambda x: x["work_date"], reverse=sort == "date_desc")
    return page(rows, page_no, page_size)


@router.get("/schools/{school_id}/workload/weekly")
def weekly(school_id: str, teacher_id: str | None = None, week_from: date | None = None, week_to: date | None = None, page_no: int = Query(1, alias="page", ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    access = require_school_access(db, user.id, school_id)
    if access.role == "teacher": teacher_id = access.teacher_id
    rows = daily_rows(db, school_id, teacher_id, week_from, week_to, False)
    grouped = defaultdict(list)
    for row in rows: grouped[(row["teacher_id"], row["metrics"]["week_start"])].append(row)
    result = []
    for (tid, week), group in grouped.items():
        plans = [r["plan"]["total_hours"] for r in group if r["plan"] and r["plan"]["total_hours"] is not None]
        actuals = [r["actual"]["total_hours"] for r in group if r["actual"] and r["actual"]["total_hours"] is not None]
        fatigue = [r["actual"]["fatigue_score"] for r in group if r["actual"] and r["actual"].get("fatigue_score") is not None]
        stress = [r["actual"]["stress_score"] for r in group if r["actual"] and r["actual"].get("stress_score") is not None]
        p, a = (sum(plans) if plans else None), (sum(actuals) if actuals else None)
        weekend = sum(r["actual"]["total_hours"] or 0 for r in group if r["actual"] and date.fromisoformat(r["work_date"]).weekday() >= 5)
        result.append({"teacher_id": tid, "week_start": week, "planned_hours": p, "actual_hours": a, "deviation_hours": a - p if a is not None and p is not None else None, "actual_to_plan_ratio": a / p if a is not None and p else None, "weekend_hours": weekend, "fatigue_mean": sum(fatigue) / len(fatigue) if fatigue else None, "stress_mean": sum(stress) / len(stress) if stress else None, "observed_days": len(actuals), "expected_days": None, "completion_rate": None, "completion_status": "not_assessed", "has_missing_plan": len(plans) < len(group), "has_missing_actual": len(actuals) < len(group)})
    result.sort(key=lambda x: x["week_start"], reverse=True)
    return page(result, page_no, page_size)


@router.patch("/schools/{school_id}/workload/daily/{record_id}")
def patch_actual(school_id: str, record_id: str, data: ActualPatch, if_match: str | None = Header(default=None, alias="If-Match"), db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id, {"admin"})
    record = db.query(DailyWorkloadActualModel).join(TeacherModel).filter(DailyWorkloadActualModel.id == record_id, TeacherModel.school_id == school_id).first()
    if not record: raise HTTPException(status_code=404, detail="Запись не найдена")
    if if_match and if_match.strip('"') != str(record.updated_at.timestamp()): raise HTTPException(status_code=409, detail="Запись изменилась")
    changes = data.model_dump(exclude_unset=True)
    old = {k: str(getattr(record, k)) for k in changes}
    for k, v in changes.items(): setattr(record, k, v)
    atotal, complete = total(record, "actual")
    if complete and record.at_school_hours is not None and record.at_home_hours is not None and abs(Decimal(record.at_school_hours) + Decimal(record.at_home_hours) - atotal) > Decimal("0.05"):
        raise HTTPException(status_code=422, detail="Сумма работы в школе и дома не совпадает с фактом")
    db.add(AuditEventModel(actor_id=user.id, action="update", entity_type="daily_workload_actuals", entity_id=record.id, school_id=school_id, changes={"old": old, "fields": list(changes)})); db.commit()
    teacher = get_teacher_in_school(db, school_id, record.teacher_id)
    plan_record = db.query(DailyWorkloadPlanModel).filter_by(teacher_id=record.teacher_id, work_date=record.work_date).first()
    return daily_dict(teacher, plan_record, record)


def make_workbook(db: Session, school_id: str, teacher_id: str | None, date_from: date | None, date_to: date | None, include_data: bool = True):
    from openpyxl import Workbook
    wb = Workbook(); wb.remove(wb.active)
    sheets = [("Учителя_нормы", NORM_HEADERS), ("План_дня", PLAN_HEADERS), ("Ежедневный_учет", ACTUAL_HEADERS)]
    for name, mapping in sheets:
        ws = wb.create_sheet(name); ws.append(["Шаблон нагрузки 1.0"]); ws.append([]); ws.append([]); ws.append(list(mapping.keys()))
    if include_data:
        teachers_q = db.query(TeacherModel).filter_by(school_id=school_id)
        if teacher_id: teachers_q = teachers_q.filter_by(id=teacher_id)
        teachers = teachers_q.all(); ids = [t.id for t in teachers]; by_id = {t.id: t for t in teachers}
        for teacher in teachers:
            norm = db.query(TeacherWorkloadNormModel).filter_by(teacher_id=teacher.id).order_by(TeacherWorkloadNormModel.effective_from.desc()).first()
            if norm:
                values = {"external_id": teacher.external_id, "subject": teacher.subject, "contract_teaching_hours_per_week": norm.contract_teaching_hours_per_week, "standard_teaching_hours_per_rate": norm.standard_teaching_hours_per_rate, "comment": norm.comment, "plan_source": norm.plan_source}
                wb["Учителя_нормы"].append([values.get(field) for field in NORM_HEADERS.values()])
        for model, name, mapping in ((DailyWorkloadPlanModel, "План_дня", PLAN_HEADERS), (DailyWorkloadActualModel, "Ежедневный_учет", ACTUAL_HEADERS)):
            q = db.query(model).filter(model.teacher_id.in_(ids or [""]))
            if date_from: q = q.filter(model.work_date >= date_from)
            if date_to: q = q.filter(model.work_date <= date_to)
            for obj in q.order_by(model.work_date).all():
                values = {"external_id": by_id[obj.teacher_id].external_id, **obj.__dict__}
                row = []
                for field in mapping.values():
                    value = values.get(field)
                    if isinstance(value, Decimal): value = float(value)
                    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")): value = "'" + value
                    row.append(value)
                wb[name].append(row)
    output = io.BytesIO(); wb.save(output); output.seek(0); return output


@router.get("/schools/{school_id}/workload/exports")
def export_workload(school_id: str, date_from: date | None = None, date_to: date | None = None, teacher_id: str | None = None, report: str = "full", db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    access = require_school_access(db, user.id, school_id, MANAGER_ROLES | {"teacher"})
    if access.role == "teacher": teacher_id = access.teacher_id
    output = make_workbook(db, school_id, teacher_id, date_from, date_to)
    db.add(AuditEventModel(actor_id=user.id, action="export", entity_type="workload", school_id=school_id, purpose=report, changes={"date_from": str(date_from), "date_to": str(date_to)})); db.commit()
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="teacher_workload_{date.today():%Y%m%d}.xlsx"'})


@router.get("/schools/{school_id}/workload/template")
def workload_template(school_id: str, db: Session = Depends(get_db), user: UserModel = Depends(get_current_user)):
    require_school_access(db, user.id, school_id)
    return StreamingResponse(make_workbook(db, school_id, None, None, None, False), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="teacher_workload_template_1.0.xlsx"'})
