from __future__ import annotations

from statistics import mean
from typing import Any

from autoresttest.inspector_api.schemas import QTableAgentSummary, QTableSnapshot


def _collect_numeric_values(value: Any, sink: list[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        sink.append(float(value))
        return
    if isinstance(value, dict):
        for nested in value.values():
            _collect_numeric_values(nested, sink)
        return
    if isinstance(value, list):
        for nested in value:
            _collect_numeric_values(nested, sink)


def build_runtime_qtable_snapshot(dataset_id: str, payload: dict[str, Any]) -> QTableSnapshot:
    agent_summaries: list[QTableAgentSummary] = []
    operation_names: set[str] = set()

    for agent_name, agent_payload in payload.items():
        if isinstance(agent_payload, str):
            agent_summaries.append(
                QTableAgentSummary(
                    agent_name=agent_name,
                    entry_count=0,
                    non_zero_count=0,
                    sparsity_ratio=1.0,
                )
            )
            continue

        numeric_values: list[float] = []
        _collect_numeric_values(agent_payload, numeric_values)
        non_zero_values = [value for value in numeric_values if abs(value) > 0]
        if isinstance(agent_payload, dict):
            operation_names.update(str(key) for key in agent_payload.keys())

        agent_summaries.append(
            QTableAgentSummary(
                agent_name=agent_name,
                entry_count=len(numeric_values),
                non_zero_count=len(non_zero_values),
                min_value=min(numeric_values) if numeric_values else None,
                max_value=max(numeric_values) if numeric_values else None,
                mean_value=round(mean(numeric_values), 6) if numeric_values else None,
                sparsity_ratio=round(
                    1.0 - (len(non_zero_values) / len(numeric_values)),
                    6,
                )
                if numeric_values
                else 1.0,
            )
        )

    operations = {
        operation_name: {
            agent_name: agent_payload.get(operation_name)
            for agent_name, agent_payload in payload.items()
            if isinstance(agent_payload, dict) and operation_name in agent_payload
        }
        for operation_name in sorted(operation_names)
    }

    return QTableSnapshot(
        dataset_id=dataset_id,
        runtime_qtables=payload,
        agent_summaries=agent_summaries,
        operations=operations,
        warnings=[],
    )
