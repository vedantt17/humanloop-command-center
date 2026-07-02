from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_summary_seeded_scale(client: TestClient) -> None:
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["active_projects"] == 40
    assert sum(item["count"] for item in payload["pipeline_funnel"]) == 12000
    assert payload["quality_flag_categories"]


def test_projects_and_export(client: TestClient) -> None:
    projects = client.get("/api/projects").json()
    assert len(projects) == 40
    export_response = client.get(f"/api/projects/{projects[0]['id']}/export?format=csv")
    assert export_response.status_code == 200
    assert "prompt,model_response,final_human_rating" in export_response.text
