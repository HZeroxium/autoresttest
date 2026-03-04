from __future__ import annotations

from fastapi import HTTPException, status

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.schemas import ArtifactsResponse, CompareResponse

from ..normalization.artifacts import list_artifact_summaries, read_artifact
from ..normalization.compare import build_compare_response
from .dataset_service import get_dataset_dir
from .run_service import get_run_summary


def get_artifact_summaries(context: AppContext, dataset_id: str) -> ArtifactsResponse:
    dataset_dir = get_dataset_dir(context, dataset_id)
    return list_artifact_summaries(dataset_dir, context.file_cache)


def get_artifact_payload(context: AppContext, dataset_id: str, artifact_name: str) -> dict[str, object]:
    dataset_dir = get_dataset_dir(context, dataset_id)
    try:
        return read_artifact(dataset_dir, context.file_cache, artifact_name)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "artifact_not_found",
                "message": str(exc),
            },
        ) from exc


def compare_runs(
    context: AppContext,
    dataset_id: str,
    *,
    baseline_run_id: str,
    candidate_run_id: str,
) -> CompareResponse:
    baseline = get_run_summary(context, dataset_id, baseline_run_id)
    candidate = get_run_summary(context, dataset_id, candidate_run_id)
    return build_compare_response(dataset_id, baseline, candidate)
