from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from autoresttest.run_artifacts import PROJECT_ROOT

from .file_cache import FileCache


@dataclass(frozen=True)
class InspectorSettings:
    host: str = "127.0.0.1"
    port: int = 8008
    poll_interval_ms: int = 1500
    data_root: Path = PROJECT_ROOT / "data"
    cache_root: Path = PROJECT_ROOT / "cache"
    static_root: Path = PROJECT_ROOT / "apps" / "autoresttest-inspector" / "web" / "dist"
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8008",
        "http://localhost:8008",
    )


@dataclass
class AppContext:
    settings: InspectorSettings
    file_cache: FileCache = field(default_factory=FileCache)
    warnings: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def get_settings() -> InspectorSettings:
    return InspectorSettings()


def build_context(settings: InspectorSettings | None = None) -> AppContext:
    return AppContext(settings=settings or get_settings())
