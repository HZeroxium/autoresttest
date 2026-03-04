from __future__ import annotations

from fastapi.testclient import TestClient

from autoresttest.inspector_api.app import create_app
from autoresttest.inspector_api.config import InspectorSettings
from autoresttest.run_artifacts import PROJECT_ROOT


def test_compare_endpoint_for_bills_api() -> None:
    app = create_app(
        InspectorSettings(
            data_root=PROJECT_ROOT / "data",
            cache_root=PROJECT_ROOT / "cache",
            static_root=PROJECT_ROOT / "apps" / "autoresttest-inspector" / "web" / "dist",
        )
    )
    client = TestClient(app)
    response = client.get(
        "/api/datasets/Bills-api/compare",
        params={
            "baselineRunId": "Bills-api-20260304T152123Z-14724",
            "candidateRunId": "Bills-api-20260304T152803Z-3764",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["datasetId"] == "Bills-api"
    assert "summaryDelta" in payload
