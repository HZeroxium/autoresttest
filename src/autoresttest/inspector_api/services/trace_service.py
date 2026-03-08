from __future__ import annotations

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.schemas import (
    OperationMetricsResponse,
    TimelinePage,
    TraceChainPage,
    TraceFacetsResponse,
)

from ..normalization.traces import (
    build_operation_metrics,
    build_trace_facets,
    build_timeline_page,
    build_trace_chain_page,
    get_stream_page,
)
from .dataset_service import get_dataset_dir
from .run_service import get_run_manifest


def get_timeline(
    context: AppContext,
    dataset_id: str,
    run_id: str,
    *,
    after_event_sequence_id: int | None = None,
    limit: int = 500,
    phase: str | None = None,
    operation_id: str | None = None,
    logical_request_id: int | None = None,
    trace_kind: str | None = None,
    status_code: int | None = None,
    status_family: str | None = None,
    search: str | None = None,
    include_payload: bool = True,
    cache_hit: bool | None = None,
    request_failed: bool | None = None,
    transport_error: bool | None = None,
    llm_purpose: str | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
) -> TimelinePage:
    dataset_dir = get_dataset_dir(context, dataset_id)
    run_manifest = get_run_manifest(context, dataset_id, run_id)
    return build_timeline_page(
        dataset_dir,
        context.file_cache,
        run_id=run_id,
        manifest_paths=run_manifest.paths,
        after_event_sequence_id=after_event_sequence_id,
        limit=limit,
        phase=phase,
        operation_id=operation_id,
        logical_request_id=logical_request_id,
        trace_kind=trace_kind,
        status_code=status_code,
        status_family=status_family,
        search=search,
        include_payload=include_payload,
        cache_hit=cache_hit,
        request_failed=request_failed,
        transport_error=transport_error,
        llm_purpose=llm_purpose,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
    )


def get_trace_stream(
    context: AppContext,
    dataset_id: str,
    run_id: str,
    *,
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
) -> dict[str, object]:
    dataset_dir = get_dataset_dir(context, dataset_id)
    run_manifest = get_run_manifest(context, dataset_id, run_id)
    return get_stream_page(
        dataset_dir,
        context.file_cache,
        run_id=run_id,
        manifest_paths=run_manifest.paths,
        stream_key=stream_key,
        offset=offset,
        limit=limit,
        phase=phase,
        operation_id=operation_id,
        logical_request_id=logical_request_id,
        status_code=status_code,
        transport_error=transport_error,
        request_failed=request_failed,
        llm_purpose=llm_purpose,
        cache_hit=cache_hit,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
    )


def get_trace_chains(
    context: AppContext,
    dataset_id: str,
    run_id: str,
    *,
    after_event_sequence_id: int | None = None,
    limit: int = 100,
    phase: str | None = None,
    operation_id: str | None = None,
    trace_kind: str | None = None,
    status_code: int | None = None,
    status_family: str | None = None,
    search: str | None = None,
    cache_hit: bool | None = None,
    request_failed: bool | None = None,
    transport_error: bool | None = None,
    llm_purpose: str | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
) -> TraceChainPage:
    dataset_dir = get_dataset_dir(context, dataset_id)
    run_manifest = get_run_manifest(context, dataset_id, run_id)
    return build_trace_chain_page(
        dataset_dir,
        context.file_cache,
        run_id=run_id,
        manifest_paths=run_manifest.paths,
        after_event_sequence_id=after_event_sequence_id,
        limit=limit,
        phase=phase,
        operation_id=operation_id,
        trace_kind=trace_kind,
        status_code=status_code,
        status_family=status_family,
        search=search,
        cache_hit=cache_hit,
        request_failed=request_failed,
        transport_error=transport_error,
        llm_purpose=llm_purpose,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
    )


def get_operation_metrics(
    context: AppContext,
    dataset_id: str,
    run_id: str,
) -> OperationMetricsResponse:
    dataset_dir = get_dataset_dir(context, dataset_id)
    run_manifest = get_run_manifest(context, dataset_id, run_id)
    return build_operation_metrics(
        dataset_dir,
        context.file_cache,
        run_id=run_id,
        manifest_paths=run_manifest.paths,
    )


def get_trace_facets(
    context: AppContext,
    dataset_id: str,
    run_id: str,
    *,
    phase: str | None = None,
    operation_id: str | None = None,
    logical_request_id: int | None = None,
    trace_kind: str | None = None,
    status_code: int | None = None,
    status_family: str | None = None,
    search: str | None = None,
    cache_hit: bool | None = None,
    request_failed: bool | None = None,
    transport_error: bool | None = None,
    llm_purpose: str | None = None,
    min_duration_ms: float | None = None,
    max_duration_ms: float | None = None,
) -> TraceFacetsResponse:
    dataset_dir = get_dataset_dir(context, dataset_id)
    run_manifest = get_run_manifest(context, dataset_id, run_id)
    return build_trace_facets(
        dataset_dir,
        context.file_cache,
        run_id=run_id,
        manifest_paths=run_manifest.paths,
        phase=phase,
        operation_id=operation_id,
        logical_request_id=logical_request_id,
        trace_kind=trace_kind,
        status_code=status_code,
        status_family=status_family,
        search=search,
        cache_hit=cache_hit,
        request_failed=request_failed,
        transport_error=transport_error,
        llm_purpose=llm_purpose,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
    )
