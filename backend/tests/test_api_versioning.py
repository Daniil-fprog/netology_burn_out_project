"""Contract tests for the public API v1 prefix."""


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
