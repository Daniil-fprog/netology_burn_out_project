"""Public Pydantic schema surface for MVP service development."""

from app.schemas.user import UserCreate, UserLogin, UserOut
from app.schemas.token import TokenOut
from app.schemas.access import (
    AccessCreate,
    UserSchoolAssignmentCreate,
    UserSchoolAssignmentOut,
)
from app.schemas.audit import AuditEventOut
from app.schemas.organization import (
    SchoolCreate,
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
    SurveyDraftPatch,
    SurveyQuestionDefinition,
    SurveyQuestionOut,
    SurveyResponseCreate,
    SurveyResponseRequest,
    SurveyResponseOut,
    SurveyTemplateCreate,
    SurveyTemplateOut,
)
from app.schemas.workload import (
    ActualPatch,
    ActualWorkEntryCreate,
    ActualWorkEntryOut,
    DailyWorkLogCreate,
    DailyWorkLogOut,
)

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserOut",
    "TokenOut",
    "AccessCreate",
    "UserSchoolAssignmentCreate",
    "UserSchoolAssignmentOut",
    "AuditEventOut",
    "SchoolCreate",
    "SchoolOut",
    "SchoolUpdate",
    "RoleCreate",
    "RoleOut",
    "UserRoleCreate",
    "UserRoleOut",
    "TeacherCreate",
    "TeacherOut",
    "TeacherUpdate",
    "WorkTypeCreate",
    "WorkTypeOut",
    "WorkTypeUpdate",
    "SurveyAnswerOut",
    "SurveyConsentRequest",
    "SurveyConsentCreate",
    "SurveyConsentOut",
    "SurveyDraftPatch",
    "SurveyQuestionDefinition",
    "SurveyQuestionOut",
    "SurveyResponseCreate",
    "SurveyResponseRequest",
    "SurveyResponseOut",
    "SurveyTemplateCreate",
    "SurveyTemplateOut",
    "ActualPatch",
    "ActualWorkEntryCreate",
    "ActualWorkEntryOut",
    "DailyWorkLogCreate",
    "DailyWorkLogOut",
]
