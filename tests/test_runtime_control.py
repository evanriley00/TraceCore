from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _register_headers(client: TestClient):
    response = client.post(
        "/auth/register",
        json={
            "email": "control-operator@example.com",
            "password": "super-secret-password",
            "full_name": "Control Operator",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_pause_and_resume_gate_new_intake(client: TestClient):
    headers = _register_headers(client)

    pause_response = client.post("/control/pause", json={})
    assert pause_response.status_code == 200
    assert pause_response.json()["state"] == "paused"

    blocked_query = client.post(
        "/v1/query",
        headers=headers,
        json={"question": "What should I do next?", "use_cache": False},
    )
    assert blocked_query.status_code == 503
    assert blocked_query.json()["status"] == "paused"

    resume_response = client.post("/control/resume", json={})
    assert resume_response.status_code == 200
    assert resume_response.json()["state"] == "running"

    resumed_query = client.post(
        "/v1/query",
        headers=headers,
        json={"question": "What should I do next?", "use_cache": False},
    )
    assert resumed_query.status_code == 200


def test_stop_keeps_observability_alive_but_blocks_business_routes(client: TestClient):
    headers = _register_headers(client)

    stop_response = client.post("/control/stop", json={})
    assert stop_response.status_code == 200
    assert stop_response.json()["state"] == "stopped"

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["runtime_state"] == "stopped"

    blocked_runs = client.get("/v1/runs", headers=headers)
    assert blocked_runs.status_code == 503
    assert blocked_runs.json()["status"] == "stopped"

    status_response = client.get("/control/status")
    assert status_response.status_code == 200
    assert status_response.json()["state"] == "stopped"


def test_control_token_is_enforced_when_configured(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'tracecore_test.db'}",
        redis_url="redis://localhost:6399/0",
        jwt_secret="test-secret-for-tracecore-suite-1234567890",
        rate_limit_per_minute=100,
        mock_llm_enabled=True,
        control_state_path=str(tmp_path / "tracecore-control-state.json"),
        control_api_token="local-control-secret",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        unauthorized = client.get("/control/status")
        assert unauthorized.status_code == 401

        authorized = client.get(
            "/control/status",
            headers={"Authorization": "Bearer local-control-secret"},
        )
        assert authorized.status_code == 200
        assert authorized.json()["auth_required"] is True
