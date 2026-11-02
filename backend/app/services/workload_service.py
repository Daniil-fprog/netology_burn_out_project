import hashlib
import io
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.teacher_domain import (
    AuditEventModel, DailyWorkloadActualModel, DailyWorkloadPlanModel,
    ImportBatchModel, TeacherModel, TeacherWorkloadNormModel,
)


DAY_TYPES = {"Учебный день", "Выходной", "Каникулы", "Отпуск", "Больничный", "Другое"}
ASTRO = ("teaching_block", "preparation", "grading", "documentation", "parent_communication", "class_management", "meetings_methodology", "other")
PLAN_HEADERS = {
    "Дата": "work_date", "ID учителя": "external_id", "Тип дня": "day_type",
    "Уроки план, уч.ч": "planned_lessons_teaching_hours", "Замены план, уч.ч": "planned_substitutions_teaching_hours",
    "План: Учебный блок, ч": "planned_teaching_block_hours", "План: Подготовка, ч": "planned_preparation_hours",
    "План: Проверка работ, ч": "planned_grading_hours", "План: Документы, ч": "planned_documentation_hours",
    "План: Родители, ч": "planned_parent_communication_hours", "План: Классное руководство, ч": "planned_class_management_hours",
    "План: Совещания/методика, ч": "planned_meetings_methodology_hours", "План: Прочее, ч": "planned_other_hours",
}
ACTUAL_HEADERS = {
    "Дата": "work_date", "ID учителя": "external_id", "Тип дня": "day_type",
    "Уроки факт, уч.ч": "actual_lessons_teaching_hours", "Замены факт, уч.ч": "actual_substitutions_teaching_hours",
    "Факт: Учебный блок, ч": "actual_teaching_block_hours", "Факт: Подготовка, ч": "actual_preparation_hours",
    "Факт: Проверка работ, ч": "actual_grading_hours", "Факт: Документы, ч": "actual_documentation_hours",
    "Факт: Родители, ч": "actual_parent_communication_hours", "Факт: Классное руководство, ч": "actual_class_management_hours",
    "Факт: Совещания/методика, ч": "actual_meetings_methodology_hours", "Факт: Прочее, ч": "actual_other_hours",
    "В школе, ч": "at_school_hours", "Дома, ч": "at_home_hours", "Усталость 1–5": "fatigue_score",
    "Стресс 1–5": "stress_score", "Комментарий": "comment",
}
NORM_HEADERS = {
    "ID учителя": "external_id", "Предмет": "subject",
    "Учебная нагрузка по договору, ч/нед": "contract_teaching_hours_per_week",
    "Норма за ставку, ч/нед": "standard_teaching_hours_per_rate", "Комментарий": "comment", "Источник плана": "plan_source",
}


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


def total(model: Any, prefix: str) -> tuple[Decimal | None, bool]:
    values = [getattr(model, f"{prefix}_{name}_hours", None) for name in ASTRO]
    if any(v is None for v in values): return None, False
    return sum((Decimal(v) for v in values), Decimal("0")), True


def daily_dict(teacher: TeacherModel, plan: DailyWorkloadPlanModel | None, actual: DailyWorkloadActualModel | None) -> dict:
    ptotal, pcomplete = total(plan, "planned") if plan else (None, False)
    atotal, acomplete = total(actual, "actual") if actual else (None, False)
    def num(v): return float(v) if v is not None else None
    work_date = (actual or plan).work_date
    return {
        "teacher_id": teacher.id, "external_teacher_id": teacher.external_id,
        "work_date": work_date.isoformat(), "day_type": (actual or plan).day_type,
        "plan": None if not plan else {"total_hours": num(ptotal), "total_complete": pcomplete, **{name: num(getattr(plan, name)) for name in PLAN_HEADERS.values() if name.startswith("planned_")}},
        "actual": None if not actual else {"total_hours": num(atotal), "total_complete": acomplete, **{name: (getattr(actual, name) if name in {"fatigue_score", "stress_score", "comment"} else num(getattr(actual, name))) for name in ACTUAL_HEADERS.values() if name.startswith("actual_") or name in {"at_school_hours", "at_home_hours", "fatigue_score", "stress_score", "comment"}}},
        "metrics": {
            "deviation_hours": num(atotal - ptotal) if atotal is not None and ptotal is not None else None,
            "actual_to_plan_ratio": num(atotal / ptotal) if atotal is not None and ptotal and ptotal > 0 else None,
            "location_difference_hours": num(Decimal(actual.at_school_hours) + Decimal(actual.at_home_hours) - atotal) if actual and atotal is not None and actual.at_school_hours is not None and actual.at_home_hours is not None else None,
            "at_home_share": num(Decimal(actual.at_home_hours) / atotal) if actual and atotal and actual.at_home_hours is not None else None,
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
    required_sheets = {"Учителя_нормы", "План_дня", "Ежедневный_учет"}
    for name in required_sheets - set(wb.sheetnames): errors.append({"sheet": name, "row": None, "field": "sheet", "message": "Обязательный лист отсутствует"})
    if errors: return {"norms": [], "plans": [], "actuals": [], "errors": errors, "warnings": warnings}
    norms = _sheet_rows(wb["Учителя_нормы"], NORM_HEADERS, set(NORM_HEADERS) - {"Комментарий", "Источник плана"}, errors)
    plans = _sheet_rows(wb["План_дня"], PLAN_HEADERS, {"Дата", "ID учителя", "Тип дня"}, errors)
    actuals = _sheet_rows(wb["Ежедневный_учет"], ACTUAL_HEADERS, {"Дата", "ID учителя", "Тип дня"}, errors)
    for kind, rows in (("norms", norms), ("plans", plans), ("actuals", actuals)):
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
                for field in numeric: row[field] = decimal_or_none(row[field])
                for field in ("fatigue_score", "stress_score"):
                    if field in row and row[field] is not None:
                        value = int(row[field])
                        if value < 1 or value > 5 or value != float(row[field]): raise ValueError(f"{field}: ожидается целое 1..5")
                        row[field] = value
                if kind == "actuals":
                    vals = [row.get(f"actual_{x}_hours") for x in ASTRO]
                    if all(v is not None for v in vals) and row.get("at_school_hours") is not None and row.get("at_home_hours") is not None:
                        diff = abs(sum(vals, Decimal("0")) - row["at_school_hours"] - row["at_home_hours"])
                        if diff > Decimal("0.05"): raise ValueError("Сумма часов в школе и дома не совпадает с фактом")
            except (ValueError, TypeError) as exc:
                errors.append({"sheet": {"norms": "Учителя_нормы", "plans": "План_дня", "actuals": "Ежедневный_учет"}[kind], "row": row["_row"], "field": "row", "message": str(exc)})
    return {"norms": norms, "plans": plans, "actuals": actuals, "errors": errors, "warnings": warnings}


def validation_report(db: Session, school_id: str, parsed: dict, mode: str, effective_from: date) -> dict:
    errors = list(parsed["errors"])
    known = {t.external_id for t in db.query(TeacherModel).filter_by(school_id=school_id)} | {r["external_id"] for r in parsed["norms"]}
    for kind in ("plans", "actuals"):
        for row in parsed[kind]:
            if row["external_id"] not in known:
                errors.append({"sheet": kind, "row": row["_row"], "field": "external_id", "message": "Учитель не найден в этой школе"})
    count = sum(len(parsed[x]) for x in ("norms", "plans", "actuals"))
    return {"valid": not errors, "template_version": "1.0", "summary": {"teachers": len(parsed["norms"]), "norms": len(parsed["norms"]), "daily_plans": len(parsed["plans"]), "daily_actuals": len(parsed["actuals"]), "to_create": count, "to_update": 0, "to_skip": 0}, "errors": errors, "warnings": parsed["warnings"] + [{"sheet": "Учителя_нормы", "row": 5, "field": "effective_from", "message": f"Дата действия {effective_from} взята из параметра импорта"}]}


def import_workbook(db: Session, school_id: str, content: bytes, filename: str, mode: str, effective_from: date, user_id: int, stored_key: str) -> ImportBatchModel:
    parsed = parse_workbook(content)
    report = validation_report(db, school_id, parsed, mode, effective_from)
    if not report["valid"]: raise HTTPException(status_code=422, detail=report)
    digest = hashlib.sha256(content).hexdigest()
    if db.query(ImportBatchModel).filter_by(school_id=school_id, sha256=digest).first():
        raise HTTPException(status_code=409, detail="Файл с таким SHA-256 уже импортирован")
    batch = ImportBatchModel(school_id=school_id, original_filename=filename, stored_file_key=stored_key, sha256=digest, status="imported", mode=mode, effective_from=effective_from, rows_total=sum(len(parsed[x]) for x in ("norms", "plans", "actuals")), validation_report=report, uploaded_by=user_id, imported_at=datetime.now(timezone.utc))
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
    for rows, model, fields in ((parsed["plans"], DailyWorkloadPlanModel, set(PLAN_HEADERS.values())), (parsed["actuals"], DailyWorkloadActualModel, set(ACTUAL_HEADERS.values()))):
        for row in rows:
            teacher = teachers[row["external_id"]]
            record = db.query(model).filter_by(teacher_id=teacher.id, work_date=row["work_date"]).first()
            values = {k: v for k, v in row.items() if k in fields and k not in {"external_id", "work_date"}}
            if record:
                if mode == "insert_only": raise HTTPException(status_code=409, detail=f"Запись {teacher.external_id}/{row['work_date']} уже существует")
                old = {k: str(getattr(record, k)) for k in values}
                for k, v in values.items(): setattr(record, k, v)
                record.source_import_id = batch.id; updated += 1
                db.add(AuditEventModel(actor_id=user_id, action="update", entity_type=model.__tablename__, entity_id=record.id, school_id=school_id, import_batch_id=batch.id, changes={"old": old, "fields": list(values)}))
            else:
                db.add(model(teacher_id=teacher.id, work_date=row["work_date"], source_import_id=batch.id, **values)); created += 1
    batch.rows_created, batch.rows_updated = created, updated
    db.add(AuditEventModel(actor_id=user_id, action="import", entity_type="import_batch", entity_id=batch.id, school_id=school_id, import_batch_id=batch.id, changes={"created": created, "updated": updated}))
    db.commit(); db.refresh(batch)
    return batch
