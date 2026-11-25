"""Keep public read schemas aligned with their SQLAlchemy tables."""

import pytest

import app.models  # noqa: F401 - register every model in Base.metadata
import app.schemas
from app.db.database import Base
from app.models.access import UserSchoolAccessModel, UserSchoolGroupAssignmentModel
from app.models.audit import AuditEventModel
from app.models.export import ExportJobModel
from app.models.import_batch import ImportBatchModel
from app.models.organization import SchoolGroupModel, SchoolGroupSchoolModel, SchoolModel
from app.models.role import RoleModel, UserRoleModel
from app.models.scope import FUTURE_TABLES, MVP_ACTIVE_TABLES
from app.models.survey import (
    SurveyAnswerModel,
    SurveyNLPAnalysisModel,
    SurveyQuestionModel,
    SurveyResponseModel,
    SurveyResponseRevisionModel,
    SurveyTemplateModel,
)
from app.models.teacher import TeacherModel
from app.models.user import UserModel
from app.models.work_type import WorkTypeModel
from app.models.workload import (
    ActualWorkEntryModel,
    DailyWorkLogModel,
    PlannedWorkItemModel,
    TeacherWorkloadNormModel,
    WorkloadPlanVersionModel,
)
from app.schemas.access import UserSchoolAssignmentOut, UserSchoolGroupAssignmentOut
from app.schemas.audit import AuditEventOut
from app.schemas.export import ExportJobOut
from app.schemas.import_batch import ImportBatchOut
from app.schemas.organization import SchoolGroupOut, SchoolGroupSchoolOut, SchoolOut
from app.schemas.role import RoleOut, UserRoleOut
from app.schemas.survey import (
    SurveyAnswerOut,
    SurveyNLPAnalysisOut,
    SurveyQuestionOut,
    SurveyResponseOut,
    SurveyResponseRevisionOut,
    SurveyTemplateOut,
)
from app.schemas.teacher import TeacherOut
from app.schemas.user import UserOut
from app.schemas.work_type import WorkTypeOut
from app.schemas.workload import (
    ActualWorkEntryOut,
    DailyWorkLogOut,
    PlannedWorkItemOut,
    WorkloadNormOut,
    WorkloadPlanVersionOut,
)


SCHEMA_MODEL_PAIRS = [
    (UserSchoolAssignmentOut, UserSchoolAccessModel, set()),
    (UserSchoolGroupAssignmentOut, UserSchoolGroupAssignmentModel, set()),
    (AuditEventOut, AuditEventModel, {"import_batch_id"}),
    (ExportJobOut, ExportJobModel, {"stored_file_key"}),
    (ImportBatchOut, ImportBatchModel, {"stored_file_key"}),
    (SchoolOut, SchoolModel, set()),
    (SchoolGroupOut, SchoolGroupModel, set()),
    (SchoolGroupSchoolOut, SchoolGroupSchoolModel, set()),
    (RoleOut, RoleModel, set()),
    (UserRoleOut, UserRoleModel, set()),
    (SurveyTemplateOut, SurveyTemplateModel, set()),
    (SurveyQuestionOut, SurveyQuestionModel, set()),
    (SurveyResponseOut, SurveyResponseModel, set()),
    (SurveyAnswerOut, SurveyAnswerModel, set()),
    (SurveyResponseRevisionOut, SurveyResponseRevisionModel, set()),
    (SurveyNLPAnalysisOut, SurveyNLPAnalysisModel, set()),
    (TeacherOut, TeacherModel, set()),
    (UserOut, UserModel, {"password_hash"}),
    (WorkTypeOut, WorkTypeModel, set()),
    (WorkloadNormOut, TeacherWorkloadNormModel, set()),
    (WorkloadPlanVersionOut, WorkloadPlanVersionModel, set()),
    (PlannedWorkItemOut, PlannedWorkItemModel, set()),
    (DailyWorkLogOut, DailyWorkLogModel, set()),
    (ActualWorkEntryOut, ActualWorkEntryModel, {"planned_work_item_id"}),
]


@pytest.mark.parametrize("schema,model,private_fields", SCHEMA_MODEL_PAIRS)
def test_read_schema_covers_model_columns(schema, model, private_fields):
    model_columns = set(model.__table__.columns.keys()) - private_fields
    assert model_columns <= set(schema.model_fields)


def test_every_model_table_has_an_explicit_product_scope():
    assert set(Base.metadata.tables) == MVP_ACTIVE_TABLES | FUTURE_TABLES


def test_public_model_package_exports_only_mvp_tables():
    exported_tables = {
        getattr(app.models, name).__tablename__ for name in app.models.__all__
    }
    assert exported_tables == MVP_ACTIVE_TABLES


def test_public_schema_package_excludes_future_features():
    future_schema_names = {
        "ExportJobCreate",
        "ImportBatchCreate",
        "PlannedWorkItemCreate",
        "SchoolGroupCreate",
        "SurveyNLPAnalysisOut",
        "SurveyResponseRevisionOut",
        "WorkloadNormCreate",
        "WorkloadPlanVersionCreate",
    }
    assert future_schema_names.isdisjoint(app.schemas.__all__)
