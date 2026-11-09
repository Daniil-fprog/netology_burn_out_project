"""Create the initial application, workload and survey schema explicitly.

Revision ID: 20261102_01
Revises: None
"""

from alembic import op
import sqlalchemy as sa


revision = "20261102_01"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    """Columns shared by the original timestamped tables."""

    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("login", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("phone", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("login"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_login", "users", ["login"], unique=True)
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    op.create_table(
        "recommendation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rec_name", sa.String(), nullable=False),
        sa.Column("rec_text", sa.String(), nullable=False),
        sa.Column("mood_type", sa.String(), nullable=False),
        sa.Column("score_from", sa.Integer(), nullable=False),
        sa.Column("score_to", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_recommendation_id", "recommendation", ["id"])

    op.create_table(
        "note",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("orig_text", sa.String(), nullable=False),
        sa.Column("translate_text", sa.String()),
        sa.Column("translate_status", sa.String()),
        sa.Column("sentiment_label", sa.String()),
        sa.Column("sentiment_score", sa.Integer()),
        sa.Column("model_confidence", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_note_id", "note", ["id"])
    op.create_table(
        "note_recommendation",
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("note.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("recommendation.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "schools",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("external_code", sa.String(80), unique=True),
        *timestamps(),
    )
    op.create_table(
        "teachers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("external_id", sa.String(80), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("subject", sa.String(150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("school_id", "external_id", name="uq_teacher_school_external"),
    )
    op.create_index("ix_teachers_school_id", "teachers", ["school_id"])
    op.create_table(
        "user_school_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("teachers.id", ondelete="SET NULL")),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("can_read_comments", sa.Boolean(), nullable=False),
        sa.Column("can_export_research", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("user_id", "school_id", name="uq_user_school_access"),
    )
    op.create_index("ix_user_school_access_user_id", "user_school_access", ["user_id"])
    op.create_index("ix_user_school_access_school_id", "user_school_access", ["school_id"])

    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_file_key", sa.Text()),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("template_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("rows_created", sa.Integer(), nullable=False),
        sa.Column("rows_updated", sa.Integer(), nullable=False),
        sa.Column("rows_skipped", sa.Integer(), nullable=False),
        sa.Column("validation_report", sa.JSON(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("imported_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("school_id", "sha256", name="uq_import_school_sha256"),
    )
    op.create_index("ix_import_batches_school_id", "import_batches", ["school_id"])

    op.create_table(
        "teacher_workload_norms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("contract_teaching_hours_per_week", sa.Numeric(6, 2), nullable=False),
        sa.Column("standard_teaching_hours_per_rate", sa.Numeric(6, 2), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("plan_source", sa.String(255)),
        sa.Column("source_import_id", sa.String(36), sa.ForeignKey("import_batches.id", ondelete="SET NULL")),
        *timestamps(),
        sa.CheckConstraint("contract_teaching_hours_per_week >= 0", name="ck_norm_contract_nonnegative"),
        sa.CheckConstraint("standard_teaching_hours_per_rate > 0", name="ck_norm_standard_positive"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_norm_period"),
        sa.UniqueConstraint("teacher_id", "effective_from", name="uq_norm_teacher_from"),
    )
    op.create_index("ix_teacher_workload_norms_teacher_id", "teacher_workload_norms", ["teacher_id"])

    _create_legacy_daily_tables()
    _create_audit_table()
    _create_survey_tables()


def _create_legacy_daily_tables():
    plan_columns = [
        sa.Column("planned_lessons_teaching_hours", sa.Numeric(6, 2)),
        sa.Column("planned_substitutions_teaching_hours", sa.Numeric(6, 2)),
        *[sa.Column(f"planned_{name}_hours", sa.Numeric(7, 2)) for name in (
            "teaching_block", "preparation", "grading", "documentation",
            "parent_communication", "class_management", "meetings_methodology", "other",
        )],
    ]
    op.create_table(
        "daily_workload_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("day_type", sa.String(40), nullable=False),
        *plan_columns,
        sa.Column("source_import_id", sa.String(36), sa.ForeignKey("import_batches.id", ondelete="SET NULL")),
        *timestamps(),
        sa.UniqueConstraint("teacher_id", "work_date", name="uq_plan_teacher_date"),
    )
    op.create_index("ix_daily_workload_plans_teacher_id", "daily_workload_plans", ["teacher_id"])
    op.create_index("ix_daily_workload_plans_work_date", "daily_workload_plans", ["work_date"])

    actual_columns = [
        sa.Column("actual_lessons_teaching_hours", sa.Numeric(6, 2)),
        sa.Column("actual_substitutions_teaching_hours", sa.Numeric(6, 2)),
        *[sa.Column(f"actual_{name}_hours", sa.Numeric(7, 2)) for name in (
            "teaching_block", "preparation", "grading", "documentation",
            "parent_communication", "class_management", "meetings_methodology", "other",
        )],
    ]
    op.create_table(
        "daily_workload_actuals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("day_type", sa.String(40), nullable=False),
        *actual_columns,
        sa.Column("at_school_hours", sa.Numeric(7, 2)),
        sa.Column("at_home_hours", sa.Numeric(7, 2)),
        sa.Column("fatigue_score", sa.SmallInteger()),
        sa.Column("stress_score", sa.SmallInteger()),
        sa.Column("comment", sa.Text()),
        sa.Column("source_import_id", sa.String(36), sa.ForeignKey("import_batches.id", ondelete="SET NULL")),
        *timestamps(),
        sa.CheckConstraint("fatigue_score IS NULL OR fatigue_score BETWEEN 1 AND 5", name="ck_actual_fatigue"),
        sa.CheckConstraint("stress_score IS NULL OR stress_score BETWEEN 1 AND 5", name="ck_actual_stress"),
        sa.UniqueConstraint("teacher_id", "work_date", name="uq_actual_teacher_date"),
    )
    op.create_index("ix_daily_workload_actuals_teacher_id", "daily_workload_actuals", ["teacher_id"])
    op.create_index("ix_daily_workload_actuals_work_date", "daily_workload_actuals", ["work_date"])


def _create_audit_table():
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(36)),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL")),
        sa.Column("import_batch_id", sa.String(36), sa.ForeignKey("import_batches.id", ondelete="SET NULL")),
        sa.Column("purpose", sa.String(80)),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_events_school_id", "audit_events", ["school_id"])


def _create_survey_tables():
    op.create_table(
        "survey_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("cadence", sa.String(20), nullable=False),
        sa.Column("locale", sa.String(12), nullable=False),
        sa.Column("definition_jsonb", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_current", sa.Boolean()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("code", "version", name="uq_survey_template_version"),
    )
    op.create_index("ix_survey_templates_code", "survey_templates", ["code"])
    op.create_index("ix_survey_template_current", "survey_templates", ["code", "is_current"], unique=True)
    op.create_table(
        "survey_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("survey_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("settings_jsonb", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("template_id", "code", name="uq_question_template_code"),
        sa.UniqueConstraint("template_id", "position", name="uq_question_template_position"),
    )
    op.create_index("ix_survey_questions_template_id", "survey_questions", ["template_id"])
    op.create_table(
        "survey_consents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("proof_reference", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_survey_consents_school_id", "survey_consents", ["school_id"])
    op.create_index("ix_survey_consents_teacher_id", "survey_consents", ["teacher_id"])
    op.create_table(
        "survey_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("survey_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cadence", sa.String(20), nullable=False),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("comment_reference_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("consent_record_id", sa.String(36), sa.ForeignKey("survey_consents.id", ondelete="RESTRICT")),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("client_request_id", sa.String(36)),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("period_start <= period_end", name="ck_response_period"),
        sa.UniqueConstraint("teacher_id", "client_request_id", name="uq_response_client_request"),
    )
    for column in ("school_id", "teacher_id", "assessment_date"):
        op.create_index(f"ix_survey_responses_{column}", "survey_responses", [column])
    op.create_index("ix_response_teacher_period", "survey_responses", ["teacher_id", "period_start", "period_end"])
    op.create_index(
        "uq_survey_active_response_period", "survey_responses",
        ["teacher_id", "cadence", "period_start", "period_end"], unique=True,
        sqlite_where=sa.text("status IN ('draft', 'submitted')"),
        postgresql_where=sa.text("status IN ('draft', 'submitted')"),
    )
    op.create_table(
        "survey_answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("response_id", sa.String(36), sa.ForeignKey("survey_responses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("survey_questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("value_jsonb", sa.JSON(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("response_id", "question_id", name="uq_response_question"),
    )
    op.create_index("ix_survey_answers_response_id", "survey_answers", ["response_id"])
    op.create_index("ix_survey_answers_question_id", "survey_answers", ["question_id"])
    op.create_table(
        "survey_response_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("response_id", sa.String(36), sa.ForeignKey("survey_responses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reason", sa.Text()),
        sa.Column("previous_answers_jsonb", sa.JSON(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.UniqueConstraint("response_id", "revision_no", name="uq_response_revision"),
    )
    op.create_table(
        "survey_nlp_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("response_id", sa.String(36), sa.ForeignKey("survey_responses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("answer_id", sa.String(36), sa.ForeignKey("survey_answers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("model_name", sa.String(100)),
        sa.Column("model_version", sa.String(50)),
        sa.Column("preprocessing_version", sa.String(50)),
        sa.Column("schema_version", sa.String(50)),
        sa.Column("result_jsonb", sa.JSON()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_survey_nlp_analyses_response_id", "survey_nlp_analyses", ["response_id"])
    op.create_table(
        "survey_export_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("report", sa.String(30), nullable=False),
        sa.Column("filters_jsonb", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("stored_file_key", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        *timestamps(),
    )
    op.create_table(
        "survey_ml_labels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("label_definition_version", sa.String(50), nullable=False),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("value_jsonb", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        *timestamps(),
    )


def downgrade():
    for table in (
        "survey_ml_labels", "survey_export_jobs", "survey_nlp_analyses",
        "survey_response_revisions", "survey_answers", "survey_responses",
        "survey_consents", "survey_questions", "survey_templates", "audit_events",
        "daily_workload_actuals", "daily_workload_plans", "teacher_workload_norms",
        "import_batches", "user_school_access", "teachers", "schools",
        "note_recommendation", "note", "recommendation", "users",
    ):
        op.drop_table(table)
