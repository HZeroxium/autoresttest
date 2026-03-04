from __future__ import annotations

from fastapi import APIRouter, Depends

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.dependencies import get_context
from autoresttest.inspector_api.schemas import AdapterHealth


router = APIRouter(tags=["health"])


@router.get("/health", response_model=AdapterHealth)
def read_health(context: AppContext = Depends(get_context)) -> AdapterHealth:
    settings = context.settings
    return AdapterHealth(
        status="ok",
        version="0.1.0",
        data_root=str(settings.data_root),
        cache_root=str(settings.cache_root),
        static_root=str(settings.static_root),
        static_assets_available=settings.static_root.exists(),
        poll_interval_ms=settings.poll_interval_ms,
    )
