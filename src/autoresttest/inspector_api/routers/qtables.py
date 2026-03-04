from __future__ import annotations

from fastapi import APIRouter, Depends

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.dependencies import get_context
from autoresttest.inspector_api.schemas import CacheQTableSnapshot, QTableSnapshot
from autoresttest.inspector_api.services.qtable_service import (
    get_cached_qtable_snapshot,
    get_runtime_qtable_snapshot,
)


router = APIRouter(prefix="/datasets/{dataset_id}", tags=["qtables"])


@router.get("/q-tables", response_model=QTableSnapshot)
def get_runtime_qtables(
    dataset_id: str,
    context: AppContext = Depends(get_context),
) -> QTableSnapshot:
    return get_runtime_qtable_snapshot(context, dataset_id)


@router.get("/cache/q-table", response_model=CacheQTableSnapshot)
def get_cached_qtables(
    dataset_id: str,
    context: AppContext = Depends(get_context),
) -> CacheQTableSnapshot:
    return get_cached_qtable_snapshot(context, dataset_id)
