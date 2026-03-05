from __future__ import annotations

import json

from fastapi.testclient import TestClient

from autoresttest.inspector_api.app import create_app
from autoresttest.inspector_api.config import InspectorSettings


def _write_run(
    data_root,
    dataset_id: str,
    run_id: str,
    *,
    total_requests: int,
    success_ops: int,
    status_distribution: dict[str, int],
    operation_status_codes: dict[str, dict[str, int]],
) -> None:
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
    (trace_dir / "llm_calls.jsonl").write_text("", encoding="utf-8")
    (run_dir / "report.json").write_text(
        json.dumps(
            {
                "Total Requests Sent": total_requests,
                "Number of Successfully Processed Operations": success_ops,
                "Status Code Distribution": status_distribution,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "operation_status_codes.json").write_text(
        json.dumps(operation_status_codes),
        encoding="utf-8",
    )
    (run_dir / "q_tables.json").write_text(
        json.dumps({"OPERATION AGENT": {"opA": {"x": 1.0}}}),
        encoding="utf-8",
    )


def test_compare_endpoint_for_bills_api(tmp_path) -> None:
    data_root = tmp_path / "data"
    cache_root = tmp_path / "cache"
    static_root = tmp_path / "dist"
    dataset_id = "demo"
    baseline_run_id = "demo-20260305T000000Z-1000"
    candidate_run_id = "demo-20260305T000300Z-1000"

    _write_run(
        data_root,
        dataset_id,
        baseline_run_id,
        total_requests=10,
        success_ops=2,
        status_distribution={"200": 4, "404": 6},
        operation_status_codes={"opA": {"200": 2}, "opB": {"404": 3}},
    )
    _write_run(
        data_root,
        dataset_id,
        candidate_run_id,
        total_requests=14,
        success_ops=3,
        status_distribution={"200": 8, "404": 6},
        operation_status_codes={"opA": {"200": 4}, "opC": {"404": 2}},
    )

    app = create_app(
        InspectorSettings(
            data_root=data_root,
            cache_root=cache_root,
            static_root=static_root,
        )
    )
    client = TestClient(app)
    response = client.get(
        f"/api/datasets/{dataset_id}/compare",
        params={
            "baselineRunId": baseline_run_id,
            "candidateRunId": candidate_run_id,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["datasetId"] == dataset_id
    assert "summaryDelta" in payload
