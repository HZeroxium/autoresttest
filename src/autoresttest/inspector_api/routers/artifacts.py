from __future__ import annotations

from fastapi import APIRouter, Depends

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.dependencies import get_context
from autoresttest.inspector_api.schemas import ArtifactsResponse
from autoresttest.inspector_api.services.artifact_service import (
    get_artifact_payload,
    get_artifact_summaries,
)


router = APIRouter(prefix="/datasets/{dataset_id}", tags=["artifacts"])


@router.get("/runs/{run_id}/artifacts", response_model=ArtifactsResponse)
def list_artifacts(
    dataset_id: str,
    run_id: str,
    context: AppContext = Depends(get_context),
) -> ArtifactsResponse:
    return get_artifact_summaries(context, dataset_id, run_id)


@router.get("/runs/{run_id}/artifacts/{artifact_name}")
def read_artifact(
    dataset_id: str,
    run_id: str,
    artifact_name: str,
    context: AppContext = Depends(get_context),
) -> dict[str, object]:
    return get_artifact_payload(context, dataset_id, run_id, artifact_name)
