"""Declared database scope for the first MVP.

This is a development policy, not a runtime feature flag. Future tables stay in
SQLAlchemy metadata and migrations, but new MVP functionality must not depend on
them until the product scope is explicitly expanded.
"""

MVP_ACTIVE_TABLES = frozenset(
    {
        "users",
        "roles",
        "user_roles",
        "schools",
        "teachers",
        "user_school_access",
        "workload_types",
        "workload_daily_logs",
        "workload_actual_entries",
        "survey_templates",
        "survey_questions",
        "survey_consents",
        "survey_responses",
        "survey_answers",
        "audit_events",
    }
)

FUTURE_TABLES = frozenset(
    {
        "school_groups",
        "school_group_schools",
        "user_school_group_assignments",
        "export_jobs",
        "workload_import_batches",
        "workload_teacher_norms",
        "workload_plan_versions",
        "workload_planned_items",
        "survey_response_revisions",
        "survey_nlp_analyses",
    }
)

assert MVP_ACTIVE_TABLES.isdisjoint(FUTURE_TABLES)
