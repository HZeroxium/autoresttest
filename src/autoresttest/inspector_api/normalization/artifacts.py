from __future__ import annotations

from pathlib import Path
from typing import Any

from autoresttest.inspector_api.schemas import (
    ArtifactPreviewEntry,
    ArtifactPreviewResponse,
    ArtifactSummary,
    ArtifactsResponse,
)


SUPPORTED_ARTIFACTS = (
    "report.json",
    "operation_status_codes.json",
    "q_tables.json",
    "successful_parameters.json",
    "successful_bodies.json",
    "successful_primitives.json",
    "successful_responses.json",
    "server_errors.json",
)

SUMMARY_LOAD_LIMIT_BYTES = 2_000_000
LARGE_PREVIEW_WARNING_BYTES = 8_000_000


def _preview_value(value: Any) -> tuple[str, int | None, dict[str, Any] | None]:
    if isinstance(value, dict):
        return (
            "object",
            len(value),
            {
                "sampleKeys": list(value.keys())[:8],
            },
        )
    if isinstance(value, list):
        return (
            "array",
            len(value),
            {
                "firstItem": value[0] if value else None,
            },
        )
    if isinstance(value, str):
        return (
            "string",
            None,
            {
                "value": value[:240],
                "truncated": len(value) > 240,
            },
        )
    return (
        type(value).__name__,
        None,
        {
            "value": value,
        },
    )


def _build_summary(payload: Any, *, size_bytes: int | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "sizeBytes": size_bytes,
        "topLevelType": type(payload).__name__,
    }
    if isinstance(payload, dict):
        summary["totalItems"] = len(payload)
        summary["sampleKeys"] = list(payload.keys())[:12]
    elif isinstance(payload, list):
        summary["totalItems"] = len(payload)
    else:
        summary["totalItems"] = 1
    return summary


def _filter_object_entries(
    payload: dict[str, Any],
    *,
    search: str | None,
    operation_id: str | None,
) -> list[tuple[str, Any]]:
    search_text = search.lower() if search else None
    filtered: list[tuple[str, Any]] = []
    for key, value in payload.items():
        key_text = str(key)
        if operation_id and key_text != operation_id:
            continue
        if search_text and search_text not in key_text.lower():
            continue
        filtered.append((key_text, value))
    filtered.sort(key=lambda item: item[0])
    return filtered


def list_artifact_summaries(
    dataset_id: str,
    run_id: str,
    run_dir: Path,
    file_cache: Any,
    *,
    include_qtables: bool = True,
) -> ArtifactsResponse:
    artifact_names = (
        SUPPORTED_ARTIFACTS
        if include_qtables
        else SUPPORTED_ARTIFACTS[0:2] + SUPPORTED_ARTIFACTS[3:]
    )
    summaries: list[ArtifactSummary] = []
    for name in artifact_names:
        path = run_dir / name
        available = path.exists() and path.is_file()
        item_count = None
        size_bytes = None
        if available:
            size_bytes = path.stat().st_size
            if size_bytes <= SUMMARY_LOAD_LIMIT_BYTES:
                try:
                    payload = file_cache.get_or_load_json(path)
                    if isinstance(payload, dict):
                        item_count = len(payload)
                    elif isinstance(payload, list):
                        item_count = len(payload)
                except Exception:
                    item_count = None
        summaries.append(
            ArtifactSummary(
                name=name,
                available=available,
                size_bytes=size_bytes,
                item_count=item_count,
            )
        )
    return ArtifactsResponse(dataset_id=dataset_id, run_id=run_id, artifacts=summaries)


def build_artifact_preview(
    dataset_id: str,
    run_id: str,
    run_dir: Path,
    file_cache: Any,
    artifact_name: str,
    *,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
    operation_id: str | None = None,
) -> ArtifactPreviewResponse:
    if artifact_name not in SUPPORTED_ARTIFACTS:
        raise FileNotFoundError(f"Unsupported artifact: {artifact_name}")
    path = run_dir / artifact_name
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_name}")

    payload = file_cache.get_or_load_json(path)
    size_bytes = path.stat().st_size
    warnings: list[str] = []
    if size_bytes >= LARGE_PREVIEW_WARNING_BYTES:
        warnings.append(
            "This artifact is large. Preview is paginated; raw JSON may take longer to load."
        )

    summary = _build_summary(payload, size_bytes=size_bytes)
    safe_offset = max(0, offset)
    safe_limit = max(1, min(limit, 200))

    if isinstance(payload, dict):
        filtered_entries = _filter_object_entries(
            payload,
            search=search,
            operation_id=operation_id,
        )
        paged_entries = filtered_entries[safe_offset : safe_offset + safe_limit]
        entries = [
            ArtifactPreviewEntry(
                key=key,
                value_type=_preview_value(value)[0],
                item_count=_preview_value(value)[1],
                preview=_preview_value(value)[2],
            )
            for key, value in paged_entries
        ]
        total = len(filtered_entries)
    elif isinstance(payload, list):
        indexed_entries = list(enumerate(payload))
        if search:
            search_text = search.lower()
            indexed_entries = [
                (index, value)
                for index, value in indexed_entries
                if search_text in str(value).lower()
            ]
        paged_entries = indexed_entries[safe_offset : safe_offset + safe_limit]
        entries = [
            ArtifactPreviewEntry(
                key=str(index),
                value_type=_preview_value(value)[0],
                item_count=_preview_value(value)[1],
                preview=_preview_value(value)[2],
            )
            for index, value in paged_entries
        ]
        total = len(indexed_entries)
    else:
        value_type, item_count, preview = _preview_value(payload)
        entries = [
            ArtifactPreviewEntry(
                key="value",
                value_type=value_type,
                item_count=item_count,
                preview=preview,
            )
        ]
        total = len(entries)

    return ArtifactPreviewResponse(
        dataset_id=dataset_id,
        run_id=run_id,
        artifact_name=artifact_name,
        summary=summary,
        offset=safe_offset,
        limit=safe_limit,
        total=total,
        has_more=safe_offset + safe_limit < total,
        entries=entries,
        warnings=warnings,
    )


def read_artifact(
    dataset_id: str,
    run_id: str,
    run_dir: Path,
    file_cache: Any,
    artifact_name: str,
) -> dict[str, Any]:
    if artifact_name not in SUPPORTED_ARTIFACTS:
        raise FileNotFoundError(f"Unsupported artifact: {artifact_name}")
    path = run_dir / artifact_name
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_name}")
    payload = file_cache.get_or_load_json(path)
    return {
        "datasetId": dataset_id,
        "runId": run_id,
        "artifactName": artifact_name,
        "payload": payload,
    }
