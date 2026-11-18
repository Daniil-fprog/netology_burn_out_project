# Model scope for the first MVP

The source files contain both the first MVP domain and models reserved for later expansion. Reserved models remain registered in SQLAlchemy and remain present in the database, but new MVP functionality must not depend on them.

## Active MVP tables

| Area | Tables |
|---|---|
| Identity and access | `users`, `roles`, `user_roles`, `schools`, `teachers`, `user_school_access` |
| Actual workload | `work_types`, `daily_work_logs`, `actual_work_entries` |
| Emotional state surveys | `survey_templates`, `survey_questions`, `survey_consents`, `survey_responses`, `survey_answers` |
| Audit | `audit_events` |

## Reserved for future expansion

| Future area | Tables |
|---|---|
| School groups | `school_groups`, `school_group_schools`, `user_school_group_assignments` |
| Import and export | `import_batches`, `export_jobs` |
| Planned workload | `teacher_workload_norms`, `workload_plan_versions`, `planned_work_items` |
| Advanced survey processing | `survey_response_revisions`, `survey_nlp_analyses` |

Do not use reserved tables in new MVP routes, services, schemas, seeds, or queries until their area is explicitly activated. Do not delete the models or remove their migration-only imports from `app.models.future_registry`.

New MVP services import their models from `app.models` and schemas from `app.schemas`. These public modules export only active MVP classes. Alembic imports `app.models.future_registry` separately so reserved tables remain registered for migrations.

The active tables currently retain two nullable links for forward compatibility:

- `actual_work_entries.planned_work_item_id` points to future table `planned_work_items`;
- `audit_events.import_batch_id` points to future table `import_batches`.

MVP schemas do not expose either field, and MVP code must leave both fields `NULL`.
