from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from autoresttest.models import to_dict_helper


AUTORESTTEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AUTORESTTEST_DIR.parent.parent
DATA_ROOT = PROJECT_ROOT / "data"


def ensure_output_dir(spec_name: str) -> Path:
    output_dir = DATA_ROOT / spec_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def ensure_runtime_dir(spec_name: str) -> Path:
    runtime_dir = ensure_output_dir(spec_name) / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir


def ensure_trace_dir(spec_name: str) -> Path:
    trace_dir = ensure_output_dir(spec_name) / "trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir


def build_report_title(spec_name: str, api_title: str | None = None) -> str:
    title = api_title if api_title else spec_name
    return f"'{title}' ({spec_name})"


def _is_json_serializable(data: Any) -> bool:
    try:
        json.dumps(data)
        return True
    except (TypeError, ValueError):
        return False


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=f"{path.name}.",
        suffix=".tmp",
    ) as tmp_file:
        json.dump(payload, tmp_file, indent=2)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        tmp_path = Path(tmp_file.name)

    os.replace(tmp_path, path)


def build_q_table_payload(q_learning: Any) -> dict[str, Any]:
    parameter_table = q_learning.parameter_agent.q_table
    body_obj_table = q_learning.body_object_agent.q_table
    value_table = q_learning.value_agent.q_table
    operation_table = q_learning.operation_agent.q_table
    data_source_table = q_learning.data_source_agent.q_table
    dependency_table = q_learning.dependency_agent.q_table
    header_table = (
        q_learning.header_agent.q_table
        if q_learning.header_agent.q_table
        else "Disabled"
    )

    simplified_param_table: dict[str, dict[str, dict[str, Any]]] = {}
    for operation, operation_values in parameter_table.items():
        simplified_param_table[operation] = {"params": {}, "body": {}}
        for parameter, parameter_values in operation_values["params"].items():
            simplified_param_table[operation]["params"][str(parameter)] = parameter_values
        for body, body_values in operation_values["body"].items():
            simplified_param_table[operation]["body"][str(body)] = body_values

    simplified_body_table: dict[str, dict[str, dict[str, Any]]] = {}
    for operation, operation_values in body_obj_table.items():
        simplified_body_table[operation] = {}
        for mime_type, mime_values in operation_values.items():
            if mime_type not in simplified_body_table[operation]:
                simplified_body_table[operation][mime_type] = {}
            for body, body_values in mime_values.items():
                simplified_body_table[operation][mime_type][str(body)] = body_values

    compiled_q_table = {
        "OPERATION AGENT": operation_table,
        "HEADER AGENT": header_table,
        "PARAMETER AGENT": simplified_param_table,
        "VALUE AGENT": value_table,
        "BODY OBJECT AGENT": simplified_body_table,
        "DATA SOURCE AGENT": data_source_table,
        "DEPENDENCY AGENT": dependency_table,
    }
    return to_dict_helper(compiled_q_table)


def build_success_payloads(q_learning: Any) -> dict[str, Any]:
    return {
        "successful_parameters.json": to_dict_helper(q_learning.successful_parameters),
        "successful_bodies.json": q_learning.successful_bodies,
        "successful_responses.json": q_learning.successful_responses,
        "successful_primitives.json": q_learning.successful_primitives,
    }


def build_error_payload(q_learning: Any) -> dict[str, list[dict[str, Any]]]:
    serializable_errors: dict[str, list[dict[str, Any]]] = {}
    for operation_idx, unique_errors in q_learning.unique_errors.items():
        serializable_errors[operation_idx] = [
            error for error in unique_errors if _is_json_serializable(error)
        ]
    return serializable_errors


def build_operation_status_codes_payload(q_learning: Any) -> dict[str, dict[int, int]]:
    return q_learning.operation_response_counter


def build_report_payload(q_learning: Any, report_title: str) -> dict[str, Any]:
    unique_processed_200s = set()
    for operation_idx, status_codes in q_learning.operation_response_counter.items():
        for status_code in status_codes:
            if status_code // 100 == 2:
                unique_processed_200s.add(operation_idx)

    unique_errors = sum(len(errs) for errs in q_learning.unique_errors.values())
    total_requests = sum(q_learning.responses.values())
    total_operations = len(q_learning.operation_agent.q_table)
    success_percentage = round(
        len(unique_processed_200s) / max(total_operations, 1) * 100,
        2,
    )

    return {
        "Title": "AutoRestTest Report for " + report_title,
        "Duration": f"{q_learning.time_duration} seconds",
        "Total Requests Sent": total_requests,
        "Status Code Distribution": dict(q_learning.responses),
        "Number of Total Operations": total_operations,
        "Number of Successfully Processed Operations": len(unique_processed_200s),
        "Percentage of Successfully Processed Operations": f"{success_percentage}%",
        "Number of Unique Server Errors": unique_errors,
        "Operations with Server Errors": q_learning.errors,
    }


def build_standard_output_payloads(
    q_learning: Any, report_title: str
) -> dict[str, Any]:
    payloads = {
        "q_tables.json": build_q_table_payload(q_learning),
        "server_errors.json": build_error_payload(q_learning),
        "operation_status_codes.json": build_operation_status_codes_payload(q_learning),
        "report.json": build_report_payload(q_learning, report_title),
    }
    payloads.update(build_success_payloads(q_learning))
    return payloads


def write_standard_output_snapshot(
    spec_name: str, q_learning: Any, report_title: str
) -> dict[str, Path]:
    output_dir = ensure_output_dir(spec_name)
    written_paths: dict[str, Path] = {}

    for filename, payload in build_standard_output_payloads(q_learning, report_title).items():
        path = output_dir / filename
        atomic_write_json(path, payload)
        written_paths[filename] = path

    return written_paths
