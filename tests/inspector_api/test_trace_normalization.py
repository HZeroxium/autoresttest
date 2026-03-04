from __future__ import annotations

from autoresttest.inspector_api.config import InspectorSettings, build_context
from autoresttest.inspector_api.services.run_service import list_runs
from autoresttest.inspector_api.services.trace_service import get_timeline
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
