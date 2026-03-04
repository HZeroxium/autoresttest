from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.dependencies import get_context
from autoresttest.inspector_api.schemas import CompareResponse
from autoresttest.inspector_api.services.artifact_service import compare_runs


router = APIRouter(prefix="/datasets/{dataset_id}", tags=["compare"])


@router.get("/compare", response_model=CompareResponse)
def read_compare(
    dataset_id: str,
    baseline_run_id: str = Query(alias="baselineRunId"),
    candidate_run_id: str = Query(alias="candidateRunId"),
    context: AppContext = Depends(get_context),
) -> CompareResponse:
    return compare_runs(
        context,
        dataset_id,
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
    )
