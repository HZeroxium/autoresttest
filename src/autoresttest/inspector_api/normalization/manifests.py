from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from autoresttest.inspector_api.schemas import (
    DatasetDetail,
    DatasetSummary,
    ReportMetrics,
    RunManifestSummary,
)
from autoresttest.reporting import (
    build_run_inventory,
    has_valid_run_manifests,
    iter_run_dirs,
    iter_valid_dataset_dirs,
)

from .artifacts import list_artifact_summaries


TRACE_PATH_KEYS = {
    "logical_requests": "logical_requests_trace",
    "http_attempts": "http_attempts_trace",
    "llm_calls": "llm_calls_trace",
}

TRACE_FILE_NAMES = {
    "logical_requests": "logical_requests.jsonl",
    "http_attempts": "http_attempts.jsonl",
    "llm_calls": "llm_calls.jsonl",
}


def _safe_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_dataset_dir(path: Path) -> bool:
    return path.is_dir() and not path.name.startswith(".") and has_valid_run_manifests(path)


def _manifest_path_for_run_dir(run_dir: Path) -> Path:
    return run_dir / "metadata" / "runtime" / "manifest.json"


def _iter_run_manifest_paths(dataset_dir: Path) -> list[Path]:
    manifest_paths: list[Path] = []
    for run_dir in iter_run_dirs(dataset_dir):
        manifest_path = _manifest_path_for_run_dir(run_dir)
        if manifest_path.exists() and manifest_path.is_file():
            manifest_paths.append(manifest_path)
    return manifest_paths


def resolve_run_dir(
    dataset_dir: Path,
    run_id: str,
    manifest_paths: dict[str, Any] | None,
) -> Path:
    manifest_paths = manifest_paths or {}
    raw_run_dir = manifest_paths.get("run_dir")
    if isinstance(raw_run_dir, str) and raw_run_dir:
        candidate = Path(raw_run_dir)
        if candidate.exists() and candidate.is_dir():
            return candidate
    return dataset_dir / run_id


def resolve_trace_paths(
    dataset_dir: Path,
    run_id: str,
    manifest_paths: dict[str, Any] | None,
) -> dict[str, Path | None]:
    run_dir = resolve_run_dir(dataset_dir, run_id, manifest_paths)
    trace_dir = run_dir / "metadata" / "trace"
    paths: dict[str, Path | None] = {}
    manifest_paths = manifest_paths or {}
    for key, manifest_key in TRACE_PATH_KEYS.items():
        raw_path = manifest_paths.get(manifest_key)
        if isinstance(raw_path, str) and raw_path:
            candidate = Path(raw_path)
        else:
            candidate = trace_dir / TRACE_FILE_NAMES[key]
        paths[key] = candidate if candidate.exists() else None
    return paths


def build_run_manifest_summary(
    dataset_id: str,
    manifest_payload: dict[str, Any],
    dataset_dir: Path,
) -> RunManifestSummary:
    run_id = str(manifest_payload.get("run_id", "unknown"))
    paths = (
        manifest_payload.get("paths", {})
        if isinstance(manifest_payload.get("paths"), dict)
        else {}
    )
    trace_paths = resolve_trace_paths(dataset_dir, run_id, paths)
    return RunManifestSummary(
        run_id=run_id,
        dataset_id=dataset_id,
        status=str(manifest_payload.get("status", "unknown")),
        started_at=_safe_dt(manifest_payload.get("started_at")),
        updated_at=_safe_dt(manifest_payload.get("updated_at")),
        completed_at=_safe_dt(manifest_payload.get("completed_at")),
        paths=paths,
        counters=(
            manifest_payload.get("counters", {})
            if isinstance(manifest_payload.get("counters"), dict)
            else {}
        ),
        trace_availability={key: path is not None for key, path in trace_paths.items()},
    )


def list_run_manifests(dataset_dir: Path, file_cache: Any) -> list[RunManifestSummary]:
    manifests: list[RunManifestSummary] = []
    for manifest_path in _iter_run_manifest_paths(dataset_dir):
        try:
            payload = file_cache.get_or_load_json(manifest_path)
            if not isinstance(payload, dict):
                continue
            manifests.append(
                build_run_manifest_summary(dataset_dir.name, payload, dataset_dir)
            )
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

    for dataset_dir in iter_valid_dataset_dirs(data_root):
        runs = list_run_manifests(dataset_dir, file_cache)
        latest_run = runs[0] if runs else None
        latest_inventory = (
            build_run_inventory(
                resolve_run_dir(dataset_dir, latest_run.run_id, latest_run.paths),
                dataset=dataset_dir.name,
                json_loader=file_cache.get_or_load_json,
                jsonl_loader=file_cache.get_or_load_jsonl,
            )
            if latest_run is not None
            else None
        )

        has_data_artifacts = False
        has_trace_artifacts = False
        for run in runs:
            run_dir = resolve_run_dir(dataset_dir, run.run_id, run.paths)
            if (run_dir / "report.json").exists() or (run_dir / "q_tables.json").exists():
                has_data_artifacts = True
            trace_dir = run_dir / "metadata" / "trace"
            if trace_dir.exists() and any(path.suffix == ".jsonl" for path in trace_dir.iterdir()):
                has_trace_artifacts = True

        graph_cache_exists = (cache_root / "graphs" / f"{dataset_dir.name}.dat").exists()
        qtable_cache_exists = (cache_root / "q_tables" / f"{dataset_dir.name}.dat").exists()

        datasets.append(
            DatasetSummary(
                dataset_id=dataset_dir.name,
                display_name=dataset_dir.name.replace("-", " "),
                has_data_artifacts=has_data_artifacts,
                has_runtime_manifests=bool(runs),
                has_trace_artifacts=has_trace_artifacts,
                has_graph_cache=graph_cache_exists,
                has_qtable_cache=qtable_cache_exists,
                latest_run_id=latest_run.run_id if latest_run else None,
                latest_run_status=latest_run.status if latest_run else None,
                latest_updated_at=latest_run.updated_at if latest_run else None,
                latest_total_requests_sent=(
                    latest_inventory.metrics.total_requests_sent
                    if latest_inventory is not None
                    else None
                ),
                latest_total_tokens=(
                    latest_inventory.metrics.total_tokens
                    if latest_inventory is not None
                    else None
                ),
                latest_report_schema=(
                    latest_inventory.metrics.report_schema
                    if latest_inventory is not None
                    else None
                ),
            )
        )
    return datasets


def get_dataset_detail(dataset_dir: Path, cache_root: Path, file_cache: Any) -> DatasetDetail:
    runs = list_run_manifests(dataset_dir, file_cache)
    datasets = list_datasets(dataset_dir.parent, cache_root, file_cache)
    dataset = next(item for item in datasets if item.dataset_id == dataset_dir.name)

    report_summary = None
    report_metrics: ReportMetrics | None = None
    artifact_names: list[str] = []
    trace_file_count = 0
    if runs:
        latest_run = runs[0]
        latest_run_dir = resolve_run_dir(dataset_dir, latest_run.run_id, latest_run.paths)
        latest_inventory = build_run_inventory(
            latest_run_dir,
            dataset=dataset_dir.name,
            json_loader=file_cache.get_or_load_json,
            jsonl_loader=file_cache.get_or_load_jsonl,
        )
        report_path = latest_run_dir / "report.json"
        if report_path.exists():
            payload = file_cache.get_or_load_json(report_path)
            if isinstance(payload, dict):
                report_summary = payload
        if latest_inventory is not None:
            report_metrics = ReportMetrics.model_validate(
                latest_inventory.metrics.to_dict()
            )

        artifacts = list_artifact_summaries(
            dataset_dir.name,
            latest_run.run_id,
            latest_run_dir,
            file_cache,
        ).artifacts
        artifact_names = [artifact.name for artifact in artifacts if artifact.available]

        for run in runs:
            run_dir = resolve_run_dir(dataset_dir, run.run_id, run.paths)
            trace_dir = run_dir / "metadata" / "trace"
            if trace_dir.exists():
                trace_file_count += len(list(trace_dir.glob("*.jsonl")))

    return DatasetDetail(
        dataset=dataset,
        latest_run=runs[0] if runs else None,
        report_summary=report_summary,
        report_metrics=report_metrics,
        run_count=len(runs),
        trace_file_count=trace_file_count,
        artifact_names=artifact_names,
        has_graph_cache=dataset.has_graph_cache,
        has_qtable_cache=dataset.has_qtable_cache,
        warnings=[],
    )
