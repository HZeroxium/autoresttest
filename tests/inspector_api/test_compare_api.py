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
    total_requests: int | None = None,
    success_ops: int | None = None,
    status_distribution: dict[str, int] | None = None,
    operation_status_codes: dict[str, dict[str, int]] | None = None,
    report_payload: dict[str, object] | None = None,
    llm_events: list[dict[str, object]] | None = None,
    counters: dict[str, object] | None = None,
    server_errors: dict[str, object] | None = None,
    status: str = "completed",
) -> None:
    run_dir = data_root / dataset_id / run_id
    runtime_dir = run_dir / "metadata" / "runtime"
    trace_dir = run_dir / "metadata" / "trace"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "dataset_name": dataset_id,
        "status": status,
        "started_at": "2026-03-05T00:00:00+00:00",
        "updated_at": "2026-03-05T00:00:10+00:00",
        "completed_at": "2026-03-05T00:00:11+00:00",
        "paths": {
            "run_dir": str(run_dir),
            "logical_requests_trace": str(trace_dir / "logical_requests.jsonl"),
            "http_attempts_trace": str(trace_dir / "http_attempts.jsonl"),
            "llm_calls_trace": str(trace_dir / "llm_calls.jsonl"),
        },
        "counters": counters or {},
    }
    (runtime_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (trace_dir / "logical_requests.jsonl").write_text("", encoding="utf-8")
    (trace_dir / "http_attempts.jsonl").write_text("", encoding="utf-8")
    (trace_dir / "llm_calls.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in (llm_events or [])),
        encoding="utf-8",
    )
    payload = report_payload
    if payload is None:
        payload = {
            "Total Requests Sent": total_requests,
            "Number of Successfully Processed Operations": success_ops,
            "Status Code Distribution": status_distribution,
        }
    (run_dir / "report.json").write_text(json.dumps(payload), encoding="utf-8")
    if operation_status_codes is not None:
        (run_dir / "operation_status_codes.json").write_text(
            json.dumps(operation_status_codes),
            encoding="utf-8",
        )
    (run_dir / "q_tables.json").write_text(
        json.dumps({"OPERATION AGENT": {"opA": {"x": 1.0}}}),
        encoding="utf-8",
    )
    if server_errors is not None:
        (run_dir / "server_errors.json").write_text(
            json.dumps(server_errors),
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


def test_compare_endpoint_includes_token_and_status_deltas(tmp_path) -> None:
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
        report_payload={
            "Title": "Legacy baseline",
            "Duration": "10.0 seconds",
        },
        operation_status_codes={"opA": {"200": 2}},
        llm_events=[
            {
                "llm": {
                    "input_tokens": 9,
                    "output_tokens": 6,
                }
            }
        ],
        counters={"llm_call_sequence": 1},
        server_errors={"opA": [{"message": "boom"}]},
    )
    _write_run(
        data_root,
        dataset_id,
        candidate_run_id,
        report_payload={
            "Title": "Scoped candidate",
            "Run Status": "interrupted",
            "Snapshot Reason": "manual_stop",
            "Total Requests Sent": 9,
            "Number of Successfully Processed Operations": 2,
            "Status Code Distribution": {"200": 4, "500": 1},
            "Input Tokens": 25,
            "Output Tokens": 15,
            "Total Tokens": 40,
            "Number of Unique Server Errors": 2,
        },
        operation_status_codes={"opA": {"200": 4}, "opB": {"500": 1}},
        llm_events=[
            {
                "llm": {
                    "input_tokens": 5,
                    "output_tokens": 4,
                }
            },
            {
                "llm": {
                    "input_tokens": 7,
                    "output_tokens": 3,
                }
            },
        ],
        counters={"llm_call_sequence": 2},
        server_errors={"opB": [{"message": "boom-1"}, {"message": "boom-2"}]},
        status="failed",
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
    assert payload["summaryDelta"]["totalRequests"] == 7
    assert payload["summaryDelta"]["totalTokens"] == 25
    assert payload["summaryDelta"]["statusCodes"] == {"200": 2, "500": 1}
    assert payload["llmDelta"] == {
        "baselineCalls": 1,
        "candidateCalls": 2,
        "deltaCalls": 1,
        "baselineTokens": 15,
        "candidateTokens": 40,
        "deltaTokens": 25,
    }
    assert payload["baselineMetrics"]["reportSchema"] == "legacy_report"
    assert payload["baselineMetrics"]["totalTokens"] == 15
    assert payload["candidateMetrics"]["reportSchema"] == "run_scoped_v2"
    assert payload["candidateMetrics"]["runStatus"] == "interrupted"
    assert payload["candidateMetrics"]["snapshotReason"] == "manual_stop"
