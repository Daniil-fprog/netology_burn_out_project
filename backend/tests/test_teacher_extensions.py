from io import BytesIO
from decimal import Decimal

from openpyxl import Workbook

from app.models.teacher_domain import DailyWorkloadActualModel, SurveyQuestionModel, SurveyTemplateModel
from app.services.survey_service import seed_surveys, validate_answers
from app.services.workload_service import ACTUAL_HEADERS, NORM_HEADERS, PLAN_HEADERS, parse_workbook, total


def test_seed_is_idempotent_and_has_31_questions(db_session):
    assert seed_surveys(db_session)["created"] == 3
    assert seed_surveys(db_session)["created"] == 0
    assert db_session.query(SurveyTemplateModel).count() == 3
    assert db_session.query(SurveyQuestionModel).count() == 31


def test_workload_total_keeps_missingness():
    actual = DailyWorkloadActualModel(
        actual_teaching_block_hours=Decimal("4.15"), actual_preparation_hours=Decimal("1.06"),
        actual_grading_hours=Decimal("0.69"), actual_documentation_hours=Decimal("0.39"),
        actual_parent_communication_hours=Decimal("0.25"), actual_class_management_hours=Decimal("0.35"),
        actual_meetings_methodology_hours=Decimal("0.15"), actual_other_hours=Decimal("0.20"),
    )
    assert total(actual, "actual") == (Decimal("7.24"), True)
    actual.actual_other_hours = None
    assert total(actual, "actual") == (None, False)


def test_realistic_workbook_contract_is_parsed():
    wb = Workbook(); wb.remove(wb.active)
    for name, mapping in (("Учителя_нормы", NORM_HEADERS), ("План_дня", PLAN_HEADERS), ("Ежедневный_учет", ACTUAL_HEADERS)):
        ws = wb.create_sheet(name); ws.append([]); ws.append([]); ws.append([]); ws.append(list(mapping))
        if name == "Учителя_нормы": ws.append(["T001", "Математика", 24, 18, None, None])
        elif name == "План_дня": ws.append(["2026-10-19", "T001", "Учебный день", 5, 0, 4.15, 1, .6, .4, .25, .35, .15, .2])
        else: ws.append(["2026-10-19", "T001", "Учебный день", 5, 0, 4.15, 1.06, .69, .39, .25, .35, .15, .2, 5.29, 1.95, 3, 3, "ok"])
    output = BytesIO(); wb.save(output)
    parsed = parse_workbook(output.getvalue())
    assert parsed["errors"] == []
    assert (len(parsed["norms"]), len(parsed["plans"]), len(parsed["actuals"])) == (1, 1, 1)
