from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class ApiError(CamelModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class AdapterHealth(CamelModel):
    status: str
    version: str
    data_root: str
    cache_root: str
    static_root: str
    static_assets_available: bool
    poll_interval_ms: int


class DatasetSummary(CamelModel):
    dataset_id: str
    display_name: str
    has_data_artifacts: bool
    has_runtime_manifests: bool
    has_trace_artifacts: bool
    has_graph_cache: bool
    has_qtable_cache: bool
    latest_run_id: str | None = None
    latest_run_status: str | None = None
    latest_updated_at: datetime | None = None


class RunManifestSummary(CamelModel):
    run_id: str
    dataset_id: str
    status: str
    started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    paths: dict[str, Any] = Field(default_factory=dict)
    counters: dict[str, Any] = Field(default_factory=dict)
    trace_availability: dict[str, bool] = Field(default_factory=dict)


class DatasetDetail(CamelModel):
    dataset: DatasetSummary
    latest_run: RunManifestSummary | None = None
    report_summary: dict[str, Any] | None = None
    run_count: int
    trace_file_count: int
    artifact_names: list[str]
    has_graph_cache: bool
    has_qtable_cache: bool
    warnings: list[str] = Field(default_factory=list)


class RunBundleSummary(CamelModel):
    manifest: RunManifestSummary
    report: dict[str, Any] | None = None
    operation_status_codes: dict[str, dict[str, int]] | None = None
    trace_counts: dict[str, int] = Field(default_factory=dict)
    phase_summaries: dict[str, dict[str, int]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class GraphNode(CamelModel):
    id: str
    label: str
    method: str
    path: str
    summary: str | None = None
    parameter_count: int
    required_parameter_count: int
    request_body_mime_types: list[str] = Field(default_factory=list)
    response_statuses: list[str] = Field(default_factory=list)
    has_runtime_qtable: bool
    has_cached_value_qtable: bool


class GraphEdge(CamelModel):
    id: str
    source_id: str
    target_id: str
    layer: str
    is_effective: bool
    similarity_links: list[dict[str, Any]] = Field(default_factory=list)
    max_similarity: float
    link_count: int


class GraphSnapshot(CamelModel):
    dataset_id: str
    node_count: int
    edge_count: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    warnings: list[str] = Field(default_factory=list)


class QTableAgentSummary(CamelModel):
    agent_name: str
    entry_count: int
    non_zero_count: int
    min_value: float | None = None
    max_value: float | None = None
    mean_value: float | None = None
    sparsity_ratio: float


class QTableSnapshot(CamelModel):
    dataset_id: str
    runtime_qtables: dict[str, Any]
    agent_summaries: list[QTableAgentSummary]
    operations: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class CacheQTableSnapshot(CamelModel):
    dataset_id: str
    value_agent: dict[str, Any]
    header_agent: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class UnifiedTraceEvent(CamelModel):
    schema_version: int
    trace_kind: str
    event_sequence_id: int
    run_id: str
    phase: str | None = None
    component: str | None = None
    operation_id: str | None = None
    logical_request_id: int | None = None
    timestamp: datetime | None = None
    duration_ms: float | None = None
    status_code: int | None = None
    transport_error: dict[str, Any] | None = None
    llm_purpose: str | None = None
    cache_hit: bool | None = None
    payload: dict[str, Any]


class TimelinePage(CamelModel):
    run_id: str
    cursor: int
    events: list[UnifiedTraceEvent]
    has_more: bool
    timeline_order: str
    is_live_capable: bool
    warnings: list[str] = Field(default_factory=list)


class ArtifactSummary(CamelModel):
    name: str
    available: bool
    size_bytes: int | None = None
    item_count: int | None = None


class ArtifactsResponse(CamelModel):
    dataset_id: str
    artifacts: list[ArtifactSummary]


class CompareResponse(CamelModel):
    dataset_id: str
    baseline_run_id: str
    candidate_run_id: str
    summary_delta: dict[str, Any]
    coverage_delta: dict[str, Any]
    trace_volume_delta: dict[str, Any]
    llm_delta: dict[str, Any]
    operation_deltas: list[dict[str, Any]]
    qtable_comparison_available: bool
    warnings: list[str] = Field(default_factory=list)
