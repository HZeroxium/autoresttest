from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autoresttest.inspector_api.schemas import TimelinePage, UnifiedTraceEvent

from .manifests import resolve_trace_paths


TRACE_KIND_PRIORITY = {
    "llm_call": 0,
    "http_attempt": 1,
    "logical_request": 2,
}

TRACE_STREAM_MAP = {
    "logical_requests": "logical_request",
    "http_attempts": "http_attempt",
    "llm_calls": "llm_call",
}


def _safe_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _normalize_event(raw_event: dict[str, Any], inferred_trace_kind: str, fallback_sequence: int) -> UnifiedTraceEvent:
    trace_kind = str(raw_event.get("trace_kind", inferred_trace_kind))
    response_payload = raw_event.get("response")
    status_code = None
    if isinstance(response_payload, dict):
        status_code = response_payload.get("status_code")
    if status_code is None and isinstance(raw_event.get("status_code"), int):
        status_code = raw_event["status_code"]
    metadata = raw_event.get("metadata", {})
    llm_payload = raw_event.get("llm", {})

    return UnifiedTraceEvent(
        schema_version=int(raw_event.get("schema_version", 0) or 0),
        trace_kind=trace_kind,
        event_sequence_id=int(raw_event.get("event_sequence_id", fallback_sequence) or fallback_sequence),
        run_id=str(raw_event.get("run_id", "")),
        phase=raw_event.get("phase"),
        component=raw_event.get("component"),
        operation_id=raw_event.get("logical_operation_id") or raw_event.get("operation_id"),
        logical_request_id=raw_event.get("logical_request_id"),
        timestamp=_safe_dt(
            raw_event.get("recorded_at")
            or raw_event.get("completed_at")
            or raw_event.get("started_at")
        ),
        duration_ms=raw_event.get("duration_ms"),
        status_code=status_code if isinstance(status_code, int) else None,
        transport_error=raw_event.get("transport_error") if isinstance(raw_event.get("transport_error"), dict) else None,
        llm_purpose=metadata.get("llm_purpose") if isinstance(metadata, dict) else None,
        cache_hit=llm_payload.get("cache_hit") if isinstance(llm_payload, dict) else None,
        payload=raw_event,
    )


def load_trace_streams(
    dataset_dir: Path,
    file_cache: Any,
    *,
    run_id: str,
    manifest_paths: dict[str, Any] | None,
) -> dict[str, list[UnifiedTraceEvent]]:
    resolved = resolve_trace_paths(dataset_dir, run_id, manifest_paths)
    streams: dict[str, list[UnifiedTraceEvent]] = {}
    fallback_counter = 1
    for stream_key, trace_kind in TRACE_STREAM_MAP.items():
        path = resolved.get(stream_key)
        if path is None:
            streams[stream_key] = []
            continue
        raw_events = file_cache.get_or_load_jsonl(path)
        normalized: list[UnifiedTraceEvent] = []
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            normalized.append(_normalize_event(event, trace_kind, fallback_counter))
            fallback_counter += 1
        streams[stream_key] = normalized
    return streams


def _has_native_sequence(events: list[UnifiedTraceEvent]) -> bool:
    return bool(events) and all(
        event.payload.get("event_sequence_id") is not None for event in events
    )


def _sort_events(events: list[UnifiedTraceEvent]) -> tuple[list[UnifiedTraceEvent], str]:
    if _has_native_sequence(events):
        return sorted(events, key=lambda event: event.event_sequence_id), "native"

    sorted_events = sorted(
        events,
        key=lambda event: (
            event.timestamp or datetime.min,
            TRACE_KIND_PRIORITY.get(event.trace_kind, 99),
            event.event_sequence_id,
        ),
    )
    synthesized: list[UnifiedTraceEvent] = []
    for index, event in enumerate(sorted_events, start=1):
        synthesized.append(event.model_copy(update={"event_sequence_id": index}))
    return synthesized, "synthesized"


def _matches_search(event: UnifiedTraceEvent, search: str | None) -> bool:
    if not search:
        return True
    haystack = json.dumps(event.payload, ensure_ascii=False).lower()
    return search.lower() in haystack


def _filter_events(
    events: list[UnifiedTraceEvent],
    *,
    phase: str | None = None,
    operation_id: str | None = None,
    trace_kind: str | None = None,
    status_code: int | None = None,
    search: str | None = None,
    cache_hit: bool | None = None,
    request_failed: bool | None = None,
    transport_error: bool | None = None,
    llm_purpose: str | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
) -> list[UnifiedTraceEvent]:
    filtered: list[UnifiedTraceEvent] = []
    for event in events:
        if phase and event.phase != phase:
            continue
        if operation_id and event.operation_id != operation_id:
            continue
        if trace_kind and event.trace_kind != trace_kind:
            continue
        if status_code is not None and event.status_code != status_code:
            continue
        if cache_hit is not None and event.cache_hit != cache_hit:
            continue
        if request_failed is not None and event.payload.get("request_failed") != request_failed:
            continue
        if transport_error is not None and (event.transport_error is not None) != transport_error:
            continue
        if llm_purpose and event.llm_purpose != llm_purpose:
            continue
        if min_duration_ms is not None and (event.duration_ms is None or event.duration_ms < min_duration_ms):
            continue
        if max_duration_ms is not None and (event.duration_ms is None or event.duration_ms > max_duration_ms):
            continue
        if not _matches_search(event, search):
            continue
        filtered.append(event)
    return filtered


def build_timeline_page(
    dataset_dir: Path,
    file_cache: Any,
    *,
    run_id: str,
    manifest_paths: dict[str, Any] | None,
    after_event_sequence_id: int | None = None,
    limit: int = 500,
    phase: str | None = None,
    operation_id: str | None = None,
    trace_kind: str | None = None,
    status_code: int | None = None,
    search: str | None = None,
) -> TimelinePage:
    streams = load_trace_streams(
        dataset_dir,
        file_cache,
        run_id=run_id,
        manifest_paths=manifest_paths,
    )
    merged = [event for stream in streams.values() for event in stream]
    ordered_events, timeline_order = _sort_events(merged)
    filtered = _filter_events(
        ordered_events,
        phase=phase,
        operation_id=operation_id,
        trace_kind=trace_kind,
        status_code=status_code,
        search=search,
    )

    if after_event_sequence_id is not None:
        filtered = [
            event for event in filtered if event.event_sequence_id > after_event_sequence_id
        ]

    bounded_limit = max(1, min(limit, 5000))
    page_events = filtered[:bounded_limit]
    has_more = len(filtered) > bounded_limit
    cursor = page_events[-1].event_sequence_id if page_events else (after_event_sequence_id or 0)
    return TimelinePage(
        run_id=run_id,
        cursor=cursor,
        events=page_events,
        has_more=has_more,
        timeline_order=timeline_order,
        is_live_capable=True,
        warnings=[],
    )


def get_stream_page(
    dataset_dir: Path,
    file_cache: Any,
    *,
    run_id: str,
    manifest_paths: dict[str, Any] | None,
    stream_key: str,
    offset: int = 0,
    limit: int = 200,
    phase: str | None = None,
    operation_id: str | None = None,
    status_code: int | None = None,
    transport_error: bool | None = None,
    request_failed: bool | None = None,
    llm_purpose: str | None = None,
    cache_hit: bool | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
) -> dict[str, Any]:
    streams = load_trace_streams(
        dataset_dir,
        file_cache,
        run_id=run_id,
        manifest_paths=manifest_paths,
    )
    stream_events = streams.get(stream_key, [])
    ordered_events, timeline_order = _sort_events(stream_events)
    filtered = _filter_events(
        ordered_events,
        phase=phase,
        operation_id=operation_id,
        trace_kind=TRACE_STREAM_MAP.get(stream_key),
        status_code=status_code,
        transport_error=transport_error,
        request_failed=request_failed,
        llm_purpose=llm_purpose,
        cache_hit=cache_hit,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
    )
    bounded_limit = max(1, min(limit, 5000))
    safe_offset = max(0, offset)
    page_events = filtered[safe_offset : safe_offset + bounded_limit]
    return {
        "runId": run_id,
        "stream": stream_key,
        "offset": safe_offset,
        "limit": bounded_limit,
        "total": len(filtered),
        "timelineOrder": timeline_order,
        "events": [event.model_dump(mode="json", by_alias=True) for event in page_events],
        "warnings": [],
    }
