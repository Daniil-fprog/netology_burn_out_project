from app.schemas.note import NoteCreate, NoteOut, NoteUpdate
from app.schemas.user import UserCreate, UserLogin, UserOut
from app.schemas.token import TokenOut
from app.schemas.recommendation import RecommendationCreate, RecommendationOut

# Teacher workload domain schemas are exported by semantic module. Keeping
# these imports here makes schema discovery straightforward for API modules.
from app.schemas.access import (
    UserSchoolAssignmentCreate,
    UserSchoolAssignmentOut,
    UserSchoolGroupAssignmentCreate,
    UserSchoolGroupAssignmentOut,
)
from app.schemas.organization import SchoolCreate, SchoolGroupCreate, SchoolGroupOut, SchoolOut
from app.schemas.role import RoleCreate, RoleOut, UserRoleCreate, UserRoleOut
from app.schemas.teacher import TeacherCreate, TeacherOut, TeacherUpdate
from app.schemas.work_type import WorkTypeCreate, WorkTypeOut, WorkTypeUpdate
from app.schemas.workload import (
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
