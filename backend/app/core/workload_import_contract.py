"""Column contract for workload Excel template version 1.0."""

from app.core.enum import DayType, WorkloadTemplateWorkTypeCode


DAY_TYPES = frozenset(item.value for item in DayType)
WORK_TYPE_CODES = tuple(item.value for item in WorkloadTemplateWorkTypeCode)

PLAN_HEADERS = {
    "Дата": "work_date", "ID учителя": "external_id", "Тип дня": "day_type",
    "Уроки план, уч.ч": "planned_lessons_hours", "Замены план, уч.ч": "planned_substitutions_hours",
    "План: Подготовка, ч": "planned_preparation_hours",
    "План: Проверка работ, ч": "planned_grading_hours", "План: Документы, ч": "planned_documentation_hours",
    "План: Родители, ч": "planned_parent_communication_hours", "План: Классное руководство, ч": "planned_class_management_hours",
    "План: Совещания/методика, ч": "planned_meetings_methodology_hours", "План: Прочее, ч": "planned_other_hours",
}

ACTUAL_HEADERS = {
    "Дата": "work_date", "ID учителя": "external_id", "Тип дня": "day_type",
    "Уроки факт, уч.ч": "actual_lessons_hours", "Замены факт, уч.ч": "actual_substitutions_hours",
    "Факт: Подготовка, ч": "actual_preparation_hours",
    "Факт: Проверка работ, ч": "actual_grading_hours", "Факт: Документы, ч": "actual_documentation_hours",
    "Факт: Родители, ч": "actual_parent_communication_hours", "Факт: Классное руководство, ч": "actual_class_management_hours",
    "Факт: Совещания/методика, ч": "actual_meetings_methodology_hours", "Факт: Прочее, ч": "actual_other_hours",
    "В школе, ч": "at_school_hours", "Дома, ч": "at_home_hours", "Комментарий": "comment",
}

ACADEMIC_HOUR_FIELDS = frozenset({
    "planned_lessons_hours",
    "planned_substitutions_hours",
    "actual_lessons_hours",
    "actual_substitutions_hours",
})

NORM_HEADERS = {
    "ID учителя": "external_id", "Предмет": "subject",
    "Учебная нагрузка по договору, ч/нед": "contract_teaching_hours_per_week",
    "Норма за ставку, ч/нед": "standard_teaching_hours_per_rate",
    "Комментарий": "comment", "Источник плана": "plan_source",
}
