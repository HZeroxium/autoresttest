from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ARTIFACT_FILES = (
    "report.json",
    "operation_status_codes.json",
    "q_tables.json",
    "server_errors.json",
    "successful_parameters.json",
    "successful_bodies.json",
    "successful_primitives.json",
    "successful_responses.json",
)

TRACE_STREAM_FILES = {
    "logical_requests": "logical_requests.jsonl",
    "http_attempts": "http_attempts.jsonl",
    "llm_calls": "llm_calls.jsonl",
}

JsonLoader = Callable[[Path], Any]
JsonlLoader = Callable[[Path], list[dict[str, Any]]]


@dataclass(frozen=True)
class NormalizedReportMetrics:
    title: str | None
    duration_seconds: float | None
    run_status: str
    snapshot_reason: str | None
    total_requests_sent: int
    status_code_distribution: dict[str, int]
    total_operations: int | None
    successful_operations: int | None
    successful_percentage: float | None
    unique_server_errors: int | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    trace_event_count: int | None
    logical_count: int | None
    http_attempt_count: int | None
    llm_call_count: int | None
    checkpoint_count: int | None
    report_schema: str
    derived_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "durationSeconds": self.duration_seconds,
            "runStatus": self.run_status,
            "snapshotReason": self.snapshot_reason,
            "totalRequestsSent": self.total_requests_sent,
            "statusCodeDistribution": self.status_code_distribution,
            "totalOperations": self.total_operations,
            "successfulOperations": self.successful_operations,
            "successfulPercentage": self.successful_percentage,
            "uniqueServerErrors": self.unique_server_errors,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "totalTokens": self.total_tokens,
            "traceEventCount": self.trace_event_count,
            "logicalCount": self.logical_count,
            "httpAttemptCount": self.http_attempt_count,
            "llmCallCount": self.llm_call_count,
            "checkpointCount": self.checkpoint_count,
            "reportSchema": self.report_schema,
            "derivedFields": list(self.derived_fields),
        }


@dataclass(frozen=True)
class RunInventory:
    dataset: str
    run: str
    run_dir: Path
    manifest_path: Path
    manifest: dict[str, Any]
    report: dict[str, Any] | None
    operation_status_codes: dict[str, dict[str, int]] | None
    server_errors: dict[str, Any] | None
    metrics: NormalizedReportMetrics
    started_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None
    has_report: bool
    has_operation_status_codes: bool
    has_qtables: bool
    has_trace: bool
    trace_availability: dict[str, bool] = field(default_factory=dict)
    counters: dict[str, Any] = field(default_factory=dict)
    status_code_distribution_json: str = "{}"


def _default_json_loader(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _default_jsonl_loader(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _safe_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _load_optional_json(path: Path, json_loader: JsonLoader | None) -> Any:
    if not path.exists() or not path.is_file():
        return None
    loader = json_loader or _default_json_loader
    try:
        return loader(path)
    except Exception:
        return None


def _load_optional_jsonl(path: Path, jsonl_loader: JsonlLoader | None) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    loader = jsonl_loader or _default_jsonl_loader
    try:
        rows = loader(path)
    except Exception:
        return []
    return [row for row in rows if isinstance(row, dict)]


def _parse_duration_seconds(raw_duration: Any) -> float | None:
    if raw_duration is None:
        return None
    numeric = _safe_float(raw_duration)
    if numeric is not None:
        return numeric
    if not isinstance(raw_duration, str):
        return None
    matched = re.search(r"(-?\d+(?:\.\d+)?)", raw_duration)
    if matched is None:
        return None
    try:
        return float(matched.group(1))
    except ValueError:
        return None


def _normalize_status_distribution(payload: Any) -> dict[str, int]:
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, int] = {}
    for code, count in payload.items():
        count_value = _safe_int(count)
        if count_value is None:
            continue
        normalized[str(code)] = count_value
    return normalized


def _normalize_operation_status_codes(payload: Any) -> dict[str, dict[str, int]]:
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, dict[str, int]] = {}
    for operation_id, statuses in payload.items():
        if not isinstance(operation_id, str) or not isinstance(statuses, dict):
            continue
        normalized_statuses = _normalize_status_distribution(statuses)
        normalized[operation_id] = normalized_statuses
    return normalized


def _sum_status_distribution(operation_status_codes: dict[str, dict[str, int]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for statuses in operation_status_codes.values():
        for code, count in statuses.items():
            summary[code] = summary.get(code, 0) + count
    return dict(sorted(summary.items(), key=lambda item: (item[0])))


def _count_successful_operations(operation_status_codes: dict[str, dict[str, int]]) -> int:
    return sum(
        1
        for statuses in operation_status_codes.values()
        if any(
            isinstance(code, str)
            and code.isdigit()
            and 200 <= int(code) < 300
            and count > 0
            for code, count in statuses.items()
        )
    )


def _count_unique_server_errors(server_errors: Any) -> int | None:
    if not isinstance(server_errors, dict):
        return None
    total = 0
    for value in server_errors.values():
        if isinstance(value, list):
            total += len(value)
        elif value is not None:
            total += 1
    return total


def _load_llm_token_totals(
    llm_trace_path: Path,
    jsonl_loader: JsonlLoader | None,
) -> tuple[int, int]:
    input_tokens = 0
    output_tokens = 0
    for row in _load_optional_jsonl(llm_trace_path, jsonl_loader):
        llm_payload = row.get("llm")
        if not isinstance(llm_payload, dict):
            continue
        input_tokens += max(0, _safe_int(llm_payload.get("input_tokens")) or 0)
        output_tokens += max(0, _safe_int(llm_payload.get("output_tokens")) or 0)
    return input_tokens, output_tokens


def classify_report_schema(report_payload: dict[str, Any] | None) -> str:
    if not isinstance(report_payload, dict):
        return "missing_report"
    if any(
        key in report_payload
        for key in (
            "Run Status",
            "Snapshot Reason",
            "Input Tokens",
            "Output Tokens",
            "Total Tokens",
        )
    ):
        return "run_scoped_v2"
    return "legacy_report"


def _manifest_trace_paths(
    run_dir: Path,
    manifest_payload: dict[str, Any],
) -> dict[str, Path]:
    trace_dir = run_dir / "metadata" / "trace"
    manifest_paths = manifest_payload.get("paths", {})
    if not isinstance(manifest_paths, dict):
        manifest_paths = {}
    resolved: dict[str, Path] = {}
    for stream_key, filename in TRACE_STREAM_FILES.items():
        manifest_key = f"{stream_key}_trace"
        raw_path = manifest_paths.get(manifest_key)
        if isinstance(raw_path, str) and raw_path:
            resolved[stream_key] = Path(raw_path)
        else:
            resolved[stream_key] = trace_dir / filename
    return resolved


def build_run_metrics(
    run_dir: Path,
    manifest_payload: dict[str, Any],
    *,
    report_payload: dict[str, Any] | None = None,
    operation_status_codes: dict[str, dict[str, int]] | None = None,
    server_errors: dict[str, Any] | None = None,
    jsonl_loader: JsonlLoader | None = None,
) -> NormalizedReportMetrics:
    report_schema = classify_report_schema(report_payload)
    operation_status_codes = operation_status_codes or {}
    counters = (
        manifest_payload.get("counters", {})
        if isinstance(manifest_payload.get("counters"), dict)
        else {}
    )
    derived_fields: list[str] = []

    title = None
    if isinstance(report_payload, dict):
        raw_title = report_payload.get("Title")
        if isinstance(raw_title, str) and raw_title.strip():
            title = raw_title
    if title is None:
        raw_title = manifest_payload.get("report_title")
        if isinstance(raw_title, str) and raw_title.strip():
            title = raw_title
            derived_fields.append("title")

    duration_seconds = None
    if isinstance(report_payload, dict):
        duration_seconds = _parse_duration_seconds(report_payload.get("Duration"))
    if duration_seconds is None:
        started_at = _safe_datetime(manifest_payload.get("started_at"))
        completed_at = _safe_datetime(manifest_payload.get("completed_at"))
        if started_at is not None and completed_at is not None:
            duration_seconds = max(0.0, (completed_at - started_at).total_seconds())
            derived_fields.append("durationSeconds")

    run_status = "unknown"
    if isinstance(report_payload, dict):
        raw_run_status = report_payload.get("Run Status")
        if isinstance(raw_run_status, str) and raw_run_status.strip():
            run_status = raw_run_status
    if run_status == "unknown":
        raw_status = manifest_payload.get("status")
        if isinstance(raw_status, str) and raw_status.strip():
            run_status = raw_status
            derived_fields.append("runStatus")

    snapshot_reason = None
    if isinstance(report_payload, dict):
        raw_reason = report_payload.get("Snapshot Reason")
        if isinstance(raw_reason, str) and raw_reason.strip():
            snapshot_reason = raw_reason
    if snapshot_reason is None:
        raw_reason = counters.get("last_snapshot_reason")
        if isinstance(raw_reason, str) and raw_reason.strip():
            snapshot_reason = raw_reason
            derived_fields.append("snapshotReason")

    status_code_distribution = {}
    if isinstance(report_payload, dict):
        status_code_distribution = _normalize_status_distribution(
            report_payload.get("Status Code Distribution")
        )
    if not status_code_distribution and operation_status_codes:
        status_code_distribution = _sum_status_distribution(operation_status_codes)
        derived_fields.append("statusCodeDistribution")

    total_requests_sent = 0
    if isinstance(report_payload, dict):
        total_requests_sent = max(0, _safe_int(report_payload.get("Total Requests Sent")) or 0)
    if total_requests_sent == 0 and status_code_distribution:
        total_requests_sent = sum(status_code_distribution.values())
        derived_fields.append("totalRequestsSent")
    if total_requests_sent == 0:
        total_requests_sent = max(0, _safe_int(counters.get("attempt_sequence")) or 0)
        if total_requests_sent:
            derived_fields.append("totalRequestsSent")

    total_operations = None
    if isinstance(report_payload, dict):
        total_operations = _safe_int(report_payload.get("Number of Total Operations"))
    if total_operations is None and operation_status_codes:
        total_operations = len(operation_status_codes)
        derived_fields.append("totalOperations")

    successful_operations = None
    if isinstance(report_payload, dict):
        successful_operations = _safe_int(
            report_payload.get("Number of Successfully Processed Operations")
        )
    if successful_operations is None and operation_status_codes:
        successful_operations = _count_successful_operations(operation_status_codes)
        derived_fields.append("successfulOperations")

    successful_percentage = None
    if isinstance(report_payload, dict):
        raw_percentage = report_payload.get(
            "Percentage of Successfully Processed Operations"
        )
        if isinstance(raw_percentage, str):
            successful_percentage = _parse_duration_seconds(raw_percentage.rstrip("%"))
        elif raw_percentage is not None:
            successful_percentage = _safe_float(raw_percentage)
    if successful_percentage is None and total_operations and successful_operations is not None:
        successful_percentage = round(
            successful_operations / max(total_operations, 1) * 100,
            2,
        )
        derived_fields.append("successfulPercentage")

    unique_server_errors = None
    if isinstance(report_payload, dict):
        unique_server_errors = _safe_int(report_payload.get("Number of Unique Server Errors"))
    if unique_server_errors is None:
        unique_server_errors = _count_unique_server_errors(server_errors)
        if unique_server_errors is not None:
            derived_fields.append("uniqueServerErrors")

    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    if isinstance(report_payload, dict):
        input_tokens = max(0, _safe_int(report_payload.get("Input Tokens")) or 0)
        output_tokens = max(0, _safe_int(report_payload.get("Output Tokens")) or 0)
        total_tokens = max(0, _safe_int(report_payload.get("Total Tokens")) or 0)
    if (input_tokens == 0 and output_tokens == 0 and total_tokens == 0):
        llm_trace_path = _manifest_trace_paths(run_dir, manifest_payload)["llm_calls"]
        derived_input_tokens, derived_output_tokens = _load_llm_token_totals(
            llm_trace_path,
            jsonl_loader,
        )
        if derived_input_tokens or derived_output_tokens:
            input_tokens = derived_input_tokens
            output_tokens = derived_output_tokens
            total_tokens = derived_input_tokens + derived_output_tokens
            derived_fields.extend(["inputTokens", "outputTokens", "totalTokens"])
    elif total_tokens == 0:
        total_tokens = input_tokens + output_tokens
        derived_fields.append("totalTokens")

    trace_event_count = _safe_int(counters.get("event_sequence"))
    logical_count = _safe_int(counters.get("logical_sequence"))
    http_attempt_count = _safe_int(counters.get("attempt_sequence"))
    llm_call_count = _safe_int(counters.get("llm_call_sequence"))
    checkpoint_count = _safe_int(counters.get("checkpoint_count"))

    return NormalizedReportMetrics(
        title=title,
        duration_seconds=duration_seconds,
        run_status=run_status,
        snapshot_reason=snapshot_reason,
        total_requests_sent=total_requests_sent,
        status_code_distribution=status_code_distribution,
        total_operations=total_operations,
        successful_operations=successful_operations,
        successful_percentage=successful_percentage,
        unique_server_errors=unique_server_errors,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens if total_tokens else input_tokens + output_tokens,
        trace_event_count=trace_event_count,
        logical_count=logical_count,
        http_attempt_count=http_attempt_count,
        llm_call_count=llm_call_count,
        checkpoint_count=checkpoint_count,
        report_schema=report_schema,
        derived_fields=tuple(dict.fromkeys(derived_fields)),
    )


def has_valid_run_manifests(dataset_dir: Path) -> bool:
    return any((run_dir / "metadata" / "runtime" / "manifest.json").exists() for run_dir in iter_run_dirs(dataset_dir))


def iter_valid_dataset_dirs(data_root: Path) -> list[Path]:
    if not data_root.exists():
        return []
    return [
        dataset_dir
        for dataset_dir in sorted(path for path in data_root.iterdir() if path.is_dir())
        if has_valid_run_manifests(dataset_dir)
    ]


def iter_run_dirs(dataset_dir: Path) -> list[Path]:
    if not dataset_dir.exists():
        return []
    return [
        run_dir
        for run_dir in sorted(path for path in dataset_dir.iterdir() if path.is_dir())
        if (run_dir / "metadata" / "runtime" / "manifest.json").exists()
    ]


def build_run_inventory(
    run_dir: Path,
    *,
    dataset: str | None = None,
    json_loader: JsonLoader | None = None,
    jsonl_loader: JsonlLoader | None = None,
) -> RunInventory | None:
    manifest_path = run_dir / "metadata" / "runtime" / "manifest.json"
    manifest_payload = _load_optional_json(manifest_path, json_loader)
    if not isinstance(manifest_payload, dict):
        return None

    dataset_name = dataset or run_dir.parent.name
    run_id = str(manifest_payload.get("run_id", run_dir.name))
    report_path = run_dir / "report.json"
    operation_status_codes_path = run_dir / "operation_status_codes.json"
    qtables_path = run_dir / "q_tables.json"
    server_errors_path = run_dir / "server_errors.json"
    trace_paths = _manifest_trace_paths(run_dir, manifest_payload)
    trace_availability = {
        key: path.exists() and path.is_file() for key, path in trace_paths.items()
    }

    report_payload = _load_optional_json(report_path, json_loader)
    if not isinstance(report_payload, dict):
        report_payload = None

    operation_status_codes = _normalize_operation_status_codes(
        _load_optional_json(operation_status_codes_path, json_loader)
    )
    if not operation_status_codes:
        operation_status_codes = None

    server_errors_payload = _load_optional_json(server_errors_path, json_loader)
    if not isinstance(server_errors_payload, dict):
        server_errors_payload = None

    metrics = build_run_metrics(
        run_dir,
        manifest_payload,
        report_payload=report_payload,
        operation_status_codes=operation_status_codes,
        server_errors=server_errors_payload,
        jsonl_loader=jsonl_loader,
    )

    return RunInventory(
        dataset=dataset_name,
        run=run_id,
        run_dir=run_dir,
        manifest_path=manifest_path,
        manifest=manifest_payload,
        report=report_payload,
        operation_status_codes=operation_status_codes,
        server_errors=server_errors_payload,
        metrics=metrics,
        started_at=_safe_datetime(manifest_payload.get("started_at")),
        updated_at=_safe_datetime(manifest_payload.get("updated_at")),
        completed_at=_safe_datetime(manifest_payload.get("completed_at")),
        has_report=report_path.exists(),
        has_operation_status_codes=operation_status_codes_path.exists(),
        has_qtables=qtables_path.exists(),
        has_trace=any(trace_availability.values()),
        trace_availability=trace_availability,
        counters=(
            manifest_payload.get("counters", {})
            if isinstance(manifest_payload.get("counters"), dict)
            else {}
        ),
        status_code_distribution_json=json.dumps(
            metrics.status_code_distribution,
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
