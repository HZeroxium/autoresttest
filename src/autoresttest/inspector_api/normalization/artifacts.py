from __future__ import annotations

from pathlib import Path
from typing import Any

from autoresttest.inspector_api.schemas import ArtifactSummary, ArtifactsResponse


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


def list_artifact_summaries(
    dataset_id: str,
    run_id: str,
    run_dir: Path,
    file_cache: Any,
    *,
    include_qtables: bool = True,
) -> ArtifactsResponse:
    artifact_names = SUPPORTED_ARTIFACTS if include_qtables else SUPPORTED_ARTIFACTS[0:2] + SUPPORTED_ARTIFACTS[3:]
    summaries: list[ArtifactSummary] = []
    for name in artifact_names:
        path = run_dir / name
        available = path.exists() and path.is_file()
        item_count = None
        size_bytes = None
        if available:
            size_bytes = path.stat().st_size
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
    if not isinstance(payload, dict):
        return {
            "datasetId": dataset_id,
            "runId": run_id,
            "artifactName": artifact_name,
            "payload": payload,
        }
    return {
        "datasetId": dataset_id,
        "runId": run_id,
        "artifactName": artifact_name,
        "payload": payload,
    }
