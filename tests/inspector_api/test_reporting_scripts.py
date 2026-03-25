from __future__ import annotations

import csv
import json
import subprocess
import sys
import textwrap
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


def _write_http_attempt_trace(run_dir: Path, rows: list[dict[str, object]]) -> Path:
    trace_dir = run_dir / "metadata" / "trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / "http_attempts.jsonl"
    _write_jsonl(path, rows)
    return path


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


def _write_legacy_run(
    data_root: Path,
    dataset_id: str,
    run_id: str,
    *,
    report: dict[str, object] | None = None,
    operation_status_codes: dict[str, dict[str, int]] | None = None,
    write_qtables: bool = False,
) -> None:
    run_dir = data_root / dataset_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if report is not None:
        (run_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    if operation_status_codes is not None:
        (run_dir / "operation_status_codes.json").write_text(
            json.dumps(operation_status_codes),
            encoding="utf-8",
        )
    if write_qtables:
        (run_dir / "q_tables.json").write_text(
            json.dumps({"OPERATION AGENT": {"legacy": {"score": 1.0}}}),
            encoding="utf-8",
        )


def _write_jacoco_report(
    results_root: Path,
    dataset_id: str,
    tool_name: str,
    run_id: str,
    *,
    report_title: str,
    instruction_cell: str,
    instruction_display: str,
    branch_cell: str,
    branch_display: str,
    complexity_missed: int,
    complexity_total: int,
    line_missed: int,
    line_total: int,
    method_missed: int,
    method_total: int,
    class_missed: int,
    class_total: int,
    session_name: str = "demo_session",
    session_start_text: str = "Mar 17, 2026, 10:00:00 PM",
    session_dump_text: str = "Mar 17, 2026, 10:05:00 PM",
    classes_considered: int = 2,
    jacoco_version: str = "0.8.14.202510111229",
) -> Path:
    report_dir = results_root / dataset_id / tool_name / "jacoco" / run_id
    report_dir.mkdir(parents=True, exist_ok=True)

    index_html = textwrap.dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml" lang="en">
          <head>
            <meta http-equiv="Content-Type" content="text/html;charset=UTF-8"/>
            <title>{report_title}</title>
          </head>
          <body>
            <div class="breadcrumb" id="breadcrumb">
              <span class="info"><a href="jacoco-sessions.html" class="el_session">Sessions</a></span>
              <span class="el_report">{report_title}</span>
            </div>
            <h1>{report_title}</h1>
            <table class="coverage" cellspacing="0" id="coveragetable">
              <thead>
                <tr>
                  <td>Element</td>
                  <td>Missed Instructions</td>
                  <td>Cov.</td>
                  <td>Missed Branches</td>
                  <td>Cov.</td>
                  <td>Missed</td>
                  <td>Cxty</td>
                  <td>Missed</td>
                  <td>Lines</td>
                  <td>Missed</td>
                  <td>Methods</td>
                  <td>Missed</td>
                  <td>Classes</td>
                </tr>
              </thead>
              <tfoot>
                <tr>
                  <td>Total</td>
                  <td>{instruction_cell}</td>
                  <td>{instruction_display}</td>
                  <td>{branch_cell}</td>
                  <td>{branch_display}</td>
                  <td>{complexity_missed}</td>
                  <td>{complexity_total}</td>
                  <td>{line_missed}</td>
                  <td>{line_total}</td>
                  <td>{method_missed}</td>
                  <td>{method_total}</td>
                  <td>{class_missed}</td>
                  <td>{class_total}</td>
                </tr>
              </tfoot>
              <tbody>
                <tr>
                  <td><a href="example/index.html" class="el_package">example</a></td>
                  <td>0 of 0</td>
                  <td>n/a</td>
                  <td>0 of 0</td>
                  <td>n/a</td>
                  <td>0</td>
                  <td>0</td>
                  <td>0</td>
                  <td>0</td>
                  <td>0</td>
                  <td>0</td>
                  <td>0</td>
                  <td>0</td>
                </tr>
              </tbody>
            </table>
            <div class="footer"><span class="right">Created with <a href="http://www.jacoco.org/jacoco">JaCoCo</a> {jacoco_version}</span></div>
          </body>
        </html>
        """
    ).lstrip()
    (report_dir / "index.html").write_text(index_html, encoding="utf-8")

    class_rows = "\n".join(
        f'<tr><td><a href="pkg/Class{index}.html" class="el_class">pkg.Class{index}</a></td><td><code>id{index}</code></td></tr>'
        for index in range(1, classes_considered + 1)
    )
    sessions_html = textwrap.dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml" lang="en">
          <head>
            <meta http-equiv="Content-Type" content="text/html;charset=UTF-8"/>
            <title>Sessions</title>
          </head>
          <body>
            <table class="coverage" cellspacing="0">
              <thead>
                <tr><td>Session</td><td>Start Time</td><td>Dump Time</td></tr>
              </thead>
              <tbody>
                <tr><td><span class="el_session">{session_name}</span></td><td>{session_start_text}</td><td>{session_dump_text}</td></tr>
              </tbody>
            </table>
            <table class="coverage" cellspacing="0">
              <thead>
                <tr><td>Class</td><td>Id</td></tr>
              </thead>
              <tbody>
                {class_rows}
              </tbody>
            </table>
          </body>
        </html>
        """
    ).lstrip()
    (report_dir / "jacoco-sessions.html").write_text(sessions_html, encoding="utf-8")
    return report_dir


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
            "Number of Total Operations": 5,
            "Number of Successfully Processed Operations": 4,
            "Percentage of Successfully Processed Operations": "80.0%",
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
    assert by_run["demo-20260305T000000Z-1000"]["operation_coverage"] == "100.0"
    assert by_run["demo-20260305T000000Z-1000"]["has_operation_status_codes"] == "true"
    assert by_run["demo-20260305T000100Z-1000"]["report_schema"] == "run_scoped_v2"
    assert by_run["demo-20260305T000100Z-1000"]["operation_coverage"] == "80.0"
    assert by_run["demo-20260305T000100Z-1000"]["run_status"] == "failed"
    assert by_run["demo-20260305T000100Z-1000"]["has_operation_status_codes"] == "false"

    with (out_dir / "dataset_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        dataset_reader = csv.DictReader(handle)
        dataset_rows = list(dataset_reader)
    assert "run_status" in dataset_reader.fieldnames
    assert "operation_coverage" in dataset_reader.fieldnames
    assert "input_tokens" in dataset_reader.fieldnames
    assert "event_sequence" in dataset_reader.fieldnames
    assert "observed_2xx_count" in dataset_reader.fieldnames
    assert "undocumented_2xx_count" in dataset_reader.fieldnames
    assert "unique_500_operation_count" in dataset_reader.fieldnames
    dataset_by_run = {row["run"]: row for row in dataset_rows}
    assert dataset_by_run["demo-20260305T000000Z-1000"]["coverage_2xx"] == "100.0000"
    assert dataset_by_run["demo-20260305T000000Z-1000"]["observed_2xx_count"] == "1"
    assert dataset_by_run["demo-20260305T000000Z-1000"]["undocumented_2xx_count"] == "0"
    assert dataset_by_run["demo-20260305T000000Z-1000"]["coverage_4xx"] == "100.0000"
    assert dataset_by_run["demo-20260305T000000Z-1000"]["unique_500_operation_count"] == "1"
    assert dataset_by_run["demo-20260305T000000Z-1000"]["coverage_all"] == "100.0000"
    assert dataset_by_run["demo-20260305T000000Z-1000"]["operation_coverage"] == "100.0"
    assert dataset_by_run["demo-20260305T000000Z-1000"]["total_requests_sent"] == "4"
    assert dataset_by_run["demo-20260305T000000Z-1000"]["event_sequence"] == "9"
    assert dataset_by_run["demo-20260305T000100Z-1000"]["coverage_2xx"] == "0.0000"
    assert dataset_by_run["demo-20260305T000100Z-1000"]["observed_2xx_count"] == "0"
    assert dataset_by_run["demo-20260305T000100Z-1000"]["undocumented_2xx_count"] == "0"
    assert dataset_by_run["demo-20260305T000100Z-1000"]["coverage_4xx"] == "0.0000"
    assert dataset_by_run["demo-20260305T000100Z-1000"]["unique_500_operation_count"] == "0"
    assert dataset_by_run["demo-20260305T000100Z-1000"]["coverage_all"] == "0.0000"
    assert dataset_by_run["demo-20260305T000100Z-1000"]["operation_coverage"] == "80.0"
    assert dataset_by_run["demo-20260305T000100Z-1000"]["run_status"] == "failed"

    with (out_dir / "operation_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        operation_reader = csv.DictReader(handle)
        operation_rows = list(operation_reader)
    assert "matched_by" in operation_reader.fieldnames
    assert "operation_coverage" in operation_reader.fieldnames
    assert "observed_2xx_all" in operation_reader.fieldnames
    assert "undocumented_2xx" in operation_reader.fieldnames
    assert "observed_2xx_count" in operation_reader.fieldnames
    assert "undocumented_2xx_count" in operation_reader.fieldnames
    assert "observed_5xx_all" in operation_reader.fieldnames
    assert "run_status" in operation_reader.fieldnames
    operation_by_run = {row["run"]: row for row in operation_rows}
    assert operation_by_run["demo-20260305T000000Z-1000"]["matched_by"] == "normalized_operation"
    assert operation_by_run["demo-20260305T000000Z-1000"]["coverage_2xx"] == "100.0000"
    assert operation_by_run["demo-20260305T000000Z-1000"]["coverage_4xx"] == "100.0000"
    assert operation_by_run["demo-20260305T000000Z-1000"]["coverage_all"] == "100.0000"
    assert operation_by_run["demo-20260305T000000Z-1000"]["operation_coverage"] == "100.0"
    assert operation_by_run["demo-20260305T000000Z-1000"]["observed_2xx_all"] == "200"
    assert operation_by_run["demo-20260305T000000Z-1000"]["undocumented_2xx"] == ""
    assert operation_by_run["demo-20260305T000000Z-1000"]["observed_2xx_count"] == "1"
    assert operation_by_run["demo-20260305T000000Z-1000"]["undocumented_2xx_count"] == "0"
    assert operation_by_run["demo-20260305T000000Z-1000"]["observed_5xx_all"] == "500"
    assert operation_by_run["demo-20260305T000000Z-1000"]["observed_total_requests"] == "4"
    assert operation_by_run["demo-20260305T000100Z-1000"]["coverage_2xx"] == "0.0000"
    assert operation_by_run["demo-20260305T000100Z-1000"]["coverage_4xx"] == "0.0000"
    assert operation_by_run["demo-20260305T000100Z-1000"]["coverage_all"] == "0.0000"
    assert operation_by_run["demo-20260305T000100Z-1000"]["observed_2xx_count"] == "0"
    assert operation_by_run["demo-20260305T000100Z-1000"]["undocumented_2xx_count"] == "0"
    assert operation_by_run["demo-20260305T000100Z-1000"]["operation_coverage"] == "80.0"
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


def test_openapi_coverage_report_handles_2xx_substitution_and_zero_doc_coverage(
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
                "dataset": "subdemo",
                "operation": "GET /widgets/{id}",
                "2xx_code": "200",
                "4xx_code": "",
                "operation_id": "",
                "method": "GET",
                "path": "/widgets/{id}",
                "normalized_operation": "get_widgets_id",
            }
        )
        writer.writerow(
            {
                "dataset": "zero",
                "operation": "GET /empty",
                "2xx_code": "",
                "4xx_code": "",
                "operation_id": "",
                "method": "GET",
                "path": "/empty",
                "normalized_operation": "get_empty",
            }
        )

    _write_run(
        data_root,
        "subdemo",
        "subdemo-20260305T000000Z-1000",
        report={
            "Title": "2xx substitution run",
            "Total Requests Sent": 1,
        },
        operation_status_codes={
            "get_widgets_id": {"201": 1},
        },
    )
    _write_run(
        data_root,
        "zero",
        "zero-20260305T000000Z-1000",
        report={
            "Title": "Zero-doc run",
            "Total Requests Sent": 0,
        },
        operation_status_codes={
            "get_empty": {},
        },
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

    with (out_dir / "dataset_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        dataset_by_run = {row["run"]: row for row in csv.DictReader(handle)}
    assert dataset_by_run["subdemo-20260305T000000Z-1000"]["coverage_2xx"] == "100.0000"
    assert dataset_by_run["subdemo-20260305T000000Z-1000"]["coverage_4xx"] == "100.0000"
    assert dataset_by_run["subdemo-20260305T000000Z-1000"]["coverage_all"] == "100.0000"
    assert dataset_by_run["subdemo-20260305T000000Z-1000"]["observed_2xx_count"] == "1"
    assert dataset_by_run["subdemo-20260305T000000Z-1000"]["undocumented_2xx_count"] == "1"
    assert dataset_by_run["zero-20260305T000000Z-1000"]["doc_2xx_count"] == "0"
    assert dataset_by_run["zero-20260305T000000Z-1000"]["doc_4xx_count"] == "0"
    assert dataset_by_run["zero-20260305T000000Z-1000"]["coverage_2xx"] == "100.0000"
    assert dataset_by_run["zero-20260305T000000Z-1000"]["coverage_4xx"] == "100.0000"
    assert dataset_by_run["zero-20260305T000000Z-1000"]["coverage_all"] == "100.0000"

    with (out_dir / "operation_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        operation_by_run = {row["run"]: row for row in csv.DictReader(handle)}
    assert operation_by_run["subdemo-20260305T000000Z-1000"]["hit_2xx"] == "200"
    assert operation_by_run["subdemo-20260305T000000Z-1000"]["observed_2xx_all"] == "201"
    assert operation_by_run["subdemo-20260305T000000Z-1000"]["undocumented_2xx"] == "201"
    assert operation_by_run["subdemo-20260305T000000Z-1000"]["coverage_2xx"] == "100.0000"
    assert operation_by_run["subdemo-20260305T000000Z-1000"]["coverage_4xx"] == "100.0000"
    assert operation_by_run["subdemo-20260305T000000Z-1000"]["coverage_all"] == "100.0000"
    assert operation_by_run["zero-20260305T000000Z-1000"]["doc_2xx_count"] == "0"
    assert operation_by_run["zero-20260305T000000Z-1000"]["doc_4xx_count"] == "0"
    assert operation_by_run["zero-20260305T000000Z-1000"]["coverage_2xx"] == "100.0000"
    assert operation_by_run["zero-20260305T000000Z-1000"]["coverage_4xx"] == "100.0000"
    assert operation_by_run["zero-20260305T000000Z-1000"]["coverage_all"] == "100.0000"


def test_openapi_coverage_report_counts_unique_500_per_operation(tmp_path) -> None:
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
        for operation, normalized in [
            ("GET /alpha", "get_alpha"),
            ("GET /beta", "get_beta"),
            ("GET /gamma", "get_gamma"),
        ]:
            writer.writerow(
                {
                    "dataset": "fivehundred",
                    "operation": operation,
                    "2xx_code": "200",
                    "4xx_code": "",
                    "operation_id": "",
                    "method": "GET",
                    "path": operation.split(maxsplit=1)[1],
                    "normalized_operation": normalized,
                }
            )

    _write_run(
        data_root,
        "fivehundred",
        "fivehundred-20260319T000000Z-1000",
        report={
            "Title": "Exact 500 uniqueness run",
            "Total Requests Sent": 112,
        },
        operation_status_codes={
            "get_alpha": {"500": 99},
            "get_beta": {"500": 1, "503": 5},
            "get_gamma": {"503": 7},
        },
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

    with (out_dir / "dataset_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        dataset_by_run = {row["run"]: row for row in csv.DictReader(handle)}
    assert (
        dataset_by_run["fivehundred-20260319T000000Z-1000"]["unique_500_operation_count"]
        == "2"
    )

    with (out_dir / "operation_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        operation_rows = list(csv.DictReader(handle))
    operation_by_name = {
        row["operation"]: row
        for row in operation_rows
        if row["run"] == "fivehundred-20260319T000000Z-1000"
    }
    assert operation_by_name["GET /alpha"]["observed_5xx_all"] == "500"
    assert operation_by_name["GET /beta"]["observed_5xx_all"] == "500|503"
    assert operation_by_name["GET /gamma"]["observed_5xx_all"] == "503"


def test_http_attempt_phase_extract_writes_minimal_phase_outputs(tmp_path) -> None:
    run_dir = tmp_path / "data" / "demo" / "demo-20260325T000000Z-1000"
    _write_http_attempt_trace(
        run_dir,
        [
            {
                "trace_kind": "http_attempt",
                "phase": "value_agent_q_table_generation",
                "logical_operation_id": "bootstrap_alpha",
                "url": "https://example.test/alpha",
                "response": {"status_code": 400},
                "ignored": "value",
            },
            {
                "trace_kind": "http_attempt",
                "phase": "marl_request_generation",
                "logical_operation_id": "marl_beta",
                "url": "https://example.test/beta",
                "response": {"status_code": None},
            },
            {
                "trace_kind": "llm_call",
                "phase": "marl_request_generation",
                "logical_operation_id": "should_be_ignored",
                "url": "https://example.test/ignored",
                "response": {"status_code": 500},
            },
            {
                "phase": "value_agent_q_table_generation",
                "operation_id": "bootstrap_gamma",
                "url": "https://example.test/gamma",
                "status_code": 201,
            },
            {
                "trace_kind": "http_attempt",
                "phase": "exploration",
                "logical_operation_id": "other_phase",
                "url": "https://example.test/other",
                "response": {"status_code": 202},
            },
            {
                "trace_kind": "http_attempt",
                "phase": "marl_request_generation",
                "logical_operation_id": "marl_delta",
                "url": "https://example.test/delta",
                "response": {"status_code": 503},
            },
        ],
    )

    result = _run_script("tools/http_attempt_phase_extract.py", str(run_dir))

    assert "[OK] Wrote 2 value_agent_q_table_generation rows:" in result.stdout
    assert "[OK] Wrote 2 marl_request_generation rows:" in result.stdout

    value_agent_path = run_dir / "value_agent_q_table_generation.json"
    marl_path = run_dir / "marl.json"
    assert value_agent_path.exists()
    assert marl_path.exists()

    value_agent_rows = json.loads(value_agent_path.read_text(encoding="utf-8"))
    marl_rows = json.loads(marl_path.read_text(encoding="utf-8"))

    assert value_agent_rows == [
        {
            "operation_id": "bootstrap_alpha",
            "url": "https://example.test/alpha",
            "status_code": 400,
        },
        {
            "operation_id": "bootstrap_gamma",
            "url": "https://example.test/gamma",
            "status_code": 201,
        },
    ]
    assert marl_rows == [
        {
            "operation_id": "marl_beta",
            "url": "https://example.test/beta",
            "status_code": None,
        },
        {
            "operation_id": "marl_delta",
            "url": "https://example.test/delta",
            "status_code": 503,
        },
    ]


def test_jacoco_overall_report_parses_overall_totals(tmp_path) -> None:
    results_root = tmp_path / "results"
    output_path = tmp_path / "coverage_results" / "jacoco_overall_coverage.csv"
    report_dir = _write_jacoco_report(
        results_root,
        "demo-service",
        "manual",
        "20260317_123456",
        report_title="Demo Coverage",
        instruction_cell="1 of 3",
        instruction_display="66%",
        branch_cell="1 of 6",
        branch_display="83%",
        complexity_missed=2,
        complexity_total=5,
        line_missed=4,
        line_total=10,
        method_missed=1,
        method_total=4,
        class_missed=1,
        class_total=2,
        session_name="demo_session",
        session_start_text="Mar 17, 2026, 10:00:00 PM",
        session_dump_text="Mar 17, 2026, 10:05:00 PM",
        classes_considered=3,
    )

    _run_script(
        "tools/jacoco_overall_report.py",
        "--results-root",
        str(results_root),
        "--output",
        str(output_path),
    )

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]
    assert row["dataset"] == "demo-service"
    assert row["tool_name"] == "manual"
    assert row["run_id"] == "20260317_123456"
    assert Path(row["report_dir"]).name == report_dir.name
    assert Path(row["index_html"]).name == "index.html"
    assert Path(row["sessions_html"]).name == "jacoco-sessions.html"
    assert row["report_title"] == "Demo Coverage"
    assert row["jacoco_version"] == "0.8.14.202510111229"
    assert row["session_name"] == "demo_session"
    assert row["session_start_text"] == "Mar 17, 2026, 10:00:00 PM"
    assert row["session_dump_text"] == "Mar 17, 2026, 10:05:00 PM"
    assert row["sessions_count"] == "1"
    assert row["classes_considered_count"] == "3"
    assert row["instruction_missed"] == "1"
    assert row["instruction_covered"] == "2"
    assert row["instruction_total"] == "3"
    assert row["instruction_coverage_pct"] == "66.6667"
    assert row["instruction_coverage_display"] == "66%"
    assert row["instruction_display_matches_counts"] == "true"
    assert row["branch_missed"] == "1"
    assert row["branch_covered"] == "5"
    assert row["branch_total"] == "6"
    assert row["branch_coverage_pct"] == "83.3333"
    assert row["branch_coverage_display"] == "83%"
    assert row["branch_display_matches_counts"] == "true"
    assert row["complexity_missed"] == "2"
    assert row["complexity_covered"] == "3"
    assert row["complexity_total"] == "5"
    assert row["complexity_coverage_pct"] == "60.0000"
    assert row["line_missed"] == "4"
    assert row["line_covered"] == "6"
    assert row["line_total"] == "10"
    assert row["line_coverage_pct"] == "60.0000"
    assert row["method_missed"] == "1"
    assert row["method_covered"] == "3"
    assert row["method_total"] == "4"
    assert row["method_coverage_pct"] == "75.0000"
    assert row["class_missed"] == "1"
    assert row["class_covered"] == "1"
    assert row["class_total"] == "2"
    assert row["class_coverage_pct"] == "50.0000"


def test_jacoco_overall_report_handles_branch_na(tmp_path) -> None:
    results_root = tmp_path / "results"
    output_path = tmp_path / "coverage_results" / "jacoco_overall_coverage.csv"
    _write_jacoco_report(
        results_root,
        "demo-service",
        "smoke",
        "20260317_223000",
        report_title="Demo Coverage",
        instruction_cell="0 of 1",
        instruction_display="100%",
        branch_cell="0 of 0",
        branch_display="n/a",
        complexity_missed=0,
        complexity_total=1,
        line_missed=0,
        line_total=1,
        method_missed=0,
        method_total=1,
        class_missed=0,
        class_total=1,
        classes_considered=1,
    )

    _run_script(
        "tools/jacoco_overall_report.py",
        "--results-root",
        str(results_root),
        "--output",
        str(output_path),
    )

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    row = rows[0]
    assert row["branch_missed"] == "0"
    assert row["branch_covered"] == "0"
    assert row["branch_total"] == "0"
    assert row["branch_coverage_pct"] == ""
    assert row["branch_coverage_display"] == "n/a"
    assert row["branch_display_matches_counts"] == "true"


def test_openapi_coverage_report_includes_legacy_runs_without_manifest(tmp_path) -> None:
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

    _write_legacy_run(
        data_root,
        "demo",
        "demo-run1",
        report={
            "Title": "Legacy manifest-free run",
            "Duration": "42 seconds",
            "Total Requests Sent": 2,
            "Status Code Distribution": {"200": 1, "404": 1},
            "Number of Total Operations": 1,
            "Number of Successfully Processed Operations": 1,
            "Percentage of Successfully Processed Operations": "100.0%",
        },
        operation_status_codes={
            "get_users_id": {"200": 1, "404": 1},
        },
        write_qtables=True,
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
        inventory_by_run = {row["run"]: row for row in csv.DictReader(handle)}
    assert "demo-run1" in inventory_by_run
    assert inventory_by_run["demo-run1"]["report_schema"] == "legacy_report"
    assert inventory_by_run["demo-run1"]["has_report"] == "true"
    assert inventory_by_run["demo-run1"]["has_operation_status_codes"] == "true"
    assert inventory_by_run["demo-run1"]["has_trace"] == "false"
    assert inventory_by_run["demo-run1"]["checkpoint_count"] == "0"

    with (out_dir / "dataset_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        dataset_by_run = {row["run"]: row for row in csv.DictReader(handle)}
    assert dataset_by_run["demo-run1"]["coverage_2xx"] == "100.0000"
    assert dataset_by_run["demo-run1"]["coverage_4xx"] == "100.0000"
    assert dataset_by_run["demo-run1"]["unique_500_operation_count"] == "0"
    assert dataset_by_run["demo-run1"]["coverage_all"] == "100.0000"
    assert dataset_by_run["demo-run1"]["operation_coverage"] == "100.0"
    assert dataset_by_run["demo-run1"]["total_requests_sent"] == "2"

    with (out_dir / "operation_coverage.csv").open("r", encoding="utf-8", newline="") as handle:
        operation_by_run = {row["run"]: row for row in csv.DictReader(handle)}
    assert operation_by_run["demo-run1"]["matched_by"] == "normalized_operation"
    assert operation_by_run["demo-run1"]["observed_2xx_all"] == "200"
    assert operation_by_run["demo-run1"]["observed_4xx_all"] == "404"
    assert operation_by_run["demo-run1"]["coverage_all"] == "100.0000"
