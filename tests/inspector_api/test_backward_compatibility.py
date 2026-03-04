from __future__ import annotations

import json

from autoresttest.inspector_api.config import InspectorSettings, build_context
from autoresttest.inspector_api.services.trace_service import get_timeline


def test_backward_compatibility_synthesizes_event_order(tmp_path) -> None:
    dataset_dir = tmp_path / "data" / "legacy"
    runtime_dir = dataset_dir / "runtime"
    trace_dir = dataset_dir / "trace"
    runtime_dir.mkdir(parents=True)
    trace_dir.mkdir(parents=True)

    run_id = "legacy-run"
    manifest = {
        "run_id": run_id,
        "status": "completed",
        "started_at": "2026-03-04T15:00:00+00:00",
        "updated_at": "2026-03-04T15:00:02+00:00",
        "paths": {},
        "counters": {},
    }
    (runtime_dir / f"{run_id}.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (trace_dir / f"{run_id}.logical_requests.jsonl").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "completed_at": "2026-03-04T15:00:03+00:00",
                "operation_id": "legacyOp",
                "trace_kind": "logical_request",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (trace_dir / f"{run_id}.http_attempts.jsonl").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "recorded_at": "2026-03-04T15:00:02+00:00",
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
    timeline = get_timeline(context, "legacy", run_id)
    assert timeline.timeline_order == "synthesized"
    assert [event.event_sequence_id for event in timeline.events] == [1, 2]
