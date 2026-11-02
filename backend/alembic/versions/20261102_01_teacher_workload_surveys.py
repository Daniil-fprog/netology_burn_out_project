"""Add teacher workload and wellbeing survey subsystem."""
from alembic import op

revision = "20261102_01"
down_revision = None
branch_labels = None
depends_on = None


NEW_TABLES = [
    "schools", "teachers", "user_school_access", "import_batches",
    "teacher_workload_norms", "daily_workload_plans", "daily_workload_actuals",
    "audit_events", "survey_templates", "survey_questions", "survey_consents",
    "survey_responses", "survey_answers", "survey_response_revisions",
    "survey_nlp_analyses", "survey_export_jobs", "survey_ml_labels",
]


def upgrade():
    # Models are the single schema source in this project. checkfirst keeps this
    # initial migration compatible with databases previously started by create_all.
    from app.db.database import Base
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    bind = op.get_bind()
    from app.db.database import Base
    import app.models  # noqa: F401
    for name in reversed(NEW_TABLES):
        table = Base.metadata.tables[name]
        table.drop(bind=bind, checkfirst=True)
