from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from autoresttest.reporting import (  # noqa: E402
    RunInventory,
    build_run_inventory,
    iter_run_dirs,
    iter_valid_dataset_dirs,
)


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


@dataclass(frozen=True)
class OperationDoc:
    dataset: str
    operation: str
    operation_id: str
    method: str
    path: str
    normalized_operation: str
    doc_2xx: frozenset[str]
    doc_4xx: frozenset[str]

    @property
    def doc_all(self) -> frozenset[str]:
        return self.doc_2xx | self.doc_4xx


@dataclass(frozen=True)
class CoverageResult:
    run: str
    dataset: str
    operation: str
    matched_observed_operation: str | None
    matched_by: str
    run_status: str
    report_schema: str
    has_operation_status_codes: bool
    doc_2xx: frozenset[str]
    hit_2xx: frozenset[str]
    observed_2xx_all: frozenset[str]
    doc_4xx: frozenset[str]
    hit_4xx: frozenset[str]
    observed_4xx_all: frozenset[str]
    observed_5xx_all: frozenset[str]
    undocumented_4xx: frozenset[str]
    observed_total_requests: int
    operation_coverage: float | None

    @property
    def doc_all(self) -> frozenset[str]:
        return self.doc_2xx | self.doc_4xx

    @property
    def hit_all(self) -> frozenset[str]:
        return self.hit_2xx | self.hit_4xx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build 2xx/4xx/overall coverage from documented OpenAPI status "
            "codes and observed operation status codes."
        )
    )
    parser.add_argument(
        "--summary-csv",
        default="datasets/openapi_status_summary.csv",
        help=(
            "CSV created from OpenAPI specs. Supports legacy columns "
            "(dataset, operation, 2xx_code, 4xx_code) and enriched columns."
        ),
    )
    parser.add_argument(
        "--data-root",
        default="data",
        help="Root directory containing data/{dataset}/{run_id}/... artifacts.",
    )
    parser.add_argument(
        "--out-dir",
        default="coverage_results",
        help="Output directory for coverage reports.",
    )
    return parser.parse_args()


def normalize_operation_name(name: str) -> str:
    text = name.strip()
    if not text:
        return ""

    parts = text.split(maxsplit=1)
    if len(parts) == 2 and parts[0].lower() in HTTP_METHODS and parts[1].startswith("/"):
        method = parts[0].lower()
        path = parts[1]
        path_norm = re.sub(r"[{}]", "", path.strip().lower())
        path_norm = re.sub(r"[^a-z0-9]+", "_", path_norm).strip("_")
        return f"{method}_{path_norm}"

    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def parse_codes(raw: str) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(token.strip().upper() for token in raw.split("|") if token.strip())


def parse_documented_class(token: str) -> int | None:
    if re.fullmatch(r"[1-5]XX", token):
        return int(token[0])
    if token.isdigit():
        value = int(token)
        if 100 <= value <= 599:
            return value // 100
    return None


def parse_observed_status_code(token: str) -> int | None:
    if token.isdigit():
        value = int(token)
        if 100 <= value <= 599:
            return value
    return None


def format_ratio(hit: int, doc: int) -> str:
    if doc == 0:
        return "N/A"
    return f"{(hit / doc) * 100:.4f}"


def format_optional_float(value: float | None) -> str:
    if value is None:
        return ""
    return str(value)


def join_codes(codes: Iterable[str]) -> str:
    return "|".join(sorted(codes))


def hit_documented_codes(
    documented: frozenset[str], observed_counts: dict[str, int], wanted_class: int
) -> frozenset[str]:
    if not documented:
        return frozenset()

    observed_values = {
        parse_observed_status_code(code)
        for code, count in observed_counts.items()
        if count and count > 0
    }
    observed_values = {value for value in observed_values if value is not None}

    hit: set[str] = set()
    for token in documented:
        doc_class = parse_documented_class(token)
        if doc_class != wanted_class:
            continue
        if token.isdigit():
            if int(token) in observed_values:
                hit.add(token)
        elif token.endswith("XX"):
            if any((value // 100) == wanted_class for value in observed_values):
                hit.add(token)
    return frozenset(hit)


def observed_codes_by_class(observed_counts: dict[str, int], wanted_class: int) -> frozenset[str]:
    values = {
        parse_observed_status_code(code)
        for code, count in observed_counts.items()
        if count and count > 0
    }
    typed = sorted(
        str(value)
        for value in values
        if value is not None and (value // 100) == wanted_class
    )
    return frozenset(typed)


def is_observed_code_documented(observed_code: str, documented: frozenset[str]) -> bool:
    if observed_code in documented:
        return True
    if not observed_code.isdigit():
        return False
    code_class = int(observed_code) // 100
    wildcard = f"{code_class}XX"
    return wildcard in documented


def load_summary(summary_csv: Path) -> dict[str, list[OperationDoc]]:
    by_dataset: dict[str, list[OperationDoc]] = {}
    with summary_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            dataset = row["dataset"].strip()
            operation = row["operation"].strip()
            operation_id = row.get("operation_id", "").strip()
            method = row.get("method", "").strip().upper()
            path = row.get("path", "").strip()
            normalized_operation = row.get("normalized_operation", "").strip()
            if not normalized_operation:
                normalized_operation = normalize_operation_name(operation)
            op_doc = OperationDoc(
                dataset=dataset,
                operation=operation,
                operation_id=operation_id,
                method=method,
                path=path,
                normalized_operation=normalized_operation,
                doc_2xx=parse_codes(row.get("2xx_code", "")),
                doc_4xx=parse_codes(row.get("4xx_code", "")),
            )
            by_dataset.setdefault(dataset, []).append(op_doc)
    return by_dataset


def build_operation_index(observed: dict[str, dict[str, int]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for operation in observed:
        index.setdefault(normalize_operation_name(operation), operation)
    return index


def _match_documented_operation(
    observed: dict[str, dict[str, int]],
    observed_index: dict[str, str],
    doc: OperationDoc,
) -> tuple[str | None, str, dict[str, int]]:
    if doc.operation in observed:
        return doc.operation, "operation", observed[doc.operation]

    if doc.operation_id and doc.operation_id in observed:
        return doc.operation_id, "operation_id", observed[doc.operation_id]

    if doc.normalized_operation:
        matched_name = observed_index.get(doc.normalized_operation)
        if matched_name is not None:
            return matched_name, "normalized_operation", observed[matched_name]

    method_path_name = f"{doc.method} {doc.path}".strip()
    if method_path_name.strip() and method_path_name in observed:
        return method_path_name, "method_path", observed[method_path_name]

    return None, "unmatched", {}


def compute_operation_results(
    inventory: RunInventory,
    docs: list[OperationDoc],
) -> tuple[list[CoverageResult], list[str]]:
    results: list[CoverageResult] = []
    unmatched_doc_ops: list[str] = []

    observed = inventory.operation_status_codes or {}
    observed_index = build_operation_index(observed)

    for doc in docs:
        matched_name, matched_by, observed_counts = _match_documented_operation(
            observed,
            observed_index,
            doc,
        )
        if matched_name is None:
            unmatched_doc_ops.append(doc.operation)

        hit_2xx = hit_documented_codes(doc.doc_2xx, observed_counts, wanted_class=2)
        hit_4xx = hit_documented_codes(doc.doc_4xx, observed_counts, wanted_class=4)
        observed_2xx_all = observed_codes_by_class(observed_counts, wanted_class=2)
        observed_4xx_all = observed_codes_by_class(observed_counts, wanted_class=4)
        observed_5xx_all = observed_codes_by_class(observed_counts, wanted_class=5)
        undocumented_4xx = frozenset(
            code
            for code in observed_4xx_all
            if not is_observed_code_documented(code, doc.doc_4xx)
        )

        results.append(
            CoverageResult(
                run=inventory.run,
                dataset=inventory.dataset,
                operation=doc.operation,
                matched_observed_operation=matched_name,
                matched_by=matched_by,
                run_status=inventory.metrics.run_status,
                report_schema=inventory.metrics.report_schema,
                has_operation_status_codes=inventory.has_operation_status_codes,
                doc_2xx=doc.doc_2xx,
                hit_2xx=hit_2xx,
                observed_2xx_all=observed_2xx_all,
                doc_4xx=doc.doc_4xx,
                hit_4xx=hit_4xx,
                observed_4xx_all=observed_4xx_all,
                observed_5xx_all=observed_5xx_all,
                undocumented_4xx=undocumented_4xx,
                observed_total_requests=sum(observed_counts.values()),
                operation_coverage=inventory.metrics.successful_percentage,
            )
        )

    return results, unmatched_doc_ops


def write_operation_report(path: Path, results: list[CoverageResult]) -> None:
    fieldnames = [
        "run",
        "dataset",
        "operation",
        "matched_observed_operation",
        "doc_2xx",
        "hit_2xx",
        "doc_2xx_count",
        "hit_2xx_count",
        "coverage_2xx",
        "doc_4xx",
        "hit_4xx",
        "observed_4xx_all",
        "undocumented_4xx",
        "doc_4xx_count",
        "hit_4xx_count",
        "observed_4xx_count",
        "undocumented_4xx_count",
        "coverage_4xx",
        "doc_all",
        "hit_all",
        "doc_all_count",
        "hit_all_count",
        "coverage_all",
        "matched_by",
        "observed_2xx_all",
        "observed_5xx_all",
        "observed_total_requests",
        "operation_coverage",
        "run_status",
        "has_operation_status_codes",
        "report_schema",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            writer.writerow(
                {
                    "run": item.run,
                    "dataset": item.dataset,
                    "operation": item.operation,
                    "matched_observed_operation": item.matched_observed_operation or "",
                    "doc_2xx": join_codes(item.doc_2xx),
                    "hit_2xx": join_codes(item.hit_2xx),
                    "doc_2xx_count": len(item.doc_2xx),
                    "hit_2xx_count": len(item.hit_2xx),
                    "coverage_2xx": format_ratio(len(item.hit_2xx), len(item.doc_2xx)),
                    "doc_4xx": join_codes(item.doc_4xx),
                    "hit_4xx": join_codes(item.hit_4xx),
                    "observed_4xx_all": join_codes(item.observed_4xx_all),
                    "undocumented_4xx": join_codes(item.undocumented_4xx),
                    "doc_4xx_count": len(item.doc_4xx),
                    "hit_4xx_count": len(item.hit_4xx),
                    "observed_4xx_count": len(item.observed_4xx_all),
                    "undocumented_4xx_count": len(item.undocumented_4xx),
                    "coverage_4xx": format_ratio(len(item.hit_4xx), len(item.doc_4xx)),
                    "doc_all": join_codes(item.doc_all),
                    "hit_all": join_codes(item.hit_all),
                    "doc_all_count": len(item.doc_all),
                    "hit_all_count": len(item.hit_all),
                    "coverage_all": format_ratio(len(item.hit_all), len(item.doc_all)),
                    "matched_by": item.matched_by,
                    "observed_2xx_all": join_codes(item.observed_2xx_all),
                    "observed_5xx_all": join_codes(item.observed_5xx_all),
                    "observed_total_requests": item.observed_total_requests,
                    "operation_coverage": format_optional_float(item.operation_coverage),
                    "run_status": item.run_status,
                    "has_operation_status_codes": str(item.has_operation_status_codes).lower(),
                    "report_schema": item.report_schema,
                }
            )


def write_dataset_report(
    path: Path,
    results: list[CoverageResult],
    inventories: dict[tuple[str, str], RunInventory],
) -> None:
    fieldnames = [
        "run",
        "dataset",
        "doc_2xx_count",
        "hit_2xx_count",
        "coverage_2xx",
        "doc_4xx_count",
        "hit_4xx_count",
        "observed_4xx_count",
        "undocumented_4xx_count",
        "coverage_4xx",
        "doc_all_count",
        "hit_all_count",
        "coverage_all",
        "operation_coverage",
        "report_schema",
        "run_status",
        "snapshot_reason",
        "started_at",
        "updated_at",
        "completed_at",
        "has_report",
        "has_operation_status_codes",
        "has_qtables",
        "has_trace",
        "total_requests_sent",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "event_sequence",
        "http_attempt_count",
        "logical_count",
        "llm_call_count",
        "checkpoint_count",
        "status_code_distribution_json",
    ]

    grouped: dict[tuple[str, str], list[CoverageResult]] = {}
    for row in results:
        grouped.setdefault((row.run, row.dataset), []).append(row)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for (run, dataset), items in sorted(grouped.items()):
            inventory = inventories[(dataset, run)]
            doc_pairs_2xx: set[tuple[str, str]] = set()
            hit_pairs_2xx: set[tuple[str, str]] = set()
            doc_pairs_4xx: set[tuple[str, str]] = set()
            hit_pairs_4xx: set[tuple[str, str]] = set()
            observed_pairs_4xx: set[tuple[str, str]] = set()
            undocumented_pairs_4xx: set[tuple[str, str]] = set()
            doc_pairs_all: set[tuple[str, str]] = set()
            hit_pairs_all: set[tuple[str, str]] = set()

            for item in items:
                for code in item.doc_2xx:
                    doc_pairs_2xx.add((item.operation, code))
                    doc_pairs_all.add((item.operation, code))
                for code in item.hit_2xx:
                    hit_pairs_2xx.add((item.operation, code))
                    hit_pairs_all.add((item.operation, code))
                for code in item.doc_4xx:
                    doc_pairs_4xx.add((item.operation, code))
                    doc_pairs_all.add((item.operation, code))
                for code in item.hit_4xx:
                    hit_pairs_4xx.add((item.operation, code))
                    hit_pairs_all.add((item.operation, code))
                for code in item.observed_4xx_all:
                    observed_pairs_4xx.add((item.operation, code))
                for code in item.undocumented_4xx:
                    undocumented_pairs_4xx.add((item.operation, code))

            writer.writerow(
                {
                    "run": run,
                    "dataset": dataset,
                    "doc_2xx_count": len(doc_pairs_2xx),
                    "hit_2xx_count": len(hit_pairs_2xx),
                    "coverage_2xx": format_ratio(len(hit_pairs_2xx), len(doc_pairs_2xx)),
                    "doc_4xx_count": len(doc_pairs_4xx),
                    "hit_4xx_count": len(hit_pairs_4xx),
                    "observed_4xx_count": len(observed_pairs_4xx),
                    "undocumented_4xx_count": len(undocumented_pairs_4xx),
                    "coverage_4xx": format_ratio(len(hit_pairs_4xx), len(doc_pairs_4xx)),
                    "doc_all_count": len(doc_pairs_all),
                    "hit_all_count": len(hit_pairs_all),
                    "coverage_all": format_ratio(len(hit_pairs_all), len(doc_pairs_all)),
                    "operation_coverage": format_optional_float(
                        inventory.metrics.successful_percentage
                    ),
                    "report_schema": inventory.metrics.report_schema,
                    "run_status": inventory.metrics.run_status,
                    "snapshot_reason": inventory.metrics.snapshot_reason or "",
                    "started_at": inventory.started_at.isoformat() if inventory.started_at else "",
                    "updated_at": inventory.updated_at.isoformat() if inventory.updated_at else "",
                    "completed_at": (
                        inventory.completed_at.isoformat() if inventory.completed_at else ""
                    ),
                    "has_report": str(inventory.has_report).lower(),
                    "has_operation_status_codes": str(inventory.has_operation_status_codes).lower(),
                    "has_qtables": str(inventory.has_qtables).lower(),
                    "has_trace": str(inventory.has_trace).lower(),
                    "total_requests_sent": inventory.metrics.total_requests_sent,
                    "input_tokens": inventory.metrics.input_tokens,
                    "output_tokens": inventory.metrics.output_tokens,
                    "total_tokens": inventory.metrics.total_tokens,
                    "event_sequence": inventory.metrics.trace_event_count or 0,
                    "http_attempt_count": inventory.metrics.http_attempt_count or 0,
                    "logical_count": inventory.metrics.logical_count or 0,
                    "llm_call_count": inventory.metrics.llm_call_count or 0,
                    "checkpoint_count": inventory.metrics.checkpoint_count or 0,
                    "status_code_distribution_json": inventory.status_code_distribution_json,
                }
            )


def write_run_inventory(path: Path, inventories: list[RunInventory]) -> None:
    fieldnames = [
        "dataset",
        "run",
        "report_schema",
        "run_status",
        "snapshot_reason",
        "started_at",
        "updated_at",
        "completed_at",
        "has_report",
        "has_operation_status_codes",
        "has_qtables",
        "has_trace",
        "total_requests_sent",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "event_sequence",
        "attempt_sequence",
        "logical_sequence",
        "llm_call_sequence",
        "checkpoint_count",
        "status_code_distribution_json",
        "operation_coverage",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for inventory in sorted(inventories, key=lambda item: (item.dataset, item.run)):
            writer.writerow(
                {
                    "dataset": inventory.dataset,
                    "run": inventory.run,
                    "report_schema": inventory.metrics.report_schema,
                    "run_status": inventory.metrics.run_status,
                    "snapshot_reason": inventory.metrics.snapshot_reason or "",
                    "started_at": inventory.started_at.isoformat() if inventory.started_at else "",
                    "updated_at": inventory.updated_at.isoformat() if inventory.updated_at else "",
                    "completed_at": (
                        inventory.completed_at.isoformat() if inventory.completed_at else ""
                    ),
                    "has_report": str(inventory.has_report).lower(),
                    "has_operation_status_codes": str(inventory.has_operation_status_codes).lower(),
                    "has_qtables": str(inventory.has_qtables).lower(),
                    "has_trace": str(inventory.has_trace).lower(),
                    "total_requests_sent": inventory.metrics.total_requests_sent,
                    "input_tokens": inventory.metrics.input_tokens,
                    "output_tokens": inventory.metrics.output_tokens,
                    "total_tokens": inventory.metrics.total_tokens,
                    "event_sequence": inventory.metrics.trace_event_count or 0,
                    "attempt_sequence": inventory.metrics.http_attempt_count or 0,
                    "logical_sequence": inventory.metrics.logical_count or 0,
                    "llm_call_sequence": inventory.metrics.llm_call_count or 0,
                    "checkpoint_count": inventory.metrics.checkpoint_count or 0,
                    "status_code_distribution_json": inventory.status_code_distribution_json,
                    "operation_coverage": format_optional_float(
                        inventory.metrics.successful_percentage
                    ),
                }
            )


def write_unmatched_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["run", "dataset", "kind", "operation"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    summary_path = Path(args.summary_csv)
    data_root = Path(args.data_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    docs_by_dataset = load_summary(summary_path)
    all_operation_results: list[CoverageResult] = []
    unmatched_rows: list[dict[str, str]] = []
    inventories: list[RunInventory] = []
    inventory_index: dict[tuple[str, str], RunInventory] = {}

    for dataset_dir in iter_valid_dataset_dirs(data_root):
        dataset = dataset_dir.name
        docs = docs_by_dataset.get(dataset)
        for run_dir in iter_run_dirs(dataset_dir):
            inventory = build_run_inventory(run_dir)
            if inventory is None:
                continue
            inventories.append(inventory)
            inventory_index[(inventory.dataset, inventory.run)] = inventory

            if docs is None:
                if inventory.has_operation_status_codes:
                    unmatched_rows.append(
                        {
                            "run": inventory.run,
                            "dataset": inventory.dataset,
                            "kind": "run_dataset_not_in_summary",
                            "operation": "",
                        }
                    )
                continue

            if not inventory.has_operation_status_codes:
                unmatched_rows.append(
                    {
                        "run": inventory.run,
                        "dataset": inventory.dataset,
                        "kind": "run_missing_operation_status_codes",
                        "operation": "",
                    }
                )

            operation_results, unmatched_doc_ops = compute_operation_results(
                inventory,
                docs,
            )
            all_operation_results.extend(operation_results)

            matched_observed = {
                item.matched_observed_operation
                for item in operation_results
                if item.matched_observed_operation
            }
            extra_observed = sorted(
                set((inventory.operation_status_codes or {}).keys()) - matched_observed
            )
            for operation in unmatched_doc_ops:
                unmatched_rows.append(
                    {
                        "run": inventory.run,
                        "dataset": inventory.dataset,
                        "kind": "documented_operation_not_found_in_observed",
                        "operation": operation,
                    }
                )
            for operation in extra_observed:
                unmatched_rows.append(
                    {
                        "run": inventory.run,
                        "dataset": inventory.dataset,
                        "kind": "observed_operation_not_found_in_documented",
                        "operation": operation,
                    }
                )

    operation_report = out_dir / "operation_coverage.csv"
    dataset_report = out_dir / "dataset_coverage.csv"
    unmatched_report = out_dir / "operation_matching_issues.csv"
    run_inventory_report = out_dir / "run_inventory.csv"

    write_operation_report(operation_report, all_operation_results)
    write_dataset_report(dataset_report, all_operation_results, inventory_index)
    write_unmatched_report(unmatched_report, unmatched_rows)
    write_run_inventory(run_inventory_report, inventories)

    print(f"[OK] Wrote operation report: {operation_report}")
    print(f"[OK] Wrote dataset report:   {dataset_report}")
    print(f"[OK] Wrote matching issues:  {unmatched_report}")
    print(f"[OK] Wrote run inventory:    {run_inventory_report}")
    print(f"[OK] Total operation rows:   {len(all_operation_results)}")
    print(f"[OK] Total matching issues:  {len(unmatched_rows)}")
    print(f"[OK] Total runs scanned:     {len(inventories)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
