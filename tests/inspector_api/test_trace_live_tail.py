from __future__ import annotations

import json

from autoresttest.inspector_api.config import InspectorSettings, build_context
from autoresttest.inspector_api.services.trace_service import get_timeline


def test_timeline_supports_incremental_tail(tmp_path) -> None:
    dataset_dir = tmp_path / "data" / "demo"
    run_id = "demo-run"
    run_dir = dataset_dir / run_id
    runtime_dir = run_dir / "metadata" / "runtime"
    trace_dir = run_dir / "metadata" / "trace"
    runtime_dir.mkdir(parents=True)
    trace_dir.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "status": "running",
        "started_at": "2026-03-04T15:00:00+00:00",
        "updated_at": "2026-03-04T15:00:00+00:00",
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
    (trace_dir / "llm_calls.jsonl").write_text("", encoding="utf-8")
    (trace_dir / "http_attempts.jsonl").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "trace_kind": "http_attempt",
                "event_sequence_id": 1,
                "run_id": run_id,
                "recorded_at": "2026-03-04T15:00:01+00:00",
                "duration_ms": 10,
                "response": {"status_code": 200},
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
    initial = get_timeline(context, "demo", run_id)
    assert len(initial.events) == 1

    with (trace_dir / "http_attempts.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "schema_version": 1,
                    "trace_kind": "http_attempt",
                    "event_sequence_id": 2,
                    "run_id": run_id,
                    "recorded_at": "2026-03-04T15:00:02+00:00",
                    "duration_ms": 12,
                    "response": {"status_code": 404},
                }
            )
            + "\n"
        )

    delta = get_timeline(context, "demo", run_id, after_event_sequence_id=1)
    assert [event.event_sequence_id for event in delta.events] == [2]
