"""Analytics endpoints combining teacher workload and survey responses."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.access import (
    SURVEY_ROLES,
    find_user_teacher_in_school,
    get_teacher_id_filter,
    get_teacher_in_school,
    require_school_access,
    require_teacher_access,
)
from app.core.security import get_current_user
from app.db.database import get_db
from app.models import (
    DailyWorkLogModel,
    SurveyResponseModel,
    TeacherModel,
    UserModel,
)
from app.services.survey_service import response_dict
from app.services.workload_analytic_service import pseudo
from app.services.workload_service import total


router = APIRouter(tags=["Workload analytics"])


@router.get("/schools/{school_id}/survey-analytics/completion")
def completion(
    school_id: str,
    date_from: date,
    date_to: date,
    teacher_id: str | None = None,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Рассчитывает число ожидаемых и подтверждённых опросов и процент заполнения."""

    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from позже date_to")
    teacher_id = get_teacher_id_filter(db, user.id, school_id) or teacher_id
    teacher_query = db.query(TeacherModel).filter_by(
        school_id=school_id, is_active=True
    )
    if teacher_id:
        teacher_query = teacher_query.filter_by(id=teacher_id)
    teachers = teacher_query.all()
    days = (date_to - date_from).days + 1
    expected_per_teacher = {
        "daily": days,
        "weekly": len(
            {
                (date_from + timedelta(days=i))
                - timedelta(days=(date_from + timedelta(days=i)).weekday())
                for i in range(days)
            }
        ),
        "monthly": len(
            {
                (
                    (date_from + timedelta(days=i)).year,
                    (date_from + timedelta(days=i)).month,
                )
                for i in range(days)
            }
        ),
    }
    items = []
    for teacher in teachers:
        counts = {"daily": 0, "weekly": 0, "monthly": 0}
        rows = (
            db.query(SurveyResponseModel)
            .filter(
                SurveyResponseModel.teacher_id == teacher.id,
                SurveyResponseModel.status == "approved",
                SurveyResponseModel.assessment_date.between(date_from, date_to),
            )
            .all()
        )
        for item in rows:
            counts[item.cadence] += 1
        expected = sum(expected_per_teacher.values())
        completed = sum(counts.values())
        items.append(
            {
                "teacher_id": teacher.id,
                "teacher_key": pseudo(teacher.id),
                "completed": completed,
                "expected": expected,
                "completion_rate": completed / expected if expected else None,
                "by_cadence": {
                    key: {
                        "completed": counts[key],
                        "expected": expected_per_teacher[key],
                    }
                    for key in counts
                },
                "denominator_policy": "calendar_periods_v1",
            }
        )
    return {"date_from": date_from, "date_to": date_to, "items": items}


@router.get("/schools/{school_id}/teachers/{teacher_id}/workload-and-wellbeing")
def workload_and_wellbeing(
    school_id: str,
    teacher_id: str,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Объединяет по датам фактическую нагрузку и опросы преподавателя."""

    require_school_access(db, user.id, school_id, SURVEY_ROLES)
    require_teacher_access(db, user.id, school_id, teacher_id)
    get_teacher_in_school(db, school_id, teacher_id)
    actual_logs = (
        db.query(DailyWorkLogModel)
        .filter(
            DailyWorkLogModel.teacher_id == teacher_id,
            DailyWorkLogModel.work_date.between(date_from, date_to),
        )
        .all()
    )
    responses = (
        db.query(SurveyResponseModel)
        .filter(
            SurveyResponseModel.teacher_id == teacher_id,
            SurveyResponseModel.assessment_date.between(date_from, date_to),
            SurveyResponseModel.status == "approved",
        )
        .all()
    )
    by_date = {}
    for log in actual_logs:
        by_date.setdefault(
            str(log.work_date),
            {"date": log.work_date, "workload": None, "surveys": []},
        )["workload"] = {
            "actual_total_hours": float(total(list(log.entries))),
            "status": log.status,
            "source": "workload_daily_logs",
        }
    own_teacher = find_user_teacher_in_school(db, user.id, school_id)
    for item in responses:
        by_date.setdefault(
            str(item.assessment_date),
            {"date": item.assessment_date, "workload": None, "surveys": []},
        )["surveys"].append(
            response_dict(
                item, own_teacher is not None and own_teacher.id == item.teacher_id
            )
        )
    return [by_date[key] for key in sorted(by_date)]
