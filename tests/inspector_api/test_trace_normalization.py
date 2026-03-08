from __future__ import annotations

import json

from autoresttest.inspector_api.config import InspectorSettings, build_context
from autoresttest.inspector_api.services.run_service import list_runs
from autoresttest.inspector_api.services.trace_service import (
    get_operation_metrics,
    get_trace_facets,
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


def test_trace_filters_and_facets_include_status_and_token_breakdowns(tmp_path) -> None:
    dataset_id = "demo"
    run_id = "demo-20260305T000200Z-1000"
    run_dir = tmp_path / "data" / dataset_id / run_id
    runtime_dir = run_dir / "metadata" / "runtime"
    trace_dir = run_dir / "metadata" / "trace"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "dataset_name": dataset_id,
        "status": "running",
        "started_at": "2026-03-05T00:00:00+00:00",
        "updated_at": "2026-03-05T00:00:10+00:00",
        "completed_at": "2026-03-05T00:00:11+00:00",
        "paths": {
            "run_dir": str(run_dir),
            "logical_requests_trace": str(trace_dir / "logical_requests.jsonl"),
            "http_attempts_trace": str(trace_dir / "http_attempts.jsonl"),
            "llm_calls_trace": str(trace_dir / "llm_calls.jsonl"),
        },
        "counters": {
            "event_sequence": 6,
            "logical_sequence": 2,
            "attempt_sequence": 2,
            "llm_call_sequence": 2,
        },
    }
    (runtime_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (trace_dir / "logical_requests.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "trace_kind": "logical_request",
                        "event_sequence_id": 1,
                        "run_id": run_id,
                        "logical_request_id": 10,
                        "phase": "exploration",
                        "component": "value_agent",
                        "operation_id": "opA",
                        "event_type": "dispatched",
                        "started_at": "2026-03-05T00:00:01+00:00",
                        "completed_at": "2026-03-05T00:00:02+00:00",
                        "duration_ms": 1000,
                        "request_failed": False,
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "trace_kind": "logical_request",
                        "event_sequence_id": 4,
                        "run_id": run_id,
                        "logical_request_id": 11,
                        "phase": "exploration",
                        "component": "value_agent",
                        "operation_id": "opA",
                        "event_type": "dispatched",
                        "started_at": "2026-03-05T00:00:03+00:00",
                        "completed_at": "2026-03-05T00:00:04+00:00",
                        "duration_ms": 900,
                        "request_failed": True,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (trace_dir / "http_attempts.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "trace_kind": "http_attempt",
                        "event_sequence_id": 2,
                        "run_id": run_id,
                        "logical_request_id": 10,
                        "phase": "exploration",
                        "component": "value_agent",
                        "logical_operation_id": "opA",
                        "http_method": "GET",
                        "recorded_at": "2026-03-05T00:00:01.300000+00:00",
                        "duration_ms": 55,
                        "attempt_index": 1,
                        "response": {"status_code": 200},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "trace_kind": "http_attempt",
                        "event_sequence_id": 5,
                        "run_id": run_id,
                        "logical_request_id": 11,
                        "phase": "exploration",
                        "component": "value_agent",
                        "logical_operation_id": "opA",
                        "http_method": "GET",
                        "recorded_at": "2026-03-05T00:00:03.300000+00:00",
                        "duration_ms": 88,
                        "attempt_index": 2,
                        "transport_error": {"type": "timeout"},
                        "response": {"status_code": 503},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (trace_dir / "llm_calls.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "trace_kind": "llm_call",
                        "event_sequence_id": 3,
                        "run_id": run_id,
                        "logical_request_id": 10,
                        "phase": "exploration",
                        "component": "value_agent",
                        "logical_operation_id": "opA",
                        "recorded_at": "2026-03-05T00:00:01.100000+00:00",
                        "duration_ms": 30,
                        "metadata": {"purpose": "seed_generation"},
                        "llm": {
                            "cache_hit": False,
                            "input_tokens": 20,
                            "output_tokens": 10,
                        },
                    }
                ),
                json.dumps(
                    {
                        "schema_version": 1,
                        "trace_kind": "llm_call",
                        "event_sequence_id": 6,
                        "run_id": run_id,
                        "logical_request_id": 11,
                        "phase": "exploration",
                        "component": "value_agent",
                        "logical_operation_id": "opA",
                        "recorded_at": "2026-03-05T00:00:03.100000+00:00",
                        "duration_ms": 40,
                        "metadata": {"llm_purpose": "repair_generation"},
                        "llm": {
                            "cache_hit": True,
                            "input_tokens": 5,
                            "output_tokens": 4,
                        },
                    }
                ),
            ]
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

    status_filtered = get_timeline(
        context,
        dataset_id,
        run_id,
        status_family="5xx",
        include_payload=False,
        limit=10,
    )
    assert [event.status_code for event in status_filtered.events] == [503]

    llm_filtered = get_timeline(
        context,
        dataset_id,
        run_id,
        trace_kind="llm_call",
        llm_purpose="seed_generation",
        cache_hit=False,
        min_duration_ms=20,
        max_duration_ms=35,
        limit=10,
    )
    assert len(llm_filtered.events) == 1
    assert llm_filtered.events[0].llm_purpose == "seed_generation"

    facets = get_trace_facets(context, dataset_id, run_id)
    assert {"value": "200", "count": 1} in facets.status_codes
    assert {"value": "503", "count": 1} in facets.status_codes
    assert {"value": "2xx", "count": 1} in facets.status_families
    assert {"value": "5xx", "count": 1} in facets.status_families
    assert facets.cache_hit_counts == {"true": 1, "false": 1}
    assert facets.request_failed_counts == {"true": 1, "false": 1}
    assert facets.transport_error_counts == {"true": 1, "false": 1}

    metrics = get_operation_metrics(context, dataset_id, run_id)
    assert metrics.totals["inputTokenTotal"] == 25
    assert metrics.totals["outputTokenTotal"] == 14
    assert metrics.totals["tokenTotal"] == 39
    assert metrics.operations[0].input_token_total == 25
    assert metrics.operations[0].output_token_total == 14
    assert metrics.operations[0].total_token_count == 39
    assert metrics.operations[0].status_code_breakdown == {"200": 1, "503": 1}
