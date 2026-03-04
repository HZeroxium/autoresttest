from __future__ import annotations

from autoresttest.inspector_api.config import InspectorSettings, build_context
from autoresttest.inspector_api.services.run_service import list_runs
from autoresttest.inspector_api.services.trace_service import (
    get_operation_metrics,
    get_timeline,
    get_trace_chains,
)
from autoresttest.run_artifacts import PROJECT_ROOT


def test_timeline_loads_for_latest_bills_api_run() -> None:
    context = build_context(
        InspectorSettings(
            data_root=PROJECT_ROOT / "data",
            cache_root=PROJECT_ROOT / "cache",
            static_root=PROJECT_ROOT / "apps" / "autoresttest-inspector" / "web" / "dist",
        )
    )
    latest_run = list_runs(context, "Bills-api")[0]
    timeline = get_timeline(context, "Bills-api", latest_run.run_id, limit=50)
    assert timeline.events
    assert timeline.cursor >= timeline.events[-1].event_sequence_id
    assert timeline.timeline_order in {"native", "synthesized"}

    preview_timeline = get_timeline(
        context,
        "Bills-api",
        latest_run.run_id,
        logical_request_id=4,
        include_payload=False,
        limit=5,
    )
    assert preview_timeline.events
    assert preview_timeline.events[0].payload["previewOnly"] is True

    chains = get_trace_chains(context, "Bills-api", latest_run.run_id, limit=5)
    assert chains.chains
    assert chains.chains[0].items

    metrics = get_operation_metrics(context, "Bills-api", latest_run.run_id)
    assert metrics.operations
    assert metrics.totals["operationCount"] >= 1
