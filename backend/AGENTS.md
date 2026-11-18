# MVP development scope

Until the user explicitly expands the product scope, new backend development must use only these MVP tables:

- `users`
- `roles`
- `user_roles`
- `schools`
- `teachers`
- `user_school_access`
- `work_types`
- `daily_work_logs`
- `actual_work_entries`
- `survey_templates`
- `survey_questions`
- `survey_consents`
- `survey_responses`
- `survey_answers`
- `audit_events`

The models listed as future scope in `app/models/scope.py` are intentionally retained for later product expansion. Do not delete them, but do not use them in new MVP endpoints, services, schemas, seeds, queries, or required workflows unless the user explicitly asks to activate that functionality.

New MVP services must import SQLAlchemy models from `app.models` and Pydantic schemas from `app.schemas`. Do not import future classes directly from semantic modules. The public package exports intentionally contain only the MVP surface.

Keep all model modules imported by `app.models` so SQLAlchemy metadata and the existing database schema remain stable.

For MVP code, leave these compatibility references unset (`NULL`):

- `actual_work_entries.planned_work_item_id`
- `audit_events.import_batch_id`

When the user activates a future subsystem, update `app/models/scope.py`, `app/models/README.md`, and this file in the same change.
