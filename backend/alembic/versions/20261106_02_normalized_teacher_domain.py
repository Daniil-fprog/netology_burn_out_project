"""Add normalized roles, organization scopes and workload entities.

Revision ID: 20261106_02
Revises: 20261102_01
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20261106_02"
down_revision = "20261102_01"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    now = datetime.now(timezone.utc)

    # Account status and an explicit account-to-teacher link.
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    with op.batch_alter_table("teachers") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_teachers_user_id_users", "users", ["user_id"], ["id"], ondelete="SET NULL")
        batch.create_unique_constraint("uq_teacher_user", ["user_id"])
        batch.create_index("ix_teachers_user_id", ["user_id"])
    with op.batch_alter_table("user_school_access") as batch:
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))

    op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500)),
        *timestamps(),
    )
    op.create_index("ix_roles_code", "roles", ["code"], unique=True)
    op.create_table(
        "user_roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    op.create_table(
        "school_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("external_code", sa.String(80), unique=True),
        *timestamps(),
    )
    op.create_table(
        "school_group_schools",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("school_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("group_id", "school_id", name="uq_school_group_school"),
    )
    op.create_index("ix_school_group_schools_group_id", "school_group_schools", ["group_id"])
    op.create_index("ix_school_group_schools_school_id", "school_group_schools", ["school_id"])
    op.create_table(
        "user_school_group_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_group_id", sa.String(36), sa.ForeignKey("school_groups.id", ondelete="CASCADE"), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("user_id", "school_group_id", name="uq_user_school_group_assignment"),
    )
    op.create_index("ix_user_school_group_assignments_user_id", "user_school_group_assignments", ["user_id"])
    op.create_index("ix_user_school_group_assignments_school_group_id", "user_school_group_assignments", ["school_group_id"])

    op.create_table(
        "work_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category_group", sa.String(120), nullable=False),
        sa.Column("default_unit", sa.String(30), nullable=False),
        sa.Column("allowed_units", sa.JSON(), nullable=False),
        sa.Column("requires_comment", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("default_unit IN ('teaching_hour', 'clock_minute')", name="ck_work_type_default_unit"),
    )
    op.create_index("ix_work_types_code", "work_types", ["code"], unique=True)

    op.create_table(
        "workload_plan_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=False),
        sa.Column("source_import_id", sa.String(36), sa.ForeignKey("import_batches.id", ondelete="SET NULL")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("change_comment", sa.Text()),
        *timestamps(),
        sa.CheckConstraint("effective_to >= effective_from", name="ck_plan_version_period"),
        sa.UniqueConstraint("school_id", "version", name="uq_school_plan_version"),
    )
    op.create_index("ix_workload_plan_versions_school_id", "workload_plan_versions", ["school_id"])
    op.create_table(
        "planned_work_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_version_id", sa.String(36), sa.ForeignKey("workload_plan_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_type_id", sa.String(36), sa.ForeignKey("work_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("subject", sa.String(150)),
        sa.Column("duration", sa.Numeric(8, 2), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text()),
        *timestamps(),
        sa.CheckConstraint("duration > 0", name="ck_planned_work_duration_positive"),
        sa.CheckConstraint("unit IN ('teaching_hour', 'clock_minute')", name="ck_planned_work_unit"),
        sa.UniqueConstraint("plan_version_id", "teacher_id", "work_date", "work_type_id", "sequence_no", name="uq_planned_work_item_sequence"),
    )
    for column in ("plan_version_id", "teacher_id", "work_type_id", "work_date"):
        op.create_index(f"ix_planned_work_items_{column}", "planned_work_items", [column])

    op.create_table(
        "daily_work_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *timestamps(),
        sa.CheckConstraint("status IN ('not_started', 'draft', 'completed')", name="ck_daily_work_log_status"),
        sa.UniqueConstraint("teacher_id", "work_date", name="uq_daily_work_log_teacher_date"),
    )
    op.create_index("ix_daily_work_logs_teacher_id", "daily_work_logs", ["teacher_id"])
    op.create_index("ix_daily_work_logs_work_date", "daily_work_logs", ["work_date"])
    op.create_table(
        "actual_work_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("daily_log_id", sa.String(36), sa.ForeignKey("daily_work_logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("planned_work_item_id", sa.String(36), sa.ForeignKey("planned_work_items.id", ondelete="SET NULL")),
        sa.Column("work_type_id", sa.String(36), sa.ForeignKey("work_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("duration", sa.Numeric(8, 2), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("location", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *timestamps(),
        sa.CheckConstraint("duration > 0", name="ck_actual_work_duration_positive"),
        sa.CheckConstraint(
            "(unit = 'clock_minute' AND duration <= 1440) OR "
            "(unit = 'teaching_hour' AND duration <= 32)",
            name="ck_actual_work_duration_daily_bound",
        ),
        sa.CheckConstraint("unit IN ('teaching_hour', 'clock_minute')", name="ck_actual_work_unit"),
        sa.CheckConstraint("location IN ('school', 'home', 'other')", name="ck_actual_work_location"),
    )
    for column in ("daily_log_id", "planned_work_item_id", "work_type_id"):
        op.create_index(f"ix_actual_work_entries_{column}", "actual_work_entries", [column])

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="RESTRICT")),
        sa.Column("school_group_id", sa.String(36), sa.ForeignKey("school_groups.id", ondelete="RESTRICT")),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("filters_jsonb", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("stored_file_key", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("downloaded_at", sa.DateTime(timezone=True)),
        sa.Column("download_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        *timestamps(),
        sa.CheckConstraint("format IN ('xlsx', 'csv', 'json')", name="ck_export_job_format"),
        sa.CheckConstraint("download_count >= 0", name="ck_export_download_count"),
    )
    for column in ("requested_by", "school_id", "school_group_id"):
        op.create_index(f"ix_export_jobs_{column}", "export_jobs", [column])

    role_table = sa.table(
        "roles",
        sa.column("id", sa.String), sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("description", sa.String), sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    role_names = {
        "teacher": "Преподаватель", "director": "Директор", "head": "Глава",
        "group_head": "Глава группы", "system_admin": "Системный администратор",
    }
    op.bulk_insert(role_table, [
        {"id": f"00000000-0000-0000-0000-{index:012d}", "code": code, "name": name,
         "description": None, "created_at": now, "updated_at": now}
        for index, (code, name) in enumerate(role_names.items(), 1)
    ])

    work_type_table = sa.table(
        "work_types",
        sa.column("id", sa.String), sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("category_group", sa.String), sa.column("default_unit", sa.String),
        sa.column("allowed_units", sa.JSON), sa.column("requires_comment", sa.Boolean),
        sa.column("is_active", sa.Boolean), sa.column("description", sa.Text),
        sa.column("archived_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    default_work_types = (
        ("lessons", "Проведение уроков", "teaching"),
        ("preparation", "Подготовка", "teaching_support"),
        ("grading", "Проверка домашних и контрольных работ", "teaching_support"),
        ("documentation", "Документация", "administrative"),
        ("class_management", "Классное руководство", "student_support"),
        ("parent_communication", "Общение с родителями", "communication"),
        ("meetings", "Совещания", "administrative"),
        ("methodology", "Методическая работа", "professional_development"),
        ("substitutions", "Замены", "teaching"),
        ("events", "Мероприятия", "extracurricular"),
        ("duties", "Дежурства", "administrative"),
        ("other", "Прочее", "other"),
    )
    op.bulk_insert(work_type_table, [
        {"id": f"10000000-0000-0000-0000-{index:012d}", "code": code, "name": name,
         "category_group": group, "default_unit": "clock_minute",
         "allowed_units": ["clock_minute", "teaching_hour"], "requires_comment": code == "other",
         "is_active": True, "description": None, "archived_at": None, "created_at": now, "updated_at": now}
        for index, (code, name, group) in enumerate(default_work_types, 1)
    ])


def downgrade():
    for table in (
        "export_jobs", "actual_work_entries", "daily_work_logs", "planned_work_items",
        "workload_plan_versions", "work_types", "user_school_group_assignments",
        "school_group_schools", "school_groups", "user_roles", "roles",
    ):
        op.drop_table(table)

    with op.batch_alter_table("user_school_access") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("created_at")
    with op.batch_alter_table("teachers") as batch:
        batch.drop_index("ix_teachers_user_id")
        batch.drop_constraint("uq_teacher_user", type_="unique")
        batch.drop_constraint("fk_teachers_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_active")
