from io import BytesIO
from decimal import Decimal
from types import SimpleNamespace

from openpyxl import Workbook

from app.models.survey import SurveyQuestionModel, SurveyTemplateModel
from app.services.survey_service import seed_surveys, validate_answers
from app.core.workload_import_contract import ACTUAL_HEADERS, NORM_HEADERS, PLAN_HEADERS
from app.services.workload_service import parse_workbook, total


def test_seed_is_idempotent_and_has_31_questions(db_session):
    assert seed_surveys(db_session)["created"] == 3
    assert seed_surveys(db_session)["created"] == 0
    assert db_session.query(SurveyTemplateModel).count() == 3
    assert db_session.query(SurveyQuestionModel).count() == 31


def test_workload_total_keeps_missingness():
    entries = [
        SimpleNamespace(duration_hours=Decimal("4.15")),
        SimpleNamespace(duration_hours=Decimal("1.06")),
        SimpleNamespace(duration_hours=Decimal("0.69")),
    ]
    assert total(entries) == Decimal("5.90")


def test_realistic_workbook_contract_is_parsed():
    wb = Workbook(); wb.remove(wb.active)
    for name, mapping in (("Учителя_нормы", NORM_HEADERS), ("План_дня", PLAN_HEADERS), ("Ежедневный_учет", ACTUAL_HEADERS)):
        ws = wb.create_sheet(name); ws.append([]); ws.append([]); ws.append([]); ws.append(list(mapping))
        if name == "Учителя_нормы": ws.append(["T001", "Математика", 24, 18, None, None])
        elif name == "План_дня": ws.append(["2026-10-19", "T001", "Учебный день", 5, 0, 1, .6, .4, .25, .35, .15, .2])
        else: ws.append(["2026-10-19", "T001", "Учебный день", 5, 0, 1.06, .69, .39, .25, .35, .15, .2, 5.29, 1.55, "ok"])
    output = BytesIO(); wb.save(output)
    parsed = parse_workbook(output.getvalue())
    assert parsed["errors"] == []
    assert (len(parsed["norms"]), len(parsed["plans"]), len(parsed["actuals"])) == (1, 1, 0)
    assert parsed["plans"][0]["planned_lessons_hours"] == Decimal("3.75")
    assert any("не импортируется" in warning["message"] for warning in parsed["warnings"])
