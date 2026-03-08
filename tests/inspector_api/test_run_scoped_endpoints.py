from __future__ import annotations

import json

from fastapi.testclient import TestClient

from autoresttest.inspector_api.app import create_app
from autoresttest.inspector_api.config import InspectorSettings


def test_run_scoped_qtable_and_artifact_endpoints(tmp_path) -> None:
    data_root = tmp_path / "data"
    cache_root = tmp_path / "cache"
    static_root = tmp_path / "dist"

    dataset_id = "demo"
    run_id = "demo-20260305T000000Z-1000"
    run_dir = data_root / dataset_id / run_id
    runtime_dir = run_dir / "metadata" / "runtime"
    trace_dir = run_dir / "metadata" / "trace"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "dataset_name": dataset_id,
        "status": "completed",
        "started_at": "2026-03-05T00:00:00+00:00",
        "updated_at": "2026-03-05T00:00:10+00:00",
        "completed_at": "2026-03-05T00:00:11+00:00",
        "paths": {
            "run_dir": str(run_dir),
            "logical_requests_trace": str(trace_dir / "logical_requests.jsonl"),
            "http_attempts_trace": str(trace_dir / "http_attempts.jsonl"),
            "llm_calls_trace": str(trace_dir / "llm_calls.jsonl"),
        },
        "counters": {},
    }
    (runtime_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (trace_dir / "logical_requests.jsonl").write_text("", encoding="utf-8")
    (trace_dir / "http_attempts.jsonl").write_text("", encoding="utf-8")
    (trace_dir / "llm_calls.jsonl").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "trace_kind": "llm_call",
                "run_id": run_id,
                "logical_request_id": 1,
                "phase": "exploration",
                "component": "value_agent",
                "logical_operation_id": "op",
                "metadata": {"llm_purpose": "seed_generation"},
                "llm": {
                    "cache_hit": False,
                    "input_tokens": 12,
                    "output_tokens": 5,
                    "duration_ms": 42,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "operation_status_codes.json").write_text(
        json.dumps({"op": {"200": 2, "400": 1}}),
        encoding="utf-8",
    )
    (run_dir / "q_tables.json").write_text(
        json.dumps({"OPERATION AGENT": {"op": {"a": 1.0}}}),
        encoding="utf-8",
    )
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "Title": "Run scoped report",
                "Run Status": "completed",
                "Snapshot Reason": "manual_snapshot",
                "Total Requests Sent": 3,
                "Status Code Distribution": {"200": 2, "400": 1},
                "Input Tokens": 12,
                "Output Tokens": 5,
                "Total Tokens": 17,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "successful_responses.json").write_text(
        json.dumps(
            {
                "op": [
                    {"status": 200, "body": {"id": 1}},
                    {"status": 200, "body": {"id": 2}},
                ],
                "other": [
                    {"status": 400, "body": {"error": "bad request"}},
                ],
            }
        ),
        encoding="utf-8",
    )

    app = create_app(
        InspectorSettings(
            data_root=data_root,
            cache_root=cache_root,
            static_root=static_root,
        )
    )
    client = TestClient(app)

    runs_response = client.get(f"/api/datasets/{dataset_id}/runs")
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert runs
    run_id = runs[0]["runId"]

    run_summary_response = client.get(f"/api/datasets/{dataset_id}/runs/{run_id}")
    assert run_summary_response.status_code == 200
    run_summary = run_summary_response.json()
    assert run_summary["reportMetrics"]["runStatus"] == "completed"
    assert run_summary["reportMetrics"]["totalTokens"] == 17
    assert run_summary["reportMetrics"]["statusCodeDistribution"] == {"200": 2, "400": 1}

    qtable_response = client.get(f"/api/datasets/{dataset_id}/runs/{run_id}/q-tables")
    assert qtable_response.status_code == 200
    assert qtable_response.json()["datasetId"] == dataset_id

    artifacts_response = client.get(f"/api/datasets/{dataset_id}/runs/{run_id}/artifacts")
    assert artifacts_response.status_code == 200
    payload = artifacts_response.json()
    assert payload["datasetId"] == dataset_id
    assert payload["runId"] == run_id

    preview_response = client.get(
        f"/api/datasets/{dataset_id}/runs/{run_id}/artifacts/successful_responses.json/preview",
        params={
            "search": "op",
            "operationId": "op",
            "limit": 1,
        },
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["artifactName"] == "successful_responses.json"
    assert preview_payload["summary"]["topLevelType"] == "dict"
    assert preview_payload["summary"]["totalItems"] == 2
    assert preview_payload["entries"][0]["key"] == "op"
    assert preview_payload["entries"][0]["valueType"] == "array"
    assert preview_payload["entries"][0]["itemCount"] == 2

    raw_artifact_response = client.get(
        f"/api/datasets/{dataset_id}/runs/{run_id}/artifacts/successful_responses.json"
    )
    assert raw_artifact_response.status_code == 200
    assert raw_artifact_response.json()["payload"]["op"][0]["status"] == 200

    old_qtable_endpoint = client.get(f"/api/datasets/{dataset_id}/q-tables")
    assert old_qtable_endpoint.status_code == 404

    old_artifacts_endpoint = client.get(f"/api/datasets/{dataset_id}/artifacts")
    assert old_artifacts_endpoint.status_code == 404
