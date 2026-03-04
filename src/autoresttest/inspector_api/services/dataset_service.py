from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.schemas import DatasetDetail, DatasetSummary

from ..normalization.manifests import get_dataset_detail, list_datasets


def get_dataset_dir(context: AppContext, dataset_id: str) -> Path:
    dataset_dir = context.settings.data_root / dataset_id
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "dataset_not_found",
                "message": f"Dataset '{dataset_id}' was not found.",
            },
        )
    return dataset_dir


def list_dataset_summaries(context: AppContext) -> list[DatasetSummary]:
    return list_datasets(
        context.settings.data_root,
        context.settings.cache_root,
        context.file_cache,
    )


def get_dataset_summary(context: AppContext, dataset_id: str) -> DatasetDetail:
    dataset_dir = get_dataset_dir(context, dataset_id)
    return get_dataset_detail(
        dataset_dir,
        context.settings.cache_root,
        context.file_cache,
    )
