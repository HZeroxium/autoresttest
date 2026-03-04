from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Hashable

import orjson


CacheLoader = Callable[[], Any]


@dataclass(frozen=True)
class CacheFingerprint:
    size: int
    mtime_ns: int


@dataclass
class _CacheEntry:
    fingerprint: tuple[tuple[int, int], ...]
    value: Any


class FileCache:
    def __init__(self, max_entries: int = 128) -> None:
        self.max_entries = max_entries
        self._entries: "OrderedDict[Hashable, _CacheEntry]" = OrderedDict()

    def get_or_load_json(self, path: Path) -> Any:
        return self._get_or_load(
            ("json", str(path.resolve())),
            self._file_fingerprint(path),
            lambda: json.loads(path.read_text(encoding="utf-8")),
        )

    def get_or_load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        return self._get_or_load(
            ("jsonl", str(path.resolve())),
            self._file_fingerprint(path),
            lambda: [
                orjson.loads(line)
                for line in path.read_bytes().splitlines()
                if line.strip()
            ],
        )

    def get_or_load_custom(
        self,
        key: Hashable,
        fingerprint_paths: list[Path],
        loader: CacheLoader,
    ) -> Any:
        return self._get_or_load(key, self._paths_fingerprint(fingerprint_paths), loader)

    def _get_or_load(
        self,
        key: Hashable,
        fingerprint: tuple[tuple[int, int], ...],
        loader: CacheLoader,
    ) -> Any:
        entry = self._entries.get(key)
        if entry is not None and entry.fingerprint == fingerprint:
            self._entries.move_to_end(key)
            return entry.value

        value = loader()
        self._entries[key] = _CacheEntry(fingerprint=fingerprint, value=value)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        return value

    def _file_fingerprint(self, path: Path) -> tuple[tuple[int, int], ...]:
        stat = path.stat()
        return ((stat.st_size, stat.st_mtime_ns),)

    def _paths_fingerprint(self, paths: list[Path]) -> tuple[tuple[int, int], ...]:
        fingerprints: list[tuple[int, int]] = []
        for path in paths:
            if not path.exists():
                continue
            stat = path.stat()
            fingerprints.append((stat.st_size, stat.st_mtime_ns))
        return tuple(fingerprints)
