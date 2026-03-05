from __future__ import annotations

import json

from autoresttest.inspector_api.config import InspectorSettings, build_context
from autoresttest.inspector_api.services.run_service import list_runs
from autoresttest.inspector_api.services.trace_service import (
    get_operation_metrics,
    get_timeline,
    get_trace_chains,
)


def test_timeline_loads_for_latest_bills_api_run(tmp_path) -> None:
    dataset_id = "demo"
    run_id = "demo-20260305T000000Z-1000"
    run_dir = tmp_path / "data" / dataset_id / run_id
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
    (trace_dir / "logical_requests.jsonl").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "trace_kind": "logical_request",
                "event_sequence_id": 4,
                "run_id": run_id,
                "logical_request_id": 4,
                "phase": "value_agent_q_table_generation",
                "component": "value_agent",
                "operation_id": "get_api_v1_billtypes",
                "event_type": "value_agent_params_informed",
                "started_at": "2026-03-05T00:00:01+00:00",
                "completed_at": "2026-03-05T00:00:02+00:00",
                "duration_ms": 1000,
                "request_failed": False,
                "attempt_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (trace_dir / "http_attempts.jsonl").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "trace_kind": "http_attempt",
                "event_sequence_id": 2,
                "run_id": run_id,
                "logical_request_id": 4,
                "phase": "value_agent_q_table_generation",
                "component": "value_agent",
                "logical_operation_id": "get_api_v1_billtypes",
                "http_method": "GET",
                "recorded_at": "2026-03-05T00:00:01.500000+00:00",
                "duration_ms": 50,
                "attempt_index": 1,
                "response": {"status_code": 200},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (trace_dir / "llm_calls.jsonl").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "trace_kind": "llm_call",
                "event_sequence_id": 1,
                "run_id": run_id,
                "logical_request_id": 4,
                "phase": "value_agent_q_table_generation",
                "component": "value_agent",
                "logical_operation_id": "get_api_v1_billtypes",
                "recorded_at": "2026-03-05T00:00:01.100000+00:00",
                "duration_ms": 30,
                "metadata": {"llm_purpose": "value_agent_params_informed"},
                "llm": {
                    "cache_hit": False,
                    "input_tokens": 20,
                    "output_tokens": 10,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    context = build_context(
        InspectorSettings(
            data_root=tmp_path / "data",
            cache_root=tmp_path / "cache",
            static_root=tmp_path / "dist",
        )
    )
    latest_run = list_runs(context, dataset_id)[0]
    timeline = get_timeline(context, dataset_id, latest_run.run_id, limit=50)
    assert timeline.events
    assert timeline.cursor >= timeline.events[-1].event_sequence_id
    assert timeline.timeline_order in {"native", "synthesized"}

    preview_timeline = get_timeline(
        context,
        dataset_id,
        latest_run.run_id,
        logical_request_id=4,
        include_payload=False,
        limit=5,
    )
    assert preview_timeline.events
    assert preview_timeline.events[0].payload["previewOnly"] is True

    chains = get_trace_chains(context, dataset_id, latest_run.run_id, limit=5)
    assert chains.chains
    assert chains.chains[0].items

    metrics = get_operation_metrics(context, dataset_id, latest_run.run_id)
    assert metrics.operations
    assert metrics.totals["operationCount"] >= 1
