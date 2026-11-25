"""Embed consent in survey responses.

Revision ID: c7f0a8d4e2b1
Revises: b49d7ce51aa2
Create Date: 2026-11-25
"""

from alembic import op
import sqlalchemy as sa


revision = "c7f0a8d4e2b1"
down_revision = "b49d7ce51aa2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("survey_responses") as batch_op:
        batch_op.add_column(
            sa.Column(
                "consent_given",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.execute(
        sa.text(
            """
            UPDATE survey_responses
            SET consent_given = true,
                consented_at = submitted_at
            WHERE consent_record_id IS NOT NULL
            """
        )
    )

    with op.batch_alter_table("survey_responses") as batch_op:
        batch_op.drop_column("consent_record_id")

    op.drop_index("ix_survey_consents_teacher_id", table_name="survey_consents")
    op.drop_index("ix_survey_consents_school_id", table_name="survey_consents")
    op.drop_table("survey_consents")


def downgrade():
    op.create_table(
        "survey_consents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("school_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("proof_reference", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_survey_consents_school_id",
        "survey_consents",
        ["school_id"],
        unique=False,
    )
    op.create_index(
        "ix_survey_consents_teacher_id",
        "survey_consents",
        ["teacher_id"],
        unique=False,
    )

    with op.batch_alter_table("survey_responses") as batch_op:
        batch_op.add_column(
            sa.Column("consent_record_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_survey_responses_consent_record_id",
            "survey_consents",
            ["consent_record_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.drop_column("consented_at")
        batch_op.drop_column("consent_given")
