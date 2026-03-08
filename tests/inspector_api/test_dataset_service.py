from __future__ import annotations

import json

from autoresttest.inspector_api.config import InspectorSettings, build_context
from autoresttest.inspector_api.services.dataset_service import list_dataset_summaries
from autoresttest.run_artifacts import PROJECT_ROOT


def test_list_datasets_includes_bills_api() -> None:
    context = build_context(
        InspectorSettings(
            data_root=PROJECT_ROOT / "data",
            cache_root=PROJECT_ROOT / "cache",
            static_root=PROJECT_ROOT / "apps" / "autoresttest-inspector" / "web" / "dist",
        )
    )
    dataset_ids = [dataset.dataset_id for dataset in list_dataset_summaries(context)]
    assert "Bills-api" in dataset_ids


def test_list_datasets_skips_directories_without_valid_run_manifests(tmp_path) -> None:
    data_root = tmp_path / "data"
    valid_run_dir = data_root / "demo" / "demo-20260305T000000Z-1000"
    runtime_dir = valid_run_dir / "metadata" / "runtime"
    trace_dir = valid_run_dir / "metadata" / "trace"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "demo-20260305T000000Z-1000",
                "dataset_name": "demo",
                "status": "completed",
                "started_at": "2026-03-05T00:00:00+00:00",
                "updated_at": "2026-03-05T00:00:10+00:00",
                "completed_at": "2026-03-05T00:00:11+00:00",
                "paths": {
                    "run_dir": str(valid_run_dir),
                    "logical_requests_trace": str(trace_dir / "logical_requests.jsonl"),
                    "http_attempts_trace": str(trace_dir / "http_attempts.jsonl"),
                    "llm_calls_trace": str(trace_dir / "llm_calls.jsonl"),
                },
                "counters": {},
            }
        ),
        encoding="utf-8",
    )
    (trace_dir / "logical_requests.jsonl").write_text("", encoding="utf-8")
    (trace_dir / "http_attempts.jsonl").write_text("", encoding="utf-8")
    (trace_dir / "llm_calls.jsonl").write_text("", encoding="utf-8")
    (data_root / "batch-runs-smoke" / "plan-20260307T180324Z-51904" / "jobs").mkdir(
        parents=True,
        exist_ok=True,
    )

    context = build_context(
        InspectorSettings(
            data_root=data_root,
            cache_root=tmp_path / "cache",
            static_root=tmp_path / "dist",
        )
    )

    summaries = list_dataset_summaries(context)

    assert [dataset.dataset_id for dataset in summaries] == ["demo"]
