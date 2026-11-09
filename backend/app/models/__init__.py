from app.models.user import UserModel
from app.models.note import NoteModel
from app.models.recommendation import RecommendationModel
from app.models.note_recommendation import NoteRecommendationModel

# Import every semantic module so all tables are registered in Base.metadata.
# The compatibility facade keeps existing service imports working unchanged.
from app.models.teacher_domain import (
    ActualWorkEntryModel,
    AuditEventModel,
    DailyWorkLogModel,
    DailyWorkloadActualModel,
    DailyWorkloadPlanModel,
    ExportJobModel,
    ImportBatchModel,
    PlannedWorkItemModel,
    RoleModel,
    SchoolGroupModel,
    SchoolGroupSchoolModel,
    SchoolModel,
    SurveyAnswerModel,
    SurveyConsentModel,
    SurveyExportJobModel,
    SurveyMLLabelModel,
    SurveyNLPAnalysisModel,
    SurveyQuestionModel,
    SurveyResponseModel,
    SurveyResponseRevisionModel,
    SurveyTemplateModel,
    TeacherModel,
    TeacherWorkloadNormModel,
    UserRoleModel,
    UserSchoolAccessModel,
    UserSchoolGroupAssignmentModel,
    WorkTypeModel,
    WorkloadPlanVersionModel,
)
