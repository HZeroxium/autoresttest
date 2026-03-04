from __future__ import annotations

from autoresttest.inspector_api.config import InspectorSettings, build_context
from autoresttest.inspector_api.services.dataset_service import list_dataset_summaries
from autoresttest.run_artifacts import PROJECT_ROOT


def test_list_datasets_includes_bills_api() -> None:
    context = build_context(
        InspectorSettings(
            data_root=PROJECT_ROOT / "data",
            cache_root=PROJECT_ROOT / "cache",
            static_root=PROJECT_ROOT / "apps" / "autoresttest-inspector" / "web" / "dist",
        )
    )
    dataset_ids = [dataset.dataset_id for dataset in list_dataset_summaries(context)]
    assert "Bills-api" in dataset_ids
