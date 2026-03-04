from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from autoresttest.inspector_api.schemas import (
    DatasetDetail,
    DatasetSummary,
    RunManifestSummary,
)

from .artifacts import list_artifact_summaries


TRACE_PATH_KEYS = {
    "logical_requests": "logical_requests_trace",
    "http_attempts": "http_attempts_trace",
    "llm_calls": "llm_calls_trace",
}


def _safe_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_valid_manifest_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix != ".json":
        return False
    if path.name == "latest_run_manifest.json":
        return False
    if path.name.endswith(".tmp"):
        return False
    return path.name.endswith(".manifest.json")


def _is_dataset_dir(path: Path) -> bool:
    return path.is_dir() and not path.name.startswith(".")


def resolve_trace_paths(
    dataset_dir: Path,
    run_id: str,
    manifest_paths: dict[str, Any] | None,
) -> dict[str, Path | None]:
    trace_dir = dataset_dir / "trace"
    paths: dict[str, Path | None] = {}
    manifest_paths = manifest_paths or {}
    for key, manifest_key in TRACE_PATH_KEYS.items():
        raw_path = manifest_paths.get(manifest_key)
        candidate: Path | None = None
        if isinstance(raw_path, str) and raw_path:
            candidate = Path(raw_path)
        else:
            candidate = trace_dir / f"{run_id}.{key}.jsonl"
        if candidate.exists():
            paths[key] = candidate
        else:
            paths[key] = None
    return paths


def build_run_manifest_summary(
    dataset_id: str,
    manifest_payload: dict[str, Any],
    dataset_dir: Path,
) -> RunManifestSummary:
    run_id = str(manifest_payload.get("run_id", "unknown"))
    trace_paths = resolve_trace_paths(dataset_dir, run_id, manifest_payload.get("paths"))
    return RunManifestSummary(
        run_id=run_id,
        dataset_id=dataset_id,
        status=str(manifest_payload.get("status", "unknown")),
        started_at=_safe_dt(manifest_payload.get("started_at")),
        updated_at=_safe_dt(manifest_payload.get("updated_at")),
        completed_at=_safe_dt(manifest_payload.get("completed_at")),
        paths=manifest_payload.get("paths", {}) if isinstance(manifest_payload.get("paths"), dict) else {},
        counters=manifest_payload.get("counters", {}) if isinstance(manifest_payload.get("counters"), dict) else {},
        trace_availability={key: path is not None for key, path in trace_paths.items()},
    )


def list_run_manifests(dataset_dir: Path, file_cache: Any) -> list[RunManifestSummary]:
    runtime_dir = dataset_dir / "runtime"
    if not runtime_dir.exists():
        return []

    manifests: list[RunManifestSummary] = []
    for path in runtime_dir.iterdir():
        if not _is_valid_manifest_file(path):
            continue
        try:
            payload = file_cache.get_or_load_json(path)
            if not isinstance(payload, dict):
                continue
            manifests.append(build_run_manifest_summary(dataset_dir.name, payload, dataset_dir))
        except Exception:
            continue

    manifests.sort(
        key=lambda item: item.started_at or item.updated_at or datetime.min,
        reverse=True,
    )
    return manifests


def list_datasets(data_root: Path, cache_root: Path, file_cache: Any) -> list[DatasetSummary]:
    datasets: list[DatasetSummary] = []
    if not data_root.exists():
        return datasets

    for dataset_dir in sorted(path for path in data_root.iterdir() if _is_dataset_dir(path)):
        runs = list_run_manifests(dataset_dir, file_cache)
        latest_run = runs[0] if runs else None
        trace_dir = dataset_dir / "trace"
        runtime_dir = dataset_dir / "runtime"
        graph_cache_exists = (cache_root / "graphs" / f"{dataset_dir.name}.dat").exists()
        qtable_cache_exists = (cache_root / "q_tables" / f"{dataset_dir.name}.dat").exists()
        datasets.append(
            DatasetSummary(
                dataset_id=dataset_dir.name,
                display_name=dataset_dir.name.replace("-", " "),
                has_data_artifacts=any((dataset_dir / name).exists() for name in ("report.json", "q_tables.json")),
                has_runtime_manifests=runtime_dir.exists() and any(_is_valid_manifest_file(path) for path in runtime_dir.iterdir()),
                has_trace_artifacts=trace_dir.exists() and any(path.suffix == ".jsonl" for path in trace_dir.iterdir()),
                has_graph_cache=graph_cache_exists,
                has_qtable_cache=qtable_cache_exists,
                latest_run_id=latest_run.run_id if latest_run else None,
                latest_run_status=latest_run.status if latest_run else None,
                latest_updated_at=latest_run.updated_at if latest_run else None,
            )
        )
    return datasets


def get_dataset_detail(dataset_dir: Path, cache_root: Path, file_cache: Any) -> DatasetDetail:
    runs = list_run_manifests(dataset_dir, file_cache)
    datasets = list_datasets(dataset_dir.parent, cache_root, file_cache)
    dataset = next(item for item in datasets if item.dataset_id == dataset_dir.name)
    report_summary = None
    report_path = dataset_dir / "report.json"
    if report_path.exists():
        payload = file_cache.get_or_load_json(report_path)
        if isinstance(payload, dict):
            report_summary = payload

    trace_dir = dataset_dir / "trace"
    trace_file_count = len(list(trace_dir.glob("*.jsonl"))) if trace_dir.exists() else 0
    artifacts = list_artifact_summaries(dataset_dir, file_cache).artifacts
    return DatasetDetail(
        dataset=dataset,
        latest_run=runs[0] if runs else None,
        report_summary=report_summary,
        run_count=len(runs),
        trace_file_count=trace_file_count,
        artifact_names=[artifact.name for artifact in artifacts if artifact.available],
        has_graph_cache=dataset.has_graph_cache,
        has_qtable_cache=dataset.has_qtable_cache,
        warnings=[],
    )
