"""Keep public read schemas aligned with their SQLAlchemy tables."""

import pytest

from app.models.access import UserSchoolAccessModel, UserSchoolGroupAssignmentModel
from app.models.audit import AuditEventModel
from app.models.export import ExportJobModel
from app.models.import_batch import ImportBatchModel
from app.models.note import NoteModel
from app.models.note_recommendation import NoteRecommendationModel
from app.models.organization import SchoolGroupModel, SchoolGroupSchoolModel, SchoolModel
from app.models.recommendation import RecommendationModel
from app.models.role import RoleModel, UserRoleModel
from app.models.survey import (
    SurveyAnswerModel,
    SurveyConsentModel,
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
from app.schemas.note import NoteOut
from app.schemas.note_recommendation import NoteRecommendationOut
from app.schemas.organization import SchoolGroupOut, SchoolGroupSchoolOut, SchoolOut
from app.schemas.recommendation import RecommendationOut
from app.schemas.role import RoleOut, UserRoleOut
from app.schemas.survey import (
    SurveyAnswerOut,
    SurveyConsentOut,
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
    (AuditEventOut, AuditEventModel, set()),
    (ExportJobOut, ExportJobModel, {"stored_file_key"}),
    (ImportBatchOut, ImportBatchModel, {"stored_file_key"}),
    (NoteOut, NoteModel, set()),
    (NoteRecommendationOut, NoteRecommendationModel, set()),
    (SchoolOut, SchoolModel, set()),
    (SchoolGroupOut, SchoolGroupModel, set()),
    (SchoolGroupSchoolOut, SchoolGroupSchoolModel, set()),
    (RecommendationOut, RecommendationModel, set()),
    (RoleOut, RoleModel, set()),
    (UserRoleOut, UserRoleModel, set()),
    (SurveyTemplateOut, SurveyTemplateModel, set()),
    (SurveyQuestionOut, SurveyQuestionModel, set()),
    (SurveyConsentOut, SurveyConsentModel, set()),
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
    (ActualWorkEntryOut, ActualWorkEntryModel, set()),
]


@pytest.mark.parametrize("schema,model,private_fields", SCHEMA_MODEL_PAIRS)
def test_read_schema_covers_model_columns(schema, model, private_fields):
    model_columns = set(model.__table__.columns.keys()) - private_fields
    assert model_columns <= set(schema.model_fields)
