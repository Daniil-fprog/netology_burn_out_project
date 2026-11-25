"""Replace submit/withdraw with approve/deactivate response statuses.

Revision ID: d2b7e4a9c1f6
Revises: c7f0a8d4e2b1
Create Date: 2026-11-25
"""

from alembic import op
import sqlalchemy as sa


revision = "d2b7e4a9c1f6"
down_revision = "c7f0a8d4e2b1"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("uq_survey_active_response_period", table_name="survey_responses")
    op.execute(
        sa.text(
            """
            UPDATE survey_responses
            SET status = CASE status
                WHEN 'submitted' THEN 'approved'
                WHEN 'withdrawn' THEN 'deactivated'
                ELSE status
            END
            """
        )
    )
    with op.batch_alter_table("survey_responses") as batch_op:
        batch_op.alter_column(
            "submitted_at",
            new_column_name="approved_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
    op.create_index(
        "uq_survey_active_response_period",
        "survey_responses",
        ["teacher_id", "cadence", "period_start", "period_end"],
        unique=True,
        sqlite_where=sa.text("status IN ('draft', 'approved')"),
        postgresql_where=sa.text("status IN ('draft', 'approved')"),
    )


def downgrade():
    op.drop_index("uq_survey_active_response_period", table_name="survey_responses")
    op.execute(
        sa.text(
            """
            UPDATE survey_responses
            SET status = CASE status
                WHEN 'approved' THEN 'submitted'
                WHEN 'deactivated' THEN 'withdrawn'
                ELSE status
            END
            """
        )
    )
    with op.batch_alter_table("survey_responses") as batch_op:
        batch_op.alter_column(
            "approved_at",
            new_column_name="submitted_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
    op.create_index(
        "uq_survey_active_response_period",
        "survey_responses",
        ["teacher_id", "cadence", "period_start", "period_end"],
        unique=True,
        sqlite_where=sa.text("status IN ('draft', 'submitted')"),
        postgresql_where=sa.text("status IN ('draft', 'submitted')"),
    )
