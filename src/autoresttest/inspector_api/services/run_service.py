from __future__ import annotations

from fastapi import HTTPException, status

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.schemas import RunBundleSummary, RunManifestSummary

from ..normalization.manifests import list_run_manifests
from ..normalization.traces import load_trace_streams
from .dataset_service import get_dataset_dir


def list_runs(context: AppContext, dataset_id: str) -> list[RunManifestSummary]:
    dataset_dir = get_dataset_dir(context, dataset_id)
    return list_run_manifests(dataset_dir, context.file_cache)


def get_run_summary(context: AppContext, dataset_id: str, run_id: str) -> RunBundleSummary:
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

    report = None
    report_path = dataset_dir / "report.json"
    if report_path.exists():
        payload = context.file_cache.get_or_load_json(report_path)
        if isinstance(payload, dict):
            report = payload

    operation_status_codes = None
    status_path = dataset_dir / "operation_status_codes.json"
    if status_path.exists():
        payload = context.file_cache.get_or_load_json(status_path)
        if isinstance(payload, dict):
            operation_status_codes = payload

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
            phase_summaries[phase_name][event.trace_kind] = phase_summaries[phase_name].get(event.trace_kind, 0) + 1

    warnings: list[str] = []
    if not manifest.trace_availability.get("llm_calls", False):
        warnings.append("This run does not include an llm_calls trace file.")

    return RunBundleSummary(
        manifest=manifest,
        report=report,
        operation_status_codes=operation_status_codes,
        trace_counts=trace_counts,
        phase_summaries=phase_summaries,
        warnings=warnings,
    )
