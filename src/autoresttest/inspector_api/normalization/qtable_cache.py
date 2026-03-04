from __future__ import annotations

import shelve
from pathlib import Path
from typing import Any

from autoresttest.inspector_api.schemas import CacheQTableSnapshot


def load_cached_qtable_snapshot(dataset_id: str, cache_root: Path, file_cache: Any) -> CacheQTableSnapshot:
    base_path = cache_root / "q_tables" / dataset_id
    dat_path = base_path.with_suffix(".dat")
    dir_path = base_path.with_suffix(".dir")
    bak_path = base_path.with_suffix(".bak")
    if not dat_path.exists():
        raise FileNotFoundError(f"Cached q-table store not found for {dataset_id}")

    def _load() -> dict[str, Any]:
        with shelve.open(str(base_path)) as db:
            return db.get(dataset_id, {"value": {}, "header": {}})

    payload = file_cache.get_or_load_custom(
        ("qtable-cache", str(base_path.resolve())),
        [dat_path, dir_path, bak_path],
        _load,
    )
    if not isinstance(payload, dict):
        payload = {"value": {}, "header": {}}

    value_agent = payload.get("value", {}) if isinstance(payload.get("value"), dict) else {}
    header_agent = payload.get("header", {}) if isinstance(payload.get("header"), dict) else {}
    return CacheQTableSnapshot(
        dataset_id=dataset_id,
        value_agent=value_agent,
        header_agent=header_agent,
        warnings=[],
    )
