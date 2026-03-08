from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_run(
    data_root: Path,
    dataset_id: str,
    run_id: str,
    *,
    counters: dict[str, object] | None = None,
    report: dict[str, object] | None = None,
    operation_status_codes: dict[str, dict[str, int]] | None = None,
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
    if write_qtables:
        (run_dir / "q_tables.json").write_text(
            json.dumps({"OPERATION AGENT": {"demo": {"score": 1.0}}}),
            encoding="utf-8",
        )


def test_openapi_status_summary_appends_enriched_columns(tmp_path) -> None:
    spec_path = tmp_path / "datasets" / "demo.json"
    output_path = tmp_path / "openapi_status_summary.csv"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "paths": {
                    "/users/{id}": {
                        "get": {
                            "operationId": "getUserById",
                            "responses": {
                                "200": {"description": "ok"},
                                "default": {
                                    "description": "Not found when the user is missing",
                                },
                            },
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    _run_script(
        "tools/openapi_status_summary.py",
        "--inputs",
        str(spec_path),
        "--output",
        str(output_path),
    )

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "dataset",
            "operation",
            "2xx_code",
            "4xx_code",
            "operation_id",
            "method",
            "path",
            "normalized_operation",
        ]
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0] == {
        "dataset": "demo",
        "operation": "getUserById",
        "2xx_code": "200",
        "4xx_code": "400|404",
        "operation_id": "getUserById",
        "method": "GET",
        "path": "/users/{id}",
        "normalized_operation": "getuserbyid",
    }


def test_openapi_coverage_report_emits_enriched_csvs_and_skips_pseudo_datasets(
    tmp_path,
) -> None:
    summary_csv = tmp_path / "datasets" / "openapi_status_summary.csv"
    data_root = tmp_path / "data"
    out_dir = tmp_path / "coverage_results"
    summary_csv.parent.mkdir(parents=True, exist_ok=True)
    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "dataset",
                "operation",
                "2xx_code",
                "4xx_code",
                "operation_id",
                "method",
                "path",
                "normalized_operation",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "dataset": "demo",
                "operation": "GET /users/{id}",
                "2xx_code": "200",
                "4xx_code": "404",
                "operation_id": "",
                "method": "GET",
                "path": "/users/{id}",
                "normalized_operation": "get_users_id",
            }
        )

    _write_run(
        data_root,
        "demo",
        "demo-20260305T000000Z-1000",
        counters={
            "event_sequence": 9,
            "attempt_sequence": 4,
            "logical_sequence": 2,
            "llm_call_sequence": 2,
            "checkpoint_count": 1,
            "last_snapshot_reason": "report_checkpoint",
        },
        report={
            "Title": "Legacy coverage run",
            "Duration": "11.0 seconds",
        },
        operation_status_codes={
            "get_users_id": {"200": 2, "404": 1, "500": 1},
        },
        llm_events=[
            {"llm": {"input_tokens": 7, "output_tokens": 3}},
            {"llm": {"input_tokens": 2, "output_tokens": 1}},
        ],
        write_qtables=True,
    )
    _write_run(
        data_root,
        "demo",
        "demo-20260305T000100Z-1000",
        counters={
            "event_sequence": 6,
            "attempt_sequence": 6,
            "logical_sequence": 3,
            "llm_call_sequence": 0,
        },
        report={
            "Title": "Scoped coverage run",
            "Run Status": "failed",
            "Snapshot Reason": "manual_stop",
            "Total Requests Sent": 6,
            "Status Code Distribution": {"503": 6},
            "Input Tokens": 4,
            "Output Tokens": 6,
            "Total Tokens": 10,
        },
    )
    (data_root / "batch-runs-smoke" / "plan-20260307T180324Z-51904" / "jobs").mkdir(
        parents=True,
        exist_ok=True,
    )

    _run_script(
        "tools/openapi_coverage_report.py",
        "--summary-csv",
        str(summary_csv),
        "--data-root",
        str(data_root),
        "--out-dir",
        str(out_dir),
    )

    with (out_dir / "run_inventory.csv").open("r", encoding="utf-8", newline="") as handle:
        inventory_reader = csv.DictReader(handle)
        inventory_rows = list(inventory_reader)
    assert len(inventory_rows) == 2
    assert {row["dataset"] for row in inventory_rows} == {"demo"}
    by_run = {row["run"]: row for row in inventory_rows}
    assert by_run["demo-20260305T000000Z-1000"]["report_schema"] == "legacy_report"
    assert by_run["demo-20260305T000000Z-1000"]["total_tokens"] == "13"
    assert by_run["demo-20260305T000000Z-1000"]["has_operation_status_codes"] == "true"
    assert by_run["demo-20260305T000100Z-1000"]["report_schema"] == "run_scoped_v2"
    assert by_run["demo-20260305T000100Z-1000"]["run_status"] == "failed"
    assert by_run["demo-20260305T000100Z-1000"]["has_operation_status_codes"] == "false"

    with (out_dir / "dataset_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        dataset_reader = csv.DictReader(handle)
        dataset_rows = list(dataset_reader)
    assert "run_status" in dataset_reader.fieldnames
    assert "input_tokens" in dataset_reader.fieldnames
    assert "event_sequence" in dataset_reader.fieldnames
    dataset_by_run = {row["run"]: row for row in dataset_rows}
    assert dataset_by_run["demo-20260305T000000Z-1000"]["total_requests_sent"] == "4"
    assert dataset_by_run["demo-20260305T000000Z-1000"]["event_sequence"] == "9"
    assert dataset_by_run["demo-20260305T000100Z-1000"]["run_status"] == "failed"

    with (out_dir / "operation_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        operation_reader = csv.DictReader(handle)
        operation_rows = list(operation_reader)
    assert "matched_by" in operation_reader.fieldnames
    assert "observed_2xx_all" in operation_reader.fieldnames
    assert "observed_5xx_all" in operation_reader.fieldnames
    assert "run_status" in operation_reader.fieldnames
    operation_by_run = {row["run"]: row for row in operation_rows}
    assert operation_by_run["demo-20260305T000000Z-1000"]["matched_by"] == "normalized_operation"
    assert operation_by_run["demo-20260305T000000Z-1000"]["observed_2xx_all"] == "200"
    assert operation_by_run["demo-20260305T000000Z-1000"]["observed_5xx_all"] == "500"
    assert operation_by_run["demo-20260305T000000Z-1000"]["observed_total_requests"] == "4"
    assert operation_by_run["demo-20260305T000100Z-1000"]["run_status"] == "failed"

    with (out_dir / "operation_matching_issues.csv").open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        issues = list(csv.DictReader(handle))
    assert {
        (row["run"], row["kind"])
        for row in issues
    } >= {("demo-20260305T000100Z-1000", "run_missing_operation_status_codes")}
