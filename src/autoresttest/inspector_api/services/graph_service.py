from __future__ import annotations

from fastapi import HTTPException

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.schemas import GraphSnapshot

from ..normalization.graph_cache import load_graph_snapshot
from .qtable_service import get_cached_qtable_snapshot, get_runtime_qtable_snapshot


def get_graph_snapshot(
    context: AppContext,
    dataset_id: str,
    run_id: str | None = None,
) -> GraphSnapshot:
    runtime_operations: set[str] = set()
    warnings: list[str] = []
    if run_id:
        try:
            runtime_qtables = get_runtime_qtable_snapshot(context, dataset_id, run_id)
            runtime_operations = set(runtime_qtables.operations.keys())
        except HTTPException:
            warnings.append(
                f"Runtime q-table snapshot is unavailable for run '{run_id}'."
            )

    cached_qtables = get_cached_qtable_snapshot(context, dataset_id, allow_missing=True)
    snapshot = load_graph_snapshot(
        dataset_id,
        context.settings.cache_root,
        context.file_cache,
        runtime_operations=runtime_operations,
        cached_value_operations=set(cached_qtables.value_agent.keys()),
    )
    if warnings:
        snapshot = snapshot.model_copy(update={"warnings": [*snapshot.warnings, *warnings]})
    return snapshot
