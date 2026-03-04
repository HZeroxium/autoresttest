from __future__ import annotations

from autoresttest.inspector_api.config import InspectorSettings, build_context
from autoresttest.inspector_api.services.graph_service import get_graph_snapshot
from autoresttest.run_artifacts import PROJECT_ROOT


def test_graph_snapshot_for_bills_api_has_nodes_and_edges() -> None:
    context = build_context(
        InspectorSettings(
            data_root=PROJECT_ROOT / "data",
            cache_root=PROJECT_ROOT / "cache",
            static_root=PROJECT_ROOT / "apps" / "autoresttest-inspector" / "web" / "dist",
        )
    )
    graph = get_graph_snapshot(context, "Bills-api")
    assert graph.node_count > 0
    assert graph.edge_count > 0
    bill_node = next(node for node in graph.nodes if node.id == "GetBill")
    assert bill_node.resource_group == "Bills"
    assert bill_node.total_degree >= 0
