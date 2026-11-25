"""Contract tests for the public API v1 prefix."""

from app.api.routers import surveys, workload_analytic


def test_application_endpoints_use_v1_prefix(client):
    assert client.get("/api/v1/home").status_code == 200
    assert client.get("/home").status_code == 404
    assert client.post("/users/login", json={}).status_code == 404


def test_health_check_stays_unversioned(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 404


def test_openapi_oauth_flow_uses_versioned_login(client):
    schema = client.get("/openapi.json").json()
    security_schemes = schema["components"]["securitySchemes"]
    oauth_scheme = next(
        item for item in security_schemes.values() if item["type"] == "oauth2"
    )
    assert oauth_scheme["flows"]["password"]["tokenUrl"] == "/api/v1/users/login"


def test_mvp2_endpoints_are_not_registered(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    disabled_paths = {
        "/api/v1/dashboard/planned",
        "/api/v1/schools/{school_id}/teachers/{teacher_id}/norms",
        "/api/v1/schools/{school_id}/workload/imports",
        "/api/v1/schools/{school_id}/workload/imports/validate",
        "/api/v1/schools/{school_id}/workload/exports",
        "/api/v1/schools/{school_id}/workload/template",
        "/api/v1/schools/{school_id}/survey-responses/{response_id}/nlp",
        "/api/v1/schools/{school_id}/survey-responses/{response_id}/nlp/reprocess",
        "/api/v1/schools/{school_id}/ml/teacher-wellbeing/dataset",
    }
    assert paths.isdisjoint(disabled_paths)


def test_standalone_survey_consent_endpoints_are_removed(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    removed_paths = {
        "/api/v1/schools/{school_id}/teachers/{teacher_id}/survey-consents",
        "/api/v1/schools/{school_id}/survey-consents/{consent_id}/withdraw",
    }
    assert paths.isdisjoint(removed_paths)


def test_submit_and_withdraw_routes_are_replaced_by_approve(client):
    schema_paths = client.get("/openapi.json").json()["paths"]
    paths = set(schema_paths)
    assert "/api/v1/schools/{school_id}/survey-responses/{response_id}/approve" in paths
    assert "/api/v1/schools/{school_id}/survey-responses/{response_id}/submit" not in paths
    assert "/api/v1/schools/{school_id}/survey-responses/{response_id}/withdraw" not in paths
    response_path = "/api/v1/schools/{school_id}/survey-responses/{response_id}"
    assert "patch" not in schema_paths[response_path]
    assert (
        "/api/v1/schools/{school_id}/survey-responses/{response_id}/corrections"
        in paths
    )


def test_workload_uses_one_period_report_route(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/schools/{school_id}/workload/daily" in paths
    assert "/api/v1/schools/{school_id}/workload/weekly" not in paths


def test_survey_list_replaces_duplicate_teacher_history_route(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/schools/{school_id}/survey-responses" in paths
    assert (
        "/api/v1/schools/{school_id}/teachers/{teacher_id}/survey-history"
        not in paths
    )


def test_analytics_endpoints_are_owned_by_workload_analytic_router(client):
    paths = client.get("/openapi.json").json()["paths"]
    analytics_paths = {
        route.path for route in workload_analytic.router.routes
    }
    survey_paths = {route.path for route in surveys.router.routes}
    expected = {
        "/schools/{school_id}/survey-analytics/completion",
        "/schools/{school_id}/teachers/{teacher_id}/workload-and-wellbeing",
    }
    assert expected <= analytics_paths
    assert expected.isdisjoint(survey_paths)
    for path in expected:
        assert f"/api/v1{path}" in paths
