"""Analytics required by the plan-only workload dashboard."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from statistics import median

from sqlalchemy.orm import Session

from app.models.organization import SchoolModel
from app.models.teacher import TeacherModel
from app.models.workload import PlannedWorkItemModel, TeacherWorkloadNormModel, WorkloadPlanVersionModel


def get_planned_dashboard(db: Session, school_ids: set[str], date_from: date, date_to: date) -> dict:
    """Build plan-only KPIs and chart series for an authorized school scope."""
    if date_from > date_to:
        raise ValueError("date_from must not be later than date_to")
    if not school_ids:
        return _empty_dashboard(date_from, date_to)

    rows = (
        db.query(PlannedWorkItemModel)
        .join(WorkloadPlanVersionModel)
        .filter(
            WorkloadPlanVersionModel.school_id.in_(school_ids),
            WorkloadPlanVersionModel.status == "published",
            PlannedWorkItemModel.work_date.between(date_from, date_to),
        )
        .order_by(WorkloadPlanVersionModel.version)
        .all()
    )
    latest = {}
    for item in rows:
        key = (item.plan_version.school_id, item.teacher_id, item.work_date, item.work_type_id, item.sequence_no)
        latest[key] = item
    items = list(latest.values())

    teachers = {
        item.id: item
        for item in db.query(TeacherModel).filter(TeacherModel.id.in_({x.teacher_id for x in items} or {""})).all()
    }
    schools = {
        item.id: item.name
        for item in db.query(SchoolModel).filter(SchoolModel.id.in_(school_ids)).all()
    }
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    teaching: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    weekly: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    subjects: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    school_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for item in items:
        hours = Decimal(item.duration_hours)
        totals[item.teacher_id] += hours
        if item.work_type.category_group == "teaching":
            teaching[item.teacher_id] += hours
        week = item.work_date.fromordinal(item.work_date.toordinal() - item.work_date.weekday())
        weekly[week] += hours
        teacher = teachers.get(item.teacher_id)
        subjects[item.subject or (teacher.subject if teacher else "Не указан")] += hours
        school_totals[schools.get(item.plan_version.school_id, item.plan_version.school_id)] += hours

    teacher_rows = []
    for teacher_id, planned in sorted(totals.items()):
        teacher = teachers[teacher_id]
        norm = (
            db.query(TeacherWorkloadNormModel)
            .filter(
                TeacherWorkloadNormModel.teacher_id == teacher_id,
                TeacherWorkloadNormModel.effective_from <= date_to,
                (TeacherWorkloadNormModel.effective_to.is_(None)) | (TeacherWorkloadNormModel.effective_to >= date_from),
            )
            .order_by(TeacherWorkloadNormModel.effective_from.desc())
            .first()
        )
        weeks = {x.work_date.fromordinal(x.work_date.toordinal() - x.work_date.weekday()) for x in items if x.teacher_id == teacher_id}
        expected = Decimal(norm.contract_teaching_hours_per_week) * len(weeks) if norm else None
        planned_teaching = teaching[teacher_id]
        teacher_rows.append({
            "teacher_id": teacher_id,
            "full_name": teacher.full_name,
            "subject": teacher.subject,
            "planned_hours": float(planned),
            "planned_teaching_hours": float(planned_teaching),
            "individual_norm_hours": float(expected) if expected is not None else None,
            "deviation_from_norm_hours": float(planned_teaching - expected) if expected is not None else None,
        })

    values = [float(value) for value in teaching.values()]
    return {
        "date_from": date_from,
        "date_to": date_to,
        "kpi": {
            "planned_teaching_hours": float(sum(teaching.values(), Decimal("0"))),
            "teacher_count": len(totals),
            "average_teaching_hours": round(sum(values) / len(values), 2) if values else None,
            "median_teaching_hours": median(values) if values else None,
        },
        "weekly": [{"week_start": key, "hours": float(weekly[key])} for key in sorted(weekly)],
        "by_subject": [{"subject": key, "hours": float(value)} for key, value in sorted(subjects.items())],
        "by_school": [{"school": key, "hours": float(value)} for key, value in sorted(school_totals.items())],
        "teachers": teacher_rows,
    }


def _empty_dashboard(date_from: date, date_to: date) -> dict:
    return {
        "date_from": date_from,
        "date_to": date_to,
        "kpi": {"planned_teaching_hours": 0.0, "teacher_count": 0, "average_teaching_hours": None, "median_teaching_hours": None},
        "weekly": [], "by_subject": [], "by_school": [], "teachers": [],
    }
