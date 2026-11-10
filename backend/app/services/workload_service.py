import hashlib
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.work_duration import to_clock_hours
from app.core.enum import WorkUnit
from app.core.workload_import_contract import (
    ACADEMIC_HOUR_FIELDS,
    DAY_TYPES,
    NORM_HEADERS,
    PLAN_HEADERS,
    WORK_TYPE_CODES,
)
from app.models.audit import AuditEventModel
from app.models.import_batch import ImportBatchModel
from app.models.teacher import TeacherModel
from app.models.work_type import WorkTypeModel
from app.models.workload import (
    ActualWorkEntryModel,
    DailyWorkLogModel,
    PlannedWorkItemModel,
    TeacherWorkloadNormModel,
    WorkloadPlanVersionModel,
)


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        result = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError("Ожидается число")
    if not result.is_finite() or result < 0:
        raise ValueError("Часы должны быть конечным неотрицательным числом")
    return result


def date_value(value: Any) -> date:
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    if isinstance(value, str):
        try: return date.fromisoformat(value.strip())
        except ValueError: pass
    raise ValueError("Ожидается дата YYYY-MM-DD или Excel date")


def total(entries: list[PlannedWorkItemModel] | list[ActualWorkEntryModel]) -> Decimal:
    return sum((Decimal(entry.duration_hours) for entry in entries), Decimal("0"))


def _hours_by_work_type(entries: list) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for entry in entries:
        code = entry.work_type.code
        result[code] = result.get(code, Decimal("0")) + Decimal(entry.duration_hours)
    return result


def daily_dict(
    teacher: TeacherModel,
    plan_items: list[PlannedWorkItemModel],
    actual_log: DailyWorkLogModel | None,
) -> dict:
    actual_entries = [] if actual_log is None else list(actual_log.entries)
    ptotal = total(plan_items) if plan_items else None
    atotal = total(actual_entries) if actual_log is not None else None
    plan_hours = _hours_by_work_type(plan_items)
    actual_hours = _hours_by_work_type(actual_entries)
    at_school = sum(
        (Decimal(entry.duration_hours) for entry in actual_entries if entry.location == "school"),
        Decimal("0"),
    )
    at_home = sum(
        (Decimal(entry.duration_hours) for entry in actual_entries if entry.location == "home"),
        Decimal("0"),
    )
    def num(v): return float(v) if v is not None else None
    work_date = actual_log.work_date if actual_log is not None else plan_items[0].work_date
    day_type = actual_log.day_type if actual_log is not None else plan_items[0].day_type
    return {
        "teacher_id": teacher.id, "external_teacher_id": teacher.external_id,
        "work_date": work_date.isoformat(), "day_type": day_type,
        "plan": None if not plan_items else {
            "total_hours": num(ptotal),
            "total_complete": True,
            **{f"planned_{code}_hours": num(plan_hours.get(code, Decimal("0"))) for code in WORK_TYPE_CODES},
        },
        "actual": None if actual_log is None else {
            "id": actual_log.id,
            "status": actual_log.status,
            "total_hours": num(atotal),
            "total_complete": actual_log.status == "completed",
            **{f"actual_{code}_hours": num(actual_hours.get(code, Decimal("0"))) for code in WORK_TYPE_CODES},
            "at_school_hours": num(at_school),
            "at_home_hours": num(at_home),
            "comment": actual_log.comment,
        },
        "metrics": {
            "deviation_hours": num(atotal - ptotal) if atotal is not None and ptotal is not None else None,
            "actual_to_plan_ratio": num(atotal / ptotal) if atotal is not None and ptotal and ptotal > 0 else None,
            "location_difference_hours": num(at_school + at_home - atotal) if atotal is not None else None,
            "at_home_share": num(at_home / atotal) if atotal else None,
            "week_start": (work_date - timedelta(days=work_date.weekday())).isoformat(),
        },
    }


def _sheet_rows(ws, mapping: dict[str, str], required: set[str], errors: list[dict]) -> list[dict]:
    header = {str(cell.value).strip(): cell.column for cell in ws[4] if cell.value is not None}
    missing = [h for h in required if h not in header]
    if missing:
        errors.append({"sheet": ws.title, "row": 4, "field": "headers", "message": f"Нет колонок: {', '.join(missing)}"})
        return []
    rows = []
    for row_no in range(5, ws.max_row + 1):
        raw = {field: ws.cell(row_no, header[title]).value for title, field in mapping.items() if title in header}
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in raw.values()): continue
        raw["_row"] = row_no
        rows.append(raw)
    return rows


def parse_workbook(content: bytes) -> dict:
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Повреждённый XLSX: {exc}")
    errors, warnings = [], []
    required_sheets = {"Учителя_нормы", "План_дня"}
    for name in required_sheets - set(wb.sheetnames): errors.append({"sheet": name, "row": None, "field": "sheet", "message": "Обязательный лист отсутствует"})
    if errors: return {"norms": [], "plans": [], "actuals": [], "errors": errors, "warnings": warnings}
    norms = _sheet_rows(wb["Учителя_нормы"], NORM_HEADERS, set(NORM_HEADERS) - {"Комментарий", "Источник плана"}, errors)
    plans = _sheet_rows(wb["План_дня"], PLAN_HEADERS, {"Дата", "ID учителя", "Тип дня"}, errors)
    if "Ежедневный_учет" in wb.sheetnames:
        warnings.append({"sheet": "Ежедневный_учет", "row": None, "field": "sheet", "message": "Фактическая нагрузка не импортируется: её вводит преподаватель"})
    actuals: list[dict] = []
    for kind, rows in (("norms", norms), ("plans", plans)):
        seen = set()
        for row in rows:
            try:
                row["external_id"] = str(row.get("external_id") or "").strip()
                if not row["external_id"]: raise ValueError("ID учителя пуст")
                if kind != "norms":
                    row["work_date"] = date_value(row["work_date"])
                    key = (row["external_id"], row["work_date"])
                    if key in seen: raise ValueError("Дубль учителя и даты в листе")
                    seen.add(key)
                    if row.get("day_type") not in DAY_TYPES: raise ValueError("Недопустимый тип дня")
                numeric = [k for k in row if k.endswith("_hours") or k in {"contract_teaching_hours_per_week", "standard_teaching_hours_per_rate"}]
                for field in numeric:
                    row[field] = decimal_or_none(row[field])
                    if field in ACADEMIC_HOUR_FIELDS and row[field] is not None:
                        row[field] = to_clock_hours(row[field], WorkUnit.TEACHING_HOUR)
            except (ValueError, TypeError) as exc:
                errors.append({"sheet": {"norms": "Учителя_нормы", "plans": "План_дня"}[kind], "row": row["_row"], "field": "row", "message": str(exc)})
    return {"norms": norms, "plans": plans, "actuals": actuals, "errors": errors, "warnings": warnings}


def validation_report(db: Session, school_id: str, parsed: dict, mode: str, effective_from: date) -> dict:
    errors = list(parsed["errors"])
    known = {t.external_id for t in db.query(TeacherModel).filter_by(school_id=school_id)} | {r["external_id"] for r in parsed["norms"]}
    for kind in ("plans",):
        for row in parsed[kind]:
            if row["external_id"] not in known:
                errors.append({"sheet": kind, "row": row["_row"], "field": "external_id", "message": "Учитель не найден в этой школе"})
    count = sum(len(parsed[x]) for x in ("norms", "plans"))
    return {"valid": not errors, "template_version": "1.0", "summary": {"teachers": len(parsed["norms"]), "norms": len(parsed["norms"]), "daily_plans": len(parsed["plans"]), "daily_actuals": len(parsed["actuals"]), "to_create": count, "to_update": 0, "to_skip": 0}, "errors": errors, "warnings": parsed["warnings"] + [{"sheet": "Учителя_нормы", "row": 5, "field": "effective_from", "message": f"Дата действия {effective_from} взята из параметра импорта"}]}


def _row_durations(row: dict, prefix: str) -> list[tuple[str, Decimal]]:
    result = []
    for code in WORK_TYPE_CODES:
        value = row.get(f"{prefix}_{code}_hours")
        if value is not None and value > 0:
            result.append((code, Decimal(value)))
    return result


def import_workbook(db: Session, school_id: str, content: bytes, filename: str, mode: str, effective_from: date, user_id: int, stored_key: str) -> ImportBatchModel:
    parsed = parse_workbook(content)
    report = validation_report(db, school_id, parsed, mode, effective_from)
    if not report["valid"]: raise HTTPException(status_code=422, detail=report)
    digest = hashlib.sha256(content).hexdigest()
    if db.query(ImportBatchModel).filter_by(school_id=school_id, sha256=digest).first():
        raise HTTPException(status_code=409, detail="Файл с таким SHA-256 уже импортирован")
    batch = ImportBatchModel(school_id=school_id, original_filename=filename, stored_file_key=stored_key, sha256=digest, status="imported", mode=mode, effective_from=effective_from, rows_total=sum(len(parsed[x]) for x in ("norms", "plans")), validation_report=report, uploaded_by=user_id, imported_at=datetime.now(timezone.utc))
    db.add(batch); db.flush()
    teachers = {t.external_id: t for t in db.query(TeacherModel).filter_by(school_id=school_id)}
    created = updated = 0
    for row in parsed["norms"]:
        teacher = teachers.get(row["external_id"])
        if not teacher:
            teacher = TeacherModel(school_id=school_id, external_id=row["external_id"], subject=str(row.get("subject") or "").strip())
            db.add(teacher); db.flush(); teachers[teacher.external_id] = teacher; created += 1
        elif row.get("subject"): teacher.subject = str(row["subject"]).strip()
        current = db.query(TeacherWorkloadNormModel).filter_by(teacher_id=teacher.id).filter(TeacherWorkloadNormModel.effective_to.is_(None)).first()
        if current and current.effective_from < effective_from: current.effective_to = effective_from - timedelta(days=1)
        norm = db.query(TeacherWorkloadNormModel).filter_by(teacher_id=teacher.id, effective_from=effective_from).first()
        values = {k: row.get(k) for k in ("contract_teaching_hours_per_week", "standard_teaching_hours_per_rate", "comment", "plan_source")}
        if norm:
            if mode == "insert_only": raise HTTPException(status_code=409, detail=f"Норма {teacher.external_id} уже существует")
            for k, v in values.items(): setattr(norm, k, v)
            norm.source_import_id = batch.id; updated += 1
        else:
            db.add(TeacherWorkloadNormModel(teacher_id=teacher.id, effective_from=effective_from, source_import_id=batch.id, **values)); created += 1
    work_types = {
        item.code: item
        for item in db.query(WorkTypeModel).filter(WorkTypeModel.code.in_(WORK_TYPE_CODES)).all()
    }
    missing_work_types = set(WORK_TYPE_CODES) - set(work_types)
    if missing_work_types:
        raise HTTPException(
            status_code=422,
            detail=f"Не настроены типы работ: {', '.join(sorted(missing_work_types))}",
        )

    if parsed["plans"]:
        previous_version = (
            db.query(WorkloadPlanVersionModel)
            .filter_by(school_id=school_id)
            .order_by(WorkloadPlanVersionModel.version.desc())
            .first()
        )
        plan_version = WorkloadPlanVersionModel(
            school_id=school_id,
            version=1 if previous_version is None else previous_version.version + 1,
            status="published",
            effective_from=min(row["work_date"] for row in parsed["plans"]),
            effective_to=max(row["work_date"] for row in parsed["plans"]),
            source_import_id=batch.id,
            created_by=user_id,
            published_at=datetime.now(timezone.utc),
            change_comment=f"Импорт {filename}",
        )
        db.add(plan_version)
        db.flush()
        for row in parsed["plans"]:
            teacher = teachers[row["external_id"]]
            for sequence_no, (code, duration) in enumerate(_row_durations(row, "planned"), 1):
                db.add(
                    PlannedWorkItemModel(
                        plan_version_id=plan_version.id,
                        teacher_id=teacher.id,
                        work_type_id=work_types[code].id,
                        work_date=row["work_date"],
                        day_type=row["day_type"],
                        subject=teacher.subject,
                        duration_hours=duration,
                        sequence_no=sequence_no,
                    )
                )
            created += 1

    batch.rows_created, batch.rows_updated = created, updated
    db.add(AuditEventModel(actor_id=user_id, action="import", entity_type="import_batch", entity_id=batch.id, school_id=school_id, import_batch_id=batch.id, changes={"created": created, "updated": updated}))
    db.commit(); db.refresh(batch)
    return batch
