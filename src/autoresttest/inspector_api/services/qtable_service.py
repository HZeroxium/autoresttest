from __future__ import annotations

from fastapi import HTTPException, status

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.schemas import CacheQTableSnapshot, QTableSnapshot

from ..normalization.manifests import resolve_run_dir
from ..normalization.qtable_cache import load_cached_qtable_snapshot
from ..normalization.qtable_runtime import build_runtime_qtable_snapshot
from .dataset_service import get_dataset_dir
from .run_service import get_run_manifest


def get_runtime_qtable_snapshot(
    context: AppContext,
    dataset_id: str,
    run_id: str,
) -> QTableSnapshot:
    dataset_dir = get_dataset_dir(context, dataset_id)
    run_manifest = get_run_manifest(context, dataset_id, run_id)
    run_dir = resolve_run_dir(dataset_dir, run_id, run_manifest.paths)
    path = run_dir / "q_tables.json"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "runtime_qtable_not_found",
                "message": (
                    f"Runtime q_tables.json is not available for "
                    f"dataset '{dataset_id}' run '{run_id}'."
                ),
            },
        )
    payload = context.file_cache.get_or_load_json(path)
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "invalid_runtime_qtable",
                "message": "Runtime q_tables.json is invalid.",
            },
        )
    return build_runtime_qtable_snapshot(dataset_id, payload)


def get_cached_qtable_snapshot(
    context: AppContext,
    dataset_id: str,
    *,
    allow_missing: bool = False,
) -> CacheQTableSnapshot:
    try:
        return load_cached_qtable_snapshot(
            dataset_id,
            context.settings.cache_root,
            context.file_cache,
        )
    except FileNotFoundError:
        if allow_missing:
            return CacheQTableSnapshot(
                dataset_id=dataset_id,
                value_agent={},
                header_agent={},
                warnings=["Cached q-table store is unavailable."],
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "cached_qtable_not_found",
                "message": (
                    f"Cached q-table store is not available for dataset '{dataset_id}'."
                ),
            },
        )
