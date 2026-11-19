"""Rename workload tables to the workload_* convention.

Revision ID: b49d7ce51aa2
Revises: fba79b1420f1
Create Date: 2026-11-19
"""

from alembic import op


revision = "b49d7ce51aa2"
down_revision = "fba79b1420f1"
branch_labels = None
depends_on = None


RENAMES = (
    ("work_types", "workload_types"),
    ("import_batches", "workload_import_batches"),
    ("teacher_workload_norms", "workload_teacher_norms"),
    ("planned_work_items", "workload_planned_items"),
    ("daily_work_logs", "workload_daily_logs"),
    ("actual_work_entries", "workload_actual_entries"),
)


def upgrade():
    for old_name, new_name in RENAMES:
        op.rename_table(old_name, new_name)


def downgrade():
    for old_name, new_name in reversed(RENAMES):
        op.rename_table(new_name, old_name)
