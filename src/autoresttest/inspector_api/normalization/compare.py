from __future__ import annotations

from typing import Any

from autoresttest.inspector_api.schemas import CompareResponse, RunBundleSummary


def build_compare_response(
    dataset_id: str,
    baseline: RunBundleSummary,
    candidate: RunBundleSummary,
) -> CompareResponse:
    baseline_report = baseline.report or {}
    candidate_report = candidate.report or {}
    baseline_status = baseline_report.get("Status Code Distribution", {})
    candidate_status = candidate_report.get("Status Code Distribution", {})
    baseline_total = baseline_report.get("Total Requests Sent", 0)
    candidate_total = candidate_report.get("Total Requests Sent", 0)
    baseline_success = baseline_report.get("Number of Successfully Processed Operations", 0)
    candidate_success = candidate_report.get("Number of Successfully Processed Operations", 0)

    operation_deltas: list[dict[str, Any]] = []
    baseline_ops = baseline.operation_status_codes or {}
    candidate_ops = candidate.operation_status_codes or {}
    for operation_id in sorted(set(baseline_ops) | set(candidate_ops)):
        before = baseline_ops.get(operation_id, {})
        after = candidate_ops.get(operation_id, {})
        if before == after:
            continue
        operation_deltas.append(
            {
                "operationId": operation_id,
                "baseline": before,
                "candidate": after,
            }
        )

    baseline_llm = baseline.trace_counts.get("llm_calls", 0)
    candidate_llm = candidate.trace_counts.get("llm_calls", 0)
    qtable_comparison_available = (
        bool(baseline.has_qtable_snapshot) and bool(candidate.has_qtable_snapshot)
    )
    return CompareResponse(
        dataset_id=dataset_id,
        baseline_run_id=baseline.manifest.run_id,
        candidate_run_id=candidate.manifest.run_id,
        summary_delta={
            "totalRequests": candidate_total - baseline_total,
            "successfulOperations": candidate_success - baseline_success,
            "statusCodes": {
                str(code): int(candidate_status.get(code, 0)) - int(baseline_status.get(code, 0))
                for code in sorted(set(baseline_status) | set(candidate_status))
            },
        },
        coverage_delta={
            "baseline": baseline_success,
            "candidate": candidate_success,
            "delta": candidate_success - baseline_success,
        },
        trace_volume_delta={
            key: candidate.trace_counts.get(key, 0) - baseline.trace_counts.get(key, 0)
            for key in sorted(set(baseline.trace_counts) | set(candidate.trace_counts))
        },
        llm_delta={
            "baselineCalls": baseline_llm,
            "candidateCalls": candidate_llm,
            "deltaCalls": candidate_llm - baseline_llm,
        },
        operation_deltas=operation_deltas,
        qtable_comparison_available=qtable_comparison_available,
        warnings=[],
    )
