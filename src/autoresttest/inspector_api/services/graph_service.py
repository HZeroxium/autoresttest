from __future__ import annotations

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.schemas import GraphSnapshot

from ..normalization.graph_cache import load_graph_snapshot
from .qtable_service import get_cached_qtable_snapshot, get_runtime_qtable_snapshot


def get_graph_snapshot(context: AppContext, dataset_id: str) -> GraphSnapshot:
    runtime_qtables = get_runtime_qtable_snapshot(context, dataset_id)
    cached_qtables = get_cached_qtable_snapshot(context, dataset_id, allow_missing=True)
    return load_graph_snapshot(
        dataset_id,
        context.settings.cache_root,
        context.file_cache,
        runtime_operations=set(runtime_qtables.operations.keys()),
        cached_value_operations=set(cached_qtables.value_agent.keys()),
    )
