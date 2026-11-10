from app.schemas.note import NoteCreate, NoteOut, NoteUpdate
from app.schemas.user import UserCreate, UserLogin, UserOut
from app.schemas.token import TokenOut
from app.schemas.recommendation import RecommendationCreate, RecommendationOut
from app.schemas.note_recommendation import NoteRecommendationOut
from app.schemas.analytics import PlannedDashboardOut

# Teacher workload domain schemas are exported by semantic module. Keeping
# these imports here makes schema discovery straightforward for API modules.
from app.schemas.access import (
    AccessCreate,
    UserSchoolAssignmentCreate,
    UserSchoolAssignmentOut,
    UserSchoolGroupAssignmentCreate,
    UserSchoolGroupAssignmentOut,
)
from app.schemas.audit import AuditEventOut
from app.schemas.export import ExportJobCreate, ExportJobOut
from app.schemas.import_batch import ImportBatchCreate, ImportBatchOut
from app.schemas.organization import (
    SchoolCreate,
    SchoolGroupCreate,
    SchoolGroupOut,
    SchoolGroupSchoolCreate,
    SchoolGroupSchoolOut,
    SchoolOut,
    SchoolUpdate,
)
from app.schemas.role import RoleCreate, RoleOut, UserRoleCreate, UserRoleOut
from app.schemas.teacher import TeacherCreate, TeacherOut, TeacherUpdate
from app.schemas.work_type import WorkTypeCreate, WorkTypeOut, WorkTypeUpdate
from app.schemas.survey import (
    SurveyAnswerOut,
    SurveyConsentRequest,
    SurveyConsentCreate,
    SurveyConsentOut,
    SurveyCorrectionRequest,
    SurveyDraftPatch,
    SurveyNLPAnalysisOut,
    SurveyQuestionDefinition,
    SurveyQuestionOut,
    SurveyResponseCreate,
    SurveyResponseRequest,
    SurveyResponseOut,
    SurveyResponseRevisionOut,
    SurveyTemplateCreate,
    SurveyTemplateOut,
)
from app.schemas.workload import (
    ActualPatch,
    ActualWorkEntryCreate,
    ActualWorkEntryOut,
    DailyWorkLogCreate,
    DailyWorkLogOut,
    PlannedWorkItemCreate,
    PlannedWorkItemOut,
    WorkloadNormCreate,
    WorkloadNormOut,
    WorkloadPlanVersionCreate,
    WorkloadPlanVersionOut,
)
