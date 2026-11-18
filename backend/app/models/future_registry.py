"""Register models reserved for later expansion.

Only migration tooling should import this module. MVP services must use the
public imports from :mod:`app.models` instead.
"""

from app.models.access import UserSchoolGroupAssignmentModel
from app.models.export import ExportJobModel
from app.models.import_batch import ImportBatchModel
from app.models.organization import SchoolGroupModel, SchoolGroupSchoolModel
from app.models.survey import SurveyNLPAnalysisModel, SurveyResponseRevisionModel
from app.models.workload import (
    PlannedWorkItemModel,
    TeacherWorkloadNormModel,
    WorkloadPlanVersionModel,
)

__all__ = [
    "UserSchoolGroupAssignmentModel",
    "ExportJobModel",
    "ImportBatchModel",
    "SchoolGroupModel",
    "SchoolGroupSchoolModel",
    "SurveyNLPAnalysisModel",
    "SurveyResponseRevisionModel",
    "PlannedWorkItemModel",
    "TeacherWorkloadNormModel",
    "WorkloadPlanVersionModel",
]
