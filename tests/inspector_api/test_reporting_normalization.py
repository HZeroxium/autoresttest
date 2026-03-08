from __future__ import annotations

import json

from autoresttest.reporting import (
    build_run_inventory,
    has_valid_run_manifests,
    iter_valid_dataset_dirs,
)


def _write_jsonl(path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_run(
    data_root,
    dataset_id: str,
    run_id: str,
    *,
    manifest_status: str = "completed",
    counters: dict[str, object] | None = None,
    report: dict[str, object] | None = None,
    operation_status_codes: dict[str, dict[str, int]] | None = None,
    server_errors: dict[str, object] | None = None,
    llm_events: list[dict[str, object]] | None = None,
    write_qtables: bool = False,
) -> None:
    run_dir = data_root / dataset_id / run_id
    runtime_dir = run_dir / "metadata" / "runtime"
    trace_dir = run_dir / "metadata" / "trace"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "dataset_name": dataset_id,
        "status": manifest_status,
        "report_title": "Normalized demo run",
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
    _write_jsonl(trace_dir / "logical_requests.jsonl", [])
    _write_jsonl(trace_dir / "http_attempts.jsonl", [])
    _write_jsonl(trace_dir / "llm_calls.jsonl", llm_events or [])

    if report is not None:
        (run_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    if operation_status_codes is not None:
        (run_dir / "operation_status_codes.json").write_text(
            json.dumps(operation_status_codes),
            encoding="utf-8",
        )
    if server_errors is not None:
        (run_dir / "server_errors.json").write_text(
            json.dumps(server_errors),
            encoding="utf-8",
        )
    if write_qtables:
        (run_dir / "q_tables.json").write_text(
            json.dumps({"OPERATION AGENT": {"demo": {"score": 1.0}}}),
            encoding="utf-8",
        )


def test_build_run_inventory_normalizes_legacy_report_with_fallbacks(tmp_path) -> None:
    data_root = tmp_path / "data"
    dataset_id = "demo"
    run_id = "demo-20260305T000000Z-1000"
    _write_run(
        data_root,
        dataset_id,
        run_id,
        counters={
            "event_sequence": 12,
            "attempt_sequence": 9,
            "logical_sequence": 4,
            "llm_call_sequence": 2,
            "checkpoint_count": 1,
            "last_snapshot_reason": "checkpoint_saved",
        },
        report={
            "Title": "Legacy demo report",
            "Duration": "11.5 seconds",
        },
        operation_status_codes={
            "get_users": {"200": 2, "404": 1},
            "create_user": {"500": 1},
        },
        server_errors={"create_user": [{"message": "boom"}]},
        llm_events=[
            {
                "llm": {
                    "input_tokens": 11,
                    "output_tokens": 5,
                }
            },
            {
                "llm": {
                    "input_tokens": 3,
                    "output_tokens": 1,
                }
            },
        ],
        write_qtables=True,
    )

    inventory = build_run_inventory(data_root / dataset_id / run_id)

    assert inventory is not None
    assert inventory.metrics.report_schema == "legacy_report"
    assert inventory.metrics.run_status == "completed"
    assert inventory.metrics.snapshot_reason == "checkpoint_saved"
    assert inventory.metrics.status_code_distribution == {"200": 2, "404": 1, "500": 1}
    assert inventory.metrics.total_requests_sent == 4
    assert inventory.metrics.total_operations == 2
    assert inventory.metrics.successful_operations == 1
    assert inventory.metrics.successful_percentage == 50.0
    assert inventory.metrics.unique_server_errors == 1
    assert inventory.metrics.input_tokens == 14
    assert inventory.metrics.output_tokens == 6
    assert inventory.metrics.total_tokens == 20
    assert inventory.metrics.trace_event_count == 12
    assert inventory.metrics.http_attempt_count == 9
    assert inventory.metrics.logical_count == 4
    assert inventory.metrics.llm_call_count == 2
    assert inventory.metrics.checkpoint_count == 1
    assert inventory.has_operation_status_codes is True
    assert inventory.has_qtables is True
    assert inventory.has_trace is True
    assert "runStatus" in inventory.metrics.derived_fields
    assert "snapshotReason" in inventory.metrics.derived_fields
    assert "totalRequestsSent" in inventory.metrics.derived_fields
    assert "inputTokens" in inventory.metrics.derived_fields


def test_build_run_inventory_prefers_run_scoped_report_fields(tmp_path) -> None:
    data_root = tmp_path / "data"
    dataset_id = "demo"
    run_id = "demo-20260305T000100Z-1000"
    _write_run(
        data_root,
        dataset_id,
        run_id,
        manifest_status="completed",
        counters={
            "attempt_sequence": 99,
            "last_snapshot_reason": "manifest_reason",
        },
        report={
            "Title": "Scoped demo report",
            "Duration": 17,
            "Run Status": "running",
            "Snapshot Reason": "mid_run_snapshot",
            "Total Requests Sent": 8,
            "Status Code Distribution": {"201": 2, "400": 1},
            "Number of Total Operations": 5,
            "Number of Successfully Processed Operations": 4,
            "Percentage of Successfully Processed Operations": "80.0%",
            "Number of Unique Server Errors": 2,
            "Input Tokens": 21,
            "Output Tokens": 9,
            "Total Tokens": 30,
        },
    )

    inventory = build_run_inventory(data_root / dataset_id / run_id)

    assert inventory is not None
    assert inventory.metrics.report_schema == "run_scoped_v2"
    assert inventory.metrics.run_status == "running"
    assert inventory.metrics.snapshot_reason == "mid_run_snapshot"
    assert inventory.metrics.total_requests_sent == 8
    assert inventory.metrics.status_code_distribution == {"201": 2, "400": 1}
    assert inventory.metrics.total_operations == 5
    assert inventory.metrics.successful_operations == 4
    assert inventory.metrics.successful_percentage == 80.0
    assert inventory.metrics.unique_server_errors == 2
    assert inventory.metrics.input_tokens == 21
    assert inventory.metrics.output_tokens == 9
    assert inventory.metrics.total_tokens == 30
    assert "runStatus" not in inventory.metrics.derived_fields
    assert "snapshotReason" not in inventory.metrics.derived_fields
    assert "totalTokens" not in inventory.metrics.derived_fields


def test_iter_valid_dataset_dirs_skips_pseudo_datasets_without_manifests(tmp_path) -> None:
    data_root = tmp_path / "data"
    valid_dataset = data_root / "demo"
    invalid_dataset = data_root / "batch-runs-smoke"
    _write_run(
        data_root,
        "demo",
        "demo-20260305T000200Z-1000",
        report={"Title": "Valid report"},
    )
    (invalid_dataset / "plan-20260307T180324Z-51904" / "jobs").mkdir(
        parents=True,
        exist_ok=True,
    )

    valid_dirs = iter_valid_dataset_dirs(data_root)

    assert [path.name for path in valid_dirs] == [valid_dataset.name]
    assert has_valid_run_manifests(valid_dataset) is True
    assert has_valid_run_manifests(invalid_dataset) is False
