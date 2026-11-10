from app.models.user import UserModel
from app.models.note import NoteModel
from app.models.recommendation import RecommendationModel
from app.models.note_recommendation import NoteRecommendationModel

# Import every semantic module so all tables are registered in Base.metadata.
from app.models.access import (
    UserSchoolAccessModel,
    UserSchoolGroupAssignmentModel,
)
from app.models.audit import AuditEventModel
from app.models.export import ExportJobModel
from app.models.import_batch import ImportBatchModel
from app.models.organization import SchoolGroupModel, SchoolGroupSchoolModel, SchoolModel
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
from app.models.work_type import WorkTypeModel
from app.models.workload import (
    ActualWorkEntryModel,
    DailyWorkLogModel,
    PlannedWorkItemModel,
    TeacherWorkloadNormModel,
    WorkloadPlanVersionModel,
)
