from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from autoresttest.inspector_api.schemas import (
    OperationMetric,
    OperationMetricsResponse,
    TimelinePage,
    TraceChainItem,
    TraceChainPage,
    TraceChainSummary,
    UnifiedTraceEvent,
)

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


def _status_family(status_code: int | None) -> str | None:
    if status_code is None:
        return None
    return f"{status_code // 100}xx"


def _kind_label(trace_kind: str) -> str:
    return {
        "logical_request": "Logical request",
        "http_attempt": "HTTP attempt",
        "llm_call": "LLM call",
    }.get(trace_kind, trace_kind.replace("_", " ").title())


def _build_summary_label(
    raw_event: dict[str, Any],
    *,
    trace_kind: str,
    status_code: int | None,
    llm_purpose: str | None,
    cache_hit: bool | None,
) -> str:
    if trace_kind == "logical_request":
        event_type = raw_event.get("event_type") or raw_event.get("logical_event_type") or "logical"
        operation_id = raw_event.get("operation_id") or raw_event.get("logical_operation_id") or "unknown"
        return f"{event_type} • {operation_id}"

    if trace_kind == "http_attempt":
        method = str(raw_event.get("http_method") or "HTTP").upper()
        transport_error = raw_event.get("transport_error")
        if isinstance(transport_error, dict):
            label = transport_error.get("type") or transport_error.get("message") or "transport_error"
            return f"{method} {label}"
        if status_code is not None:
            return f"{method} {status_code}"
        return method

    if trace_kind == "llm_call":
        mode = "cache" if cache_hit else "live"
        return f"{llm_purpose or 'llm'} • {mode}"

    return trace_kind


def _token_total(raw_event: dict[str, Any]) -> int | None:
    llm_payload = raw_event.get("llm")
    if not isinstance(llm_payload, dict):
        return None
    input_tokens = llm_payload.get("input_tokens")
    output_tokens = llm_payload.get("output_tokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    return input_tokens + output_tokens


def _trim_payload(event: UnifiedTraceEvent) -> dict[str, Any]:
    payload = event.payload
    summary: dict[str, Any] = {
        "previewOnly": True,
        "traceKind": event.trace_kind,
        "eventSequenceId": event.event_sequence_id,
        "operationId": event.operation_id,
        "logicalRequestId": event.logical_request_id,
        "summaryLabel": event.summary_label,
        "payloadKeys": sorted(payload.keys()),
    }
    if event.trace_kind == "http_attempt":
        summary["http"] = {
            "method": payload.get("http_method"),
            "url": payload.get("url"),
            "statusCode": event.status_code,
            "attemptIndex": payload.get("attempt_index"),
        }
    elif event.trace_kind == "llm_call":
        llm_payload = payload.get("llm")
        if isinstance(llm_payload, dict):
            summary["llm"] = {
                "model": llm_payload.get("model"),
                "cacheHit": llm_payload.get("cache_hit"),
                "inputTokens": llm_payload.get("input_tokens"),
                "outputTokens": llm_payload.get("output_tokens"),
            }
    elif event.trace_kind == "logical_request":
        summary["logical"] = {
            "eventType": payload.get("event_type"),
            "requestFailed": payload.get("request_failed"),
            "attemptCount": payload.get("attempt_count"),
        }
    return summary


def _normalize_event(
    raw_event: dict[str, Any],
    inferred_trace_kind: str,
    fallback_sequence: int,
) -> UnifiedTraceEvent:
    trace_kind = str(raw_event.get("trace_kind", inferred_trace_kind))
    response_payload = raw_event.get("response")
    status_code = None
    if isinstance(response_payload, dict):
        status_code = response_payload.get("status_code")
    if status_code is None and isinstance(raw_event.get("status_code"), int):
        status_code = raw_event["status_code"]
    metadata = raw_event.get("metadata", {})
    llm_payload = raw_event.get("llm", {})
    cache_hit = llm_payload.get("cache_hit") if isinstance(llm_payload, dict) else None
    llm_purpose = metadata.get("llm_purpose") if isinstance(metadata, dict) else None
    is_retry = bool(raw_event.get("attempt_index", 1) > 1)
    normalized_status = status_code if isinstance(status_code, int) else None
    is_error = (
        bool(normalized_status is not None and normalized_status >= 400)
        or isinstance(raw_event.get("transport_error"), dict)
        or bool(raw_event.get("request_failed"))
    )

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
        status_code=normalized_status,
        transport_error=raw_event.get("transport_error")
        if isinstance(raw_event.get("transport_error"), dict)
        else None,
        llm_purpose=llm_purpose,
        cache_hit=cache_hit if isinstance(cache_hit, bool) else None,
        kind_label=_kind_label(trace_kind),
        summary_label=_build_summary_label(
            raw_event,
            trace_kind=trace_kind,
            status_code=normalized_status,
            llm_purpose=llm_purpose,
            cache_hit=cache_hit if isinstance(cache_hit, bool) else None,
        ),
        status_family=_status_family(normalized_status),
        is_error=is_error,
        is_retry=is_retry,
        token_total=_token_total(raw_event),
        payload=raw_event,
    )


def _apply_payload_mode(event: UnifiedTraceEvent, include_payload: bool) -> UnifiedTraceEvent:
    if include_payload:
        return event
    return event.model_copy(update={"payload": _trim_payload(event)})


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
    lowered = search.lower()
    if event.summary_label and lowered in event.summary_label.lower():
        return True
    haystack = json.dumps(event.payload, ensure_ascii=False).lower()
    return lowered in haystack


def _filter_events(
    events: Iterable[UnifiedTraceEvent],
    *,
    phase: str | None = None,
    operation_id: str | None = None,
    logical_request_id: int | None = None,
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
        if logical_request_id is not None and event.logical_request_id != logical_request_id:
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
        if min_duration_ms is not None and (
            event.duration_ms is None or event.duration_ms < min_duration_ms
        ):
            continue
        if max_duration_ms is not None and (
            event.duration_ms is None or event.duration_ms > max_duration_ms
        ):
            continue
        if not _matches_search(event, search):
            continue
        filtered.append(event)
    return filtered


def _group_chain_key(event: UnifiedTraceEvent) -> tuple[str, int]:
    if event.logical_request_id is not None:
        return (f"logical:{event.logical_request_id}", event.logical_request_id)
    return (f"orphan:{event.trace_kind}:{event.event_sequence_id}", -1)


def _dominant_status_code(events: list[UnifiedTraceEvent]) -> int | None:
    counts: dict[int, int] = {}
    for event in events:
        if event.trace_kind != "http_attempt" or event.status_code is None:
            continue
        counts[event.status_code] = counts.get(event.status_code, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


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
    logical_request_id: int | None = None,
    trace_kind: str | None = None,
    status_code: int | None = None,
    search: str | None = None,
    include_payload: bool = True,
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
        logical_request_id=logical_request_id,
        trace_kind=trace_kind,
        status_code=status_code,
        search=search,
    )

    if after_event_sequence_id is not None:
        filtered = [
            event for event in filtered if event.event_sequence_id > after_event_sequence_id
        ]

    bounded_limit = max(1, min(limit, 5000))
    page_events = [_apply_payload_mode(event, include_payload) for event in filtered[:bounded_limit]]
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


def build_trace_chain_page(
    dataset_dir: Path,
    file_cache: Any,
    *,
    run_id: str,
    manifest_paths: dict[str, Any] | None,
    limit: int = 100,
    phase: str | None = None,
    operation_id: str | None = None,
    trace_kind: str | None = None,
    status_code: int | None = None,
    search: str | None = None,
) -> TraceChainPage:
    streams = load_trace_streams(
        dataset_dir,
        file_cache,
        run_id=run_id,
        manifest_paths=manifest_paths,
    )
    merged = [event for stream in streams.values() for event in stream]
    ordered_events, _ = _sort_events(merged)

    grouped_all: dict[str, list[UnifiedTraceEvent]] = defaultdict(list)
    chain_order: dict[str, int] = {}
    chain_logical_id: dict[str, int | None] = {}
    for event in ordered_events:
        chain_id, logical_id = _group_chain_key(event)
        grouped_all[chain_id].append(event)
        chain_logical_id[chain_id] = logical_id if logical_id >= 0 else None
        chain_order.setdefault(chain_id, event.event_sequence_id)

    chain_summaries: list[TraceChainSummary] = []
    for chain_id, chain_events in sorted(chain_order.items(), key=lambda item: item[1]):
        events = grouped_all[chain_id]
        matching_events = _filter_events(
            events,
            phase=phase,
            operation_id=operation_id,
            trace_kind=trace_kind,
            status_code=status_code,
            search=search,
        )
        if not matching_events:
            continue

        logical_event = next((event for event in events if event.trace_kind == "logical_request"), None)
        header_event = logical_event or events[0]
        items = [
            TraceChainItem(
                event_sequence_id=event.event_sequence_id,
                trace_kind=event.trace_kind,
                timestamp=event.timestamp,
                duration_ms=event.duration_ms,
                status_code=event.status_code,
                is_error=bool(event.is_error),
                is_retry=bool(event.is_retry),
                summary_label=event.summary_label or event.kind_label or event.trace_kind,
                operation_id=event.operation_id,
                logical_request_id=event.logical_request_id,
            )
            for event in matching_events
        ]
        chain_summaries.append(
            TraceChainSummary(
                chain_id=chain_id,
                logical_request_id=chain_logical_id[chain_id],
                is_orphan=logical_event is None,
                phase=header_event.phase,
                component=header_event.component,
                operation_id=header_event.operation_id,
                started_at=_safe_dt(logical_event.payload.get("started_at")) if logical_event else events[0].timestamp,
                completed_at=_safe_dt(logical_event.payload.get("completed_at")) if logical_event else events[-1].timestamp,
                duration_ms=logical_event.duration_ms if logical_event else None,
                event_sequence_start=events[0].event_sequence_id,
                event_sequence_end=events[-1].event_sequence_id,
                http_attempt_count=sum(1 for event in events if event.trace_kind == "http_attempt"),
                llm_call_count=sum(1 for event in events if event.trace_kind == "llm_call"),
                has_error=any(bool(event.is_error) for event in events),
                has_retry=any(bool(event.is_retry) for event in events if event.trace_kind == "http_attempt"),
                has_cache_hit=any(bool(event.cache_hit) for event in events if event.trace_kind == "llm_call"),
                dominant_status_code=_dominant_status_code(events),
                items=items,
            )
        )

    bounded_limit = max(1, min(limit, 500))
    page_chains = chain_summaries[:bounded_limit]
    has_more = len(chain_summaries) > bounded_limit
    cursor = page_chains[-1].event_sequence_end if page_chains else 0
    return TraceChainPage(
        run_id=run_id,
        cursor=cursor,
        chains=page_chains,
        has_more=has_more,
        warnings=[],
    )


def build_operation_metrics(
    dataset_dir: Path,
    file_cache: Any,
    *,
    run_id: str,
    manifest_paths: dict[str, Any] | None,
) -> OperationMetricsResponse:
    streams = load_trace_streams(
        dataset_dir,
        file_cache,
        run_id=run_id,
        manifest_paths=manifest_paths,
    )
    merged = [event for stream in streams.values() for event in stream]
    ordered_events, _ = _sort_events(merged)

    metrics: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "logical_count": 0,
            "http_attempt_count": 0,
            "llm_call_count": 0,
            "retry_count": 0,
            "success_2xx_count": 0,
            "client_error_4xx_count": 0,
            "server_error_5xx_count": 0,
            "transport_error_count": 0,
            "_logical_durations": [],
            "_child_durations": [],
            "_token_total": 0,
        }
    )

    for event in ordered_events:
        if not event.operation_id:
            continue
        bucket = metrics[event.operation_id]
        if event.trace_kind == "logical_request":
            bucket["logical_count"] += 1
            if isinstance(event.duration_ms, (int, float)):
                bucket["_logical_durations"].append(float(event.duration_ms))
        elif event.trace_kind == "http_attempt":
            bucket["http_attempt_count"] += 1
            if bool(event.is_retry):
                bucket["retry_count"] += 1
            if isinstance(event.duration_ms, (int, float)):
                bucket["_child_durations"].append(float(event.duration_ms))
            if event.transport_error is not None:
                bucket["transport_error_count"] += 1
            if event.status_code is not None:
                if 200 <= event.status_code < 300:
                    bucket["success_2xx_count"] += 1
                elif 400 <= event.status_code < 500:
                    bucket["client_error_4xx_count"] += 1
                elif event.status_code >= 500:
                    bucket["server_error_5xx_count"] += 1
        elif event.trace_kind == "llm_call":
            bucket["llm_call_count"] += 1
            if isinstance(event.duration_ms, (int, float)):
                bucket["_child_durations"].append(float(event.duration_ms))
            if event.token_total is not None:
                bucket["_token_total"] += event.token_total

    operation_metrics: list[OperationMetric] = []
    total_token_count = 0
    total_logical = total_http = total_llm = 0
    for operation_id, bucket in metrics.items():
        durations = bucket["_logical_durations"] or bucket["_child_durations"]
        avg_duration_ms = round(mean(durations), 3) if durations else None
        max_duration_ms = round(max(durations), 3) if durations else None
        total_token_count += int(bucket["_token_total"])
        total_logical += int(bucket["logical_count"])
        total_http += int(bucket["http_attempt_count"])
        total_llm += int(bucket["llm_call_count"])
        operation_metrics.append(
            OperationMetric(
                operation_id=operation_id,
                logical_count=int(bucket["logical_count"]),
                http_attempt_count=int(bucket["http_attempt_count"]),
                llm_call_count=int(bucket["llm_call_count"]),
                retry_count=int(bucket["retry_count"]),
                success_2xx_count=int(bucket["success_2xx_count"]),
                client_error_4xx_count=int(bucket["client_error_4xx_count"]),
                server_error_5xx_count=int(bucket["server_error_5xx_count"]),
                transport_error_count=int(bucket["transport_error_count"]),
                avg_duration_ms=avg_duration_ms,
                max_duration_ms=max_duration_ms,
            )
        )

    operation_metrics.sort(key=lambda metric: metric.operation_id)
    return OperationMetricsResponse(
        run_id=run_id,
        operations=operation_metrics,
        totals={
            "operationCount": len(operation_metrics),
            "logicalCount": total_logical,
            "httpAttemptCount": total_http,
            "llmCallCount": total_llm,
            "tokenTotal": total_token_count,
        },
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
    logical_request_id: int | None = None,
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
        logical_request_id=logical_request_id,
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
