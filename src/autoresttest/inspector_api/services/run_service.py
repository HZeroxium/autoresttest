from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.schemas import RunBundleSummary, RunManifestSummary

from ..normalization.manifests import list_run_manifests, resolve_run_dir
from ..normalization.traces import load_trace_streams
from .dataset_service import get_dataset_dir


def list_runs(context: AppContext, dataset_id: str) -> list[RunManifestSummary]:
    dataset_dir = get_dataset_dir(context, dataset_id)
    return list_run_manifests(dataset_dir, context.file_cache)


def get_run_manifest(
    context: AppContext,
    dataset_id: str,
    run_id: str,
) -> RunManifestSummary:
    dataset_dir = get_dataset_dir(context, dataset_id)
    manifests = list_run_manifests(dataset_dir, context.file_cache)
    manifest = next((item for item in manifests if item.run_id == run_id), None)
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "run_not_found",
                "message": f"Run '{run_id}' was not found for dataset '{dataset_id}'.",
            },
        )
    return manifest


def _load_optional_json(path: Path, file_cache: Any) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = file_cache.get_or_load_json(path)
    if isinstance(payload, dict):
        return payload
    return None


def get_run_summary(context: AppContext, dataset_id: str, run_id: str) -> RunBundleSummary:
    dataset_dir = get_dataset_dir(context, dataset_id)
    manifest = get_run_manifest(context, dataset_id, run_id)
    run_dir = resolve_run_dir(dataset_dir, run_id, manifest.paths)

    report = _load_optional_json(run_dir / "report.json", context.file_cache)
    operation_status_codes = _load_optional_json(
        run_dir / "operation_status_codes.json",
        context.file_cache,
    )
    qtable_payload = _load_optional_json(run_dir / "q_tables.json", context.file_cache)

    streams = load_trace_streams(
        dataset_dir,
        context.file_cache,
        run_id=run_id,
        manifest_paths=manifest.paths,
    )
    trace_counts = {key: len(value) for key, value in streams.items()}
    phase_summaries: dict[str, dict[str, int]] = {}
    for events in streams.values():
        for event in events:
            phase_name = event.phase or "unknown"
            if phase_name not in phase_summaries:
                phase_summaries[phase_name] = {
                    "logical_request": 0,
                    "http_attempt": 0,
                    "llm_call": 0,
                }
            phase_summaries[phase_name][event.trace_kind] = (
                phase_summaries[phase_name].get(event.trace_kind, 0) + 1
            )

    warnings: list[str] = []
    if not manifest.trace_availability.get("llm_calls", False):
        warnings.append("This run does not include an llm_calls trace file.")
    if not run_dir.exists():
        warnings.append(
            f"Run directory '{run_dir}' is missing; this run may be partially migrated."
        )

    return RunBundleSummary(
        manifest=manifest,
        report=report,
        operation_status_codes=operation_status_codes,
        has_qtable_snapshot=qtable_payload is not None,
        trace_counts=trace_counts,
        phase_summaries=phase_summaries,
        warnings=warnings,
    )
