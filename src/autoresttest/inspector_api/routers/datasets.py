from __future__ import annotations

from fastapi import APIRouter, Depends

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.dependencies import get_context
from autoresttest.inspector_api.schemas import DatasetDetail, DatasetSummary
from autoresttest.inspector_api.services.dataset_service import (
    get_dataset_summary,
    list_dataset_summaries,
)


router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetSummary])
def list_datasets(context: AppContext = Depends(get_context)) -> list[DatasetSummary]:
    return list_dataset_summaries(context)


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(
    dataset_id: str,
    context: AppContext = Depends(get_context),
) -> DatasetDetail:
    return get_dataset_summary(context, dataset_id)
