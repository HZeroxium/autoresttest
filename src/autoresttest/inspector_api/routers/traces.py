from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.dependencies import get_context
from autoresttest.inspector_api.schemas import (
    OperationMetricsResponse,
    TimelinePage,
    TraceChainPage,
    TraceFacetsResponse,
)
from autoresttest.inspector_api.services.trace_service import (
    get_operation_metrics,
    get_trace_facets,
    get_timeline,
    get_trace_chains,
    get_trace_stream,
)


router = APIRouter(prefix="/datasets/{dataset_id}/runs/{run_id}", tags=["traces"])


@router.get("/timeline", response_model=TimelinePage)
def read_timeline(
    dataset_id: str,
    run_id: str,
    after_event_sequence_id: int | None = Query(default=None, alias="afterEventSequenceId"),
    limit: int = 500,
    phase: str | None = None,
    operation_id: str | None = Query(default=None, alias="operationId"),
    logical_request_id: int | None = Query(default=None, alias="logicalRequestId"),
    trace_kind: str | None = Query(default=None, alias="traceKind"),
    status_code: int | None = Query(default=None, alias="statusCode"),
    status_family: str | None = Query(default=None, alias="statusFamily"),
    search: str | None = None,
    include_payload: bool = Query(default=True, alias="includePayload"),
    cache_hit: bool | None = Query(default=None, alias="cacheHit"),
    request_failed: bool | None = Query(default=None, alias="requestFailed"),
    transport_error: bool | None = Query(default=None, alias="transportError"),
    llm_purpose: str | None = Query(default=None, alias="llmPurpose"),
    min_duration_ms: float | None = Query(default=None, alias="minDurationMs"),
    max_duration_ms: float | None = Query(default=None, alias="maxDurationMs"),
    context: AppContext = Depends(get_context),
) -> TimelinePage:
    return get_timeline(
        context,
        dataset_id,
        run_id,
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


@router.get("/trace-chains", response_model=TraceChainPage)
def read_trace_chains(
    dataset_id: str,
    run_id: str,
    after_event_sequence_id: int | None = Query(default=None, alias="afterEventSequenceId"),
    limit: int = 100,
    phase: str | None = None,
    operation_id: str | None = Query(default=None, alias="operationId"),
    trace_kind: str | None = Query(default=None, alias="traceKind"),
    status_code: int | None = Query(default=None, alias="statusCode"),
    status_family: str | None = Query(default=None, alias="statusFamily"),
    search: str | None = None,
    cache_hit: bool | None = Query(default=None, alias="cacheHit"),
    request_failed: bool | None = Query(default=None, alias="requestFailed"),
    transport_error: bool | None = Query(default=None, alias="transportError"),
    llm_purpose: str | None = Query(default=None, alias="llmPurpose"),
    min_duration_ms: float | None = Query(default=None, alias="minDurationMs"),
    max_duration_ms: float | None = Query(default=None, alias="maxDurationMs"),
    context: AppContext = Depends(get_context),
) -> TraceChainPage:
    return get_trace_chains(
        context,
        dataset_id,
        run_id,
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


@router.get("/operation-metrics", response_model=OperationMetricsResponse)
def read_operation_metrics(
    dataset_id: str,
    run_id: str,
    context: AppContext = Depends(get_context),
) -> OperationMetricsResponse:
    return get_operation_metrics(context, dataset_id, run_id)


@router.get("/trace-facets", response_model=TraceFacetsResponse)
def read_trace_facets(
    dataset_id: str,
    run_id: str,
    phase: str | None = None,
    operation_id: str | None = Query(default=None, alias="operationId"),
    logical_request_id: int | None = Query(default=None, alias="logicalRequestId"),
    trace_kind: str | None = Query(default=None, alias="traceKind"),
    status_code: int | None = Query(default=None, alias="statusCode"),
    status_family: str | None = Query(default=None, alias="statusFamily"),
    search: str | None = None,
    cache_hit: bool | None = Query(default=None, alias="cacheHit"),
    request_failed: bool | None = Query(default=None, alias="requestFailed"),
    transport_error: bool | None = Query(default=None, alias="transportError"),
    llm_purpose: str | None = Query(default=None, alias="llmPurpose"),
    min_duration_ms: float | None = Query(default=None, alias="minDurationMs"),
    max_duration_ms: float | None = Query(default=None, alias="maxDurationMs"),
    context: AppContext = Depends(get_context),
) -> TraceFacetsResponse:
    return get_trace_facets(
        context,
        dataset_id,
        run_id,
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


@router.get("/logical-requests")
def read_logical_requests(
    dataset_id: str,
    run_id: str,
    offset: int = 0,
    limit: int = 200,
    phase: str | None = None,
    operation_id: str | None = Query(default=None, alias="operationId"),
    logical_request_id: int | None = Query(default=None, alias="logicalRequestId"),
    request_failed: bool | None = Query(default=None, alias="requestFailed"),
    context: AppContext = Depends(get_context),
) -> dict[str, object]:
    return get_trace_stream(
        context,
        dataset_id,
        run_id,
        stream_key="logical_requests",
        offset=offset,
        limit=limit,
        phase=phase,
        operation_id=operation_id,
        logical_request_id=logical_request_id,
        request_failed=request_failed,
    )


@router.get("/http-attempts")
def read_http_attempts(
    dataset_id: str,
    run_id: str,
    offset: int = 0,
    limit: int = 200,
    phase: str | None = None,
    operation_id: str | None = Query(default=None, alias="operationId"),
    logical_request_id: int | None = Query(default=None, alias="logicalRequestId"),
    status_code: int | None = Query(default=None, alias="statusCode"),
    transport_error: bool | None = Query(default=None, alias="transportError"),
    min_duration_ms: float | None = Query(default=None, alias="minDurationMs"),
    max_duration_ms: float | None = Query(default=None, alias="maxDurationMs"),
    context: AppContext = Depends(get_context),
) -> dict[str, object]:
    return get_trace_stream(
        context,
        dataset_id,
        run_id,
        stream_key="http_attempts",
        offset=offset,
        limit=limit,
        phase=phase,
        operation_id=operation_id,
        logical_request_id=logical_request_id,
        status_code=status_code,
        transport_error=transport_error,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
    )


@router.get("/llm-calls")
def read_llm_calls(
    dataset_id: str,
    run_id: str,
    offset: int = 0,
    limit: int = 200,
    phase: str | None = None,
    operation_id: str | None = Query(default=None, alias="operationId"),
    logical_request_id: int | None = Query(default=None, alias="logicalRequestId"),
    llm_purpose: str | None = Query(default=None, alias="llmPurpose"),
    cache_hit: bool | None = Query(default=None, alias="cacheHit"),
    min_duration_ms: float | None = Query(default=None, alias="minDurationMs"),
    max_duration_ms: float | None = Query(default=None, alias="maxDurationMs"),
    context: AppContext = Depends(get_context),
) -> dict[str, object]:
    return get_trace_stream(
        context,
        dataset_id,
        run_id,
        stream_key="llm_calls",
        offset=offset,
        limit=limit,
        phase=phase,
        operation_id=operation_id,
        logical_request_id=logical_request_id,
        llm_purpose=llm_purpose,
        cache_hit=cache_hit,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
    )
