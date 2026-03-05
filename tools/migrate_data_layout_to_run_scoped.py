from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


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


def _safe_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_old_manifest(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name == "latest_run_manifest.json":
        return False
    if path.suffix != ".json":
        return False
    if path.name.endswith(".tmp"):
        return False
    return path.name.endswith(".manifest.json")


def _copy_file(src: Path, dst: Path, dry_run: bool) -> None:
    if not src.exists():
        return
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _write_json(path: Path, payload: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _delete_path(path: Path, dry_run: bool) -> None:
    if not path.exists():
        return
    if dry_run:
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _rewrite_manifest_paths(
    payload: dict[str, Any],
    dataset_dir: Path,
    run_dir: Path,
) -> dict[str, Any]:
    metadata_dir = run_dir / "metadata"
    trace_dir = metadata_dir / "trace"
    runtime_dir = metadata_dir / "runtime"
    payload = dict(payload)
    existing_paths = payload.get("paths", {})
    if not isinstance(existing_paths, dict):
        existing_paths = {}

    payload["paths"] = {
        **existing_paths,
        "dataset_dir": str(dataset_dir),
        "run_dir": str(run_dir),
        "metadata_dir": str(metadata_dir),
        "trace_dir": str(trace_dir),
        "runtime_dir": str(runtime_dir),
        "logical_requests_trace": str(trace_dir / TRACE_STREAM_FILES["logical_requests"]),
        "http_attempts_trace": str(trace_dir / TRACE_STREAM_FILES["http_attempts"]),
        "llm_calls_trace": str(trace_dir / TRACE_STREAM_FILES["llm_calls"]),
        "latest_snapshot_report": str(run_dir / "report.json"),
    }
    return payload


def migrate_dataset(
    dataset_dir: Path,
    *,
    dry_run: bool,
    prune_legacy: bool,
) -> dict[str, Any]:
    runtime_dir = dataset_dir / "runtime"
    trace_dir = dataset_dir / "trace"
    manifest_paths = []
    if runtime_dir.exists():
        manifest_paths = sorted(path for path in runtime_dir.iterdir() if _is_old_manifest(path))

    migrated_runs: list[str] = []
    rewritten_manifests = 0
    copied_trace_files = 0
    copied_artifact_files = 0

    if not manifest_paths:
        return {
            "dataset": dataset_dir.name,
            "migratedRuns": migrated_runs,
            "rewrittenManifests": rewritten_manifests,
            "copiedTraceFiles": copied_trace_files,
            "copiedArtifactFiles": copied_artifact_files,
            "skipped": True,
        }

    latest_manifest_payload: dict[str, Any] | None = None
    latest_run_id: str | None = None
    latest_sort_key: datetime | None = None

    for old_manifest in manifest_paths:
        payload_raw = json.loads(old_manifest.read_text(encoding="utf-8"))
        if not isinstance(payload_raw, dict):
            continue
        run_id = str(payload_raw.get("run_id", "")).strip()
        if not run_id:
            run_id = old_manifest.name.replace(".manifest.json", "")

        run_dir = dataset_dir / run_id
        new_trace_dir = run_dir / "metadata" / "trace"
        new_runtime_dir = run_dir / "metadata" / "runtime"
        new_manifest_path = new_runtime_dir / "manifest.json"

        # Copy trace files from old naming convention.
        for stream_key, new_name in TRACE_STREAM_FILES.items():
            old_name = f"{run_id}.{stream_key}.jsonl"
            old_trace = trace_dir / old_name
            new_trace = new_trace_dir / new_name
            if old_trace.exists():
                _copy_file(old_trace, new_trace, dry_run)
                copied_trace_files += 1

        rewritten_payload = _rewrite_manifest_paths(payload_raw, dataset_dir, run_dir)
        _write_json(new_manifest_path, rewritten_payload, dry_run)
        rewritten_manifests += 1
        migrated_runs.append(run_id)

        sort_key = (
            _safe_dt(rewritten_payload.get("started_at"))
            or _safe_dt(rewritten_payload.get("updated_at"))
            or _safe_dt(rewritten_payload.get("completed_at"))
        )
        if latest_sort_key is None or (sort_key is not None and sort_key > latest_sort_key):
            latest_sort_key = sort_key
            latest_run_id = run_id
            latest_manifest_payload = rewritten_payload

    # Copy dataset-level artifacts into latest run only.
    if latest_run_id is not None:
        latest_run_dir = dataset_dir / latest_run_id
        for artifact_name in ARTIFACT_FILES:
            source = dataset_dir / artifact_name
            target = latest_run_dir / artifact_name
            if source.exists():
                _copy_file(source, target, dry_run)
                copied_artifact_files += 1

        if latest_manifest_payload is not None:
            latest_manifest_path = latest_run_dir / "metadata" / "runtime" / "manifest.json"
            latest_manifest_payload = _rewrite_manifest_paths(
                latest_manifest_payload,
                dataset_dir,
                latest_run_dir,
            )
            _write_json(latest_manifest_path, latest_manifest_payload, dry_run)

    if prune_legacy:
        _delete_path(runtime_dir, dry_run)
        _delete_path(trace_dir, dry_run)
        _delete_path(dataset_dir / "latest_run_manifest.json", dry_run)
        for artifact_name in ARTIFACT_FILES:
            _delete_path(dataset_dir / artifact_name, dry_run)

    return {
        "dataset": dataset_dir.name,
        "migratedRuns": migrated_runs,
        "rewrittenManifests": rewritten_manifests,
        "copiedTraceFiles": copied_trace_files,
        "copiedArtifactFiles": copied_artifact_files,
        "skipped": False,
    }


def migrate_data_layout(
    data_root: Path,
    *,
    dry_run: bool = True,
    prune_legacy: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "dataRoot": str(data_root),
        "dryRun": dry_run,
        "pruneLegacy": prune_legacy,
        "datasets": [],
    }

    if not data_root.exists():
        report["warning"] = f"Data root does not exist: {data_root}"
        return report

    for dataset_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
        dataset_report = migrate_dataset(
            dataset_dir,
            dry_run=dry_run,
            prune_legacy=prune_legacy,
        )
        report["datasets"].append(dataset_report)

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate AutoRestTest data layout to run-scoped structure.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data"),
        help="Root data directory (default: data).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without writing changes.",
    )
    parser.add_argument(
        "--prune-legacy",
        action="store_true",
        help="Delete legacy runtime/trace folders and dataset-level artifacts after migration.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = migrate_data_layout(
        args.data_root,
        dry_run=args.dry_run,
        prune_legacy=args.prune_legacy,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
