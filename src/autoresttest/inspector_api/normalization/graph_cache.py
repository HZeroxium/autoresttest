from __future__ import annotations

import shelve
from pathlib import Path
from typing import Any

from autoresttest.inspector_api.schemas import GraphEdge, GraphNode, GraphSnapshot
from autoresttest.models import ParameterProperties, ResponseProperties, to_dict_helper


def _count_required_parameters(parameters: dict[Any, ParameterProperties]) -> int:
    return sum(1 for parameter in parameters.values() if getattr(parameter, "required", False))


def _edge_similarity_links(similar_parameters: dict[Any, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for source_key, values in similar_parameters.items():
        source_name = "|".join(str(part) for part in source_key) if isinstance(source_key, tuple) else str(source_key)
        for similarity in values or []:
            if hasattr(similarity, "to_dict"):
                converted = similarity.to_dict()
            else:
                converted = to_dict_helper(similarity)
            if isinstance(converted, dict):
                converted["source"] = source_name
                links.append(converted)
    return links


def _build_edge(layer: str, edge: Any) -> GraphEdge:
    links = _edge_similarity_links(getattr(edge, "similar_parameters", {}) or {})
    max_similarity = max((float(link.get("similarity", 0.0)) for link in links), default=0.0)
    source_id = edge.source.operation_id
    target_id = edge.destination.operation_id
    return GraphEdge(
        id=f"{layer}:{source_id}:{target_id}",
        source_id=source_id,
        target_id=target_id,
        layer=layer,
        is_effective=layer == "effective",
        similarity_links=links,
        max_similarity=round(max_similarity, 6),
        link_count=len(links),
    )


def load_graph_snapshot(
    dataset_id: str,
    cache_root: Path,
    file_cache: Any,
    *,
    runtime_operations: set[str] | None = None,
    cached_value_operations: set[str] | None = None,
) -> GraphSnapshot:
    base_path = cache_root / "graphs" / dataset_id
    dat_path = base_path.with_suffix(".dat")
    dir_path = base_path.with_suffix(".dir")
    bak_path = base_path.with_suffix(".bak")
    if not dat_path.exists():
        raise FileNotFoundError(f"Graph cache not found for {dataset_id}")

    def _load() -> dict[str, Any]:
        with shelve.open(str(base_path)) as db:
            return db[dataset_id]

    payload = file_cache.get_or_load_custom(
        ("graph-cache", str(base_path.resolve())),
        [dat_path, dir_path, bak_path],
        _load,
    )
    if not isinstance(payload, dict):
        raise ValueError("Invalid graph cache payload")

    runtime_operations = runtime_operations or set()
    cached_value_operations = cached_value_operations or set()

    nodes_dict = payload.get("nodes", {})
    edges_list = payload.get("edges", [])
    if not isinstance(nodes_dict, dict):
        raise ValueError("Invalid graph nodes")

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for operation_id, node in nodes_dict.items():
        operation_properties = node.operation_properties
        parameters = operation_properties.parameters or {}
        request_body = operation_properties.request_body or {}
        responses = operation_properties.responses or {}
        nodes.append(
            GraphNode(
                id=operation_id,
                label=operation_id,
                method=operation_properties.http_method.upper(),
                path=operation_properties.endpoint_path,
                summary=operation_properties.summary,
                parameter_count=len(parameters),
                required_parameter_count=_count_required_parameters(parameters),
                request_body_mime_types=sorted(request_body.keys()),
                response_statuses=sorted(str(code) for code in responses.keys()),
                has_runtime_qtable=operation_id in runtime_operations,
                has_cached_value_qtable=operation_id in cached_value_operations,
            )
        )

        for layer, node_edges in (
            ("effective", getattr(node, "outgoing_edges", [])),
            ("tentative", getattr(node, "tentative_edges", [])),
        ):
            for edge in node_edges:
                dedupe_key = (edge.source.operation_id, edge.destination.operation_id, layer)
                if dedupe_key in seen_edges:
                    continue
                seen_edges.add(dedupe_key)
                edges.append(_build_edge(layer, edge))

    for edge in edges_list if isinstance(edges_list, list) else []:
        dedupe_key = (edge.source.operation_id, edge.destination.operation_id, "confirmed")
        if dedupe_key in seen_edges:
            continue
        seen_edges.add(dedupe_key)
        edges.append(_build_edge("confirmed", edge))

    return GraphSnapshot(
        dataset_id=dataset_id,
        node_count=len(nodes),
        edge_count=len(edges),
        nodes=sorted(nodes, key=lambda item: item.id),
        edges=sorted(edges, key=lambda item: item.id),
        warnings=[],
    )
