from __future__ import annotations

from fastapi import APIRouter, Depends

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.dependencies import get_context
from autoresttest.inspector_api.schemas import GraphSnapshot
from autoresttest.inspector_api.services.graph_service import get_graph_snapshot


router = APIRouter(prefix="/datasets/{dataset_id}", tags=["graph"])


@router.get("/graph", response_model=GraphSnapshot)
def get_graph(
    dataset_id: str,
    context: AppContext = Depends(get_context),
) -> GraphSnapshot:
    return get_graph_snapshot(context, dataset_id)
