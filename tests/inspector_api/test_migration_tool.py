from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "tools"
        / "migrate_data_layout_to_run_scoped.py"
    )
    spec = importlib.util.spec_from_file_location(
        "migrate_data_layout_to_run_scoped",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load migration tool module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_tool_moves_to_run_scoped_layout(tmp_path) -> None:
    module = _load_migration_module()
    migrate_data_layout = module.migrate_data_layout

    data_root = tmp_path / "data"
    dataset_dir = data_root / "demo"
    runtime_dir = dataset_dir / "runtime"
    trace_dir = dataset_dir / "trace"
    runtime_dir.mkdir(parents=True)
    trace_dir.mkdir(parents=True)

    run_id = "demo-20260305T000000Z-1234"
    (trace_dir / f"{run_id}.logical_requests.jsonl").write_text("{}", encoding="utf-8")
    (trace_dir / f"{run_id}.http_attempts.jsonl").write_text("{}", encoding="utf-8")
    (trace_dir / f"{run_id}.llm_calls.jsonl").write_text("{}", encoding="utf-8")
    (dataset_dir / "report.json").write_text('{"ok":true}', encoding="utf-8")
    (dataset_dir / "q_tables.json").write_text('{"OPERATION AGENT":{}}', encoding="utf-8")

    old_manifest = {
        "run_id": run_id,
        "status": "completed",
        "started_at": "2026-03-05T00:00:00+00:00",
        "updated_at": "2026-03-05T00:00:05+00:00",
        "paths": {
            "logical_requests_trace": str(trace_dir / f"{run_id}.logical_requests.jsonl"),
            "http_attempts_trace": str(trace_dir / f"{run_id}.http_attempts.jsonl"),
            "llm_calls_trace": str(trace_dir / f"{run_id}.llm_calls.jsonl"),
        },
        "counters": {},
    }
    (runtime_dir / f"{run_id}.manifest.json").write_text(
        json.dumps(old_manifest),
        encoding="utf-8",
    )

    report = migrate_data_layout(
        data_root,
        dry_run=False,
        prune_legacy=True,
    )
    assert report["datasets"][0]["rewrittenManifests"] == 1

    run_dir = dataset_dir / run_id
    new_manifest_path = run_dir / "metadata" / "runtime" / "manifest.json"
    assert new_manifest_path.exists()
    manifest_payload = json.loads(new_manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["paths"]["run_dir"] == str(run_dir)
    assert (
        manifest_payload["paths"]["logical_requests_trace"]
        == str(run_dir / "metadata" / "trace" / "logical_requests.jsonl")
    )

    assert (run_dir / "metadata" / "trace" / "logical_requests.jsonl").exists()
    assert (run_dir / "metadata" / "trace" / "http_attempts.jsonl").exists()
    assert (run_dir / "metadata" / "trace" / "llm_calls.jsonl").exists()
    assert (run_dir / "report.json").exists()
    assert (run_dir / "q_tables.json").exists()

    assert not (dataset_dir / "runtime").exists()
    assert not (dataset_dir / "trace").exists()
    assert not (dataset_dir / "report.json").exists()
    assert not (dataset_dir / "q_tables.json").exists()


def test_migration_tool_dry_run_does_not_modify_filesystem(tmp_path) -> None:
    module = _load_migration_module()
    migrate_data_layout = module.migrate_data_layout

    data_root = tmp_path / "data"
    dataset_dir = data_root / "demo"
    runtime_dir = dataset_dir / "runtime"
    trace_dir = dataset_dir / "trace"
    runtime_dir.mkdir(parents=True)
    trace_dir.mkdir(parents=True)

    run_id = "demo-20260305T010000Z-1234"
    (trace_dir / f"{run_id}.logical_requests.jsonl").write_text("{}", encoding="utf-8")
    (runtime_dir / f"{run_id}.manifest.json").write_text(
        json.dumps({"run_id": run_id}),
        encoding="utf-8",
    )
    (dataset_dir / "report.json").write_text('{"ok":true}', encoding="utf-8")

    report = migrate_data_layout(
        data_root,
        dry_run=True,
        prune_legacy=True,
    )
    assert report["dryRun"] is True
    assert report["datasets"][0]["rewrittenManifests"] == 1

    assert (runtime_dir / f"{run_id}.manifest.json").exists()
    assert (trace_dir / f"{run_id}.logical_requests.jsonl").exists()
    assert (dataset_dir / "report.json").exists()
    assert not (dataset_dir / run_id / "metadata" / "runtime" / "manifest.json").exists()
