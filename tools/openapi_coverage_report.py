from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


@dataclass(frozen=True)
class OperationDoc:
    dataset: str
    operation: str
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
    doc_2xx: frozenset[str]
    hit_2xx: frozenset[str]
    doc_4xx: frozenset[str]
    hit_4xx: frozenset[str]
    observed_4xx_all: frozenset[str]
    undocumented_4xx: frozenset[str]

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
        help="CSV created from OpenAPI specs (dataset, operation, 2xx_code, 4xx_code).",
    )
    parser.add_argument(
        "--data-root",
        default="data",
        help="Root directory containing data/{dataset}/{run_id}/operation_status_codes.json",
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
    return f"{hit / doc:.4f}"


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
    observed_values = {x for x in observed_values if x is not None}

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
    typed = sorted(str(v) for v in values if v is not None and (v // 100) == wanted_class)
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
    with summary_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dataset = row["dataset"].strip()
            operation = row["operation"].strip()
            op_doc = OperationDoc(
                dataset=dataset,
                operation=operation,
                doc_2xx=parse_codes(row.get("2xx_code", "")),
                doc_4xx=parse_codes(row.get("4xx_code", "")),
            )
            by_dataset.setdefault(dataset, []).append(op_doc)
    return by_dataset


def load_observed(path: Path) -> dict[str, dict[str, int]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}

    parsed: dict[str, dict[str, int]] = {}
    for op_name, statuses in data.items():
        if not isinstance(op_name, str) or not isinstance(statuses, dict):
            continue
        parsed_statuses: dict[str, int] = {}
        for code, count in statuses.items():
            if isinstance(code, str) and isinstance(count, int):
                parsed_statuses[code] = count
        parsed[op_name] = parsed_statuses
    return parsed


def build_operation_index(observed: dict[str, dict[str, int]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for op in observed:
        index.setdefault(normalize_operation_name(op), op)
    return index


def compute_operation_results(
    run_name: str,
    dataset: str,
    docs: list[OperationDoc],
    observed: dict[str, dict[str, int]],
) -> tuple[list[CoverageResult], list[str]]:
    results: list[CoverageResult] = []
    unmatched_doc_ops: list[str] = []

    observed_index = build_operation_index(observed)

    for doc in docs:
        direct = observed.get(doc.operation)
        matched_name: str | None = doc.operation if direct is not None else None

        if direct is None:
            normalized = normalize_operation_name(doc.operation)
            matched_name = observed_index.get(normalized)
            direct = observed.get(matched_name) if matched_name else None

        observed_counts = direct or {}
        if matched_name is None:
            unmatched_doc_ops.append(doc.operation)

        hit_2xx = hit_documented_codes(doc.doc_2xx, observed_counts, wanted_class=2)
        hit_4xx = hit_documented_codes(doc.doc_4xx, observed_counts, wanted_class=4)
        observed_4xx_all = observed_codes_by_class(observed_counts, wanted_class=4)
        undocumented_4xx = frozenset(
            code
            for code in observed_4xx_all
            if not is_observed_code_documented(code, doc.doc_4xx)
        )

        results.append(
            CoverageResult(
                run=run_name,
                dataset=dataset,
                operation=doc.operation,
                matched_observed_operation=matched_name,
                doc_2xx=doc.doc_2xx,
                hit_2xx=hit_2xx,
                doc_4xx=doc.doc_4xx,
                hit_4xx=hit_4xx,
                observed_4xx_all=observed_4xx_all,
                undocumented_4xx=undocumented_4xx,
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
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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
                }
            )


def write_dataset_report(path: Path, results: list[CoverageResult]) -> None:
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
    ]

    grouped: dict[tuple[str, str], list[CoverageResult]] = {}
    for row in results:
        grouped.setdefault((row.run, row.dataset), []).append(row)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for (run, dataset), items in sorted(grouped.items()):
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
                    "coverage_2xx": format_ratio(
                        len(hit_pairs_2xx), len(doc_pairs_2xx)
                    ),
                    "doc_4xx_count": len(doc_pairs_4xx),
                    "hit_4xx_count": len(hit_pairs_4xx),
                    "observed_4xx_count": len(observed_pairs_4xx),
                    "undocumented_4xx_count": len(undocumented_pairs_4xx),
                    "coverage_4xx": format_ratio(
                        len(hit_pairs_4xx), len(doc_pairs_4xx)
                    ),
                    "doc_all_count": len(doc_pairs_all),
                    "hit_all_count": len(hit_pairs_all),
                    "coverage_all": format_ratio(
                        len(hit_pairs_all), len(doc_pairs_all)
                    ),
                }
            )


def write_unmatched_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["run", "dataset", "kind", "operation"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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

    for dataset_dir in sorted(p for p in data_root.iterdir() if p.is_dir()):
        dataset = dataset_dir.name
        run_dirs = sorted(p for p in dataset_dir.iterdir() if p.is_dir())
        if dataset not in docs_by_dataset:
            for run_dir in run_dirs:
                if (run_dir / "operation_status_codes.json").exists():
                    unmatched_rows.append(
                        {
                            "run": run_dir.name,
                            "dataset": dataset,
                            "kind": "run_dataset_not_in_summary",
                            "operation": "",
                        }
                    )
            continue

        docs = docs_by_dataset[dataset]
        for run_dir in run_dirs:
            run_name = run_dir.name
            observed_path = run_dir / "operation_status_codes.json"
            if not observed_path.exists():
                continue

            observed = load_observed(observed_path)
            operation_results, unmatched_doc_ops = compute_operation_results(
                run_name=run_name, dataset=dataset, docs=docs, observed=observed
            )
            all_operation_results.extend(operation_results)

            matched_observed = {
                item.matched_observed_operation
                for item in operation_results
                if item.matched_observed_operation
            }
            extra_observed = sorted(set(observed.keys()) - matched_observed)
            for op in unmatched_doc_ops:
                unmatched_rows.append(
                    {
                        "run": run_name,
                        "dataset": dataset,
                        "kind": "documented_operation_not_found_in_observed",
                        "operation": op,
                    }
                )
            for op in extra_observed:
                unmatched_rows.append(
                    {
                        "run": run_name,
                        "dataset": dataset,
                        "kind": "observed_operation_not_found_in_documented",
                        "operation": op,
                    }
                )

    operation_report = out_dir / "operation_coverage.csv"
    dataset_report = out_dir / "dataset_coverage.csv"
    unmatched_report = out_dir / "operation_matching_issues.csv"

    write_operation_report(operation_report, all_operation_results)
    write_dataset_report(dataset_report, all_operation_results)
    write_unmatched_report(unmatched_report, unmatched_rows)

    print(f"[OK] Wrote operation report: {operation_report}")
    print(f"[OK] Wrote dataset report:   {dataset_report}")
    print(f"[OK] Wrote matching issues:  {unmatched_report}")
    print(f"[OK] Total operation rows:   {len(all_operation_results)}")
    print(f"[OK] Total matching issues:  {len(unmatched_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
