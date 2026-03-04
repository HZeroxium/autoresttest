from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from autoresttest.inspector_api.config import AppContext
from autoresttest.inspector_api.dependencies import get_context
from autoresttest.inspector_api.schemas import TimelinePage
from autoresttest.inspector_api.services.trace_service import get_timeline, get_trace_stream


router = APIRouter(prefix="/datasets/{dataset_id}/runs/{run_id}", tags=["traces"])


@router.get("/timeline", response_model=TimelinePage)
def read_timeline(
    dataset_id: str,
    run_id: str,
    after_event_sequence_id: int | None = Query(default=None, alias="afterEventSequenceId"),
    limit: int = 500,
    phase: str | None = None,
    operation_id: str | None = Query(default=None, alias="operationId"),
    trace_kind: str | None = Query(default=None, alias="traceKind"),
    status_code: int | None = Query(default=None, alias="statusCode"),
    search: str | None = None,
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
        trace_kind=trace_kind,
        status_code=status_code,
        search=search,
    )


@router.get("/logical-requests")
def read_logical_requests(
    dataset_id: str,
    run_id: str,
    offset: int = 0,
    limit: int = 200,
    phase: str | None = None,
    operation_id: str | None = Query(default=None, alias="operationId"),
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
        llm_purpose=llm_purpose,
        cache_hit=cache_hit,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
    )
