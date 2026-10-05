from fastapi.testclient import TestClient

import main


def test_smoke_health_openapi_and_locate_contract(_session_client):
    client = _session_client

    health = client.get("/healthz")
    assert health.status_code == 200

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    schema = openapi.json()
    assert "/api/locate" in schema["paths"]
    assert schema["paths"]["/api/locate"]["get"]["summary"] == "Reverse geocode coordinates"

    root = client.get("/")
    assert root.status_code == 200
