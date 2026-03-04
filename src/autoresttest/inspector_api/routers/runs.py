from __future__ import annotations

from fastapi import APIRouter, Depends

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.dependencies import get_context
from autoresttest.inspector_api.schemas import RunBundleSummary, RunManifestSummary
from autoresttest.inspector_api.services.run_service import get_run_summary, list_runs


router = APIRouter(prefix="/datasets/{dataset_id}/runs", tags=["runs"])


@router.get("", response_model=list[RunManifestSummary])
def list_dataset_runs(
    dataset_id: str,
    context: AppContext = Depends(get_context),
) -> list[RunManifestSummary]:
    return list_runs(context, dataset_id)


@router.get("/{run_id}", response_model=RunBundleSummary)
def get_dataset_run(
    dataset_id: str,
    run_id: str,
    context: AppContext = Depends(get_context),
) -> RunBundleSummary:
    return get_run_summary(context, dataset_id, run_id)
