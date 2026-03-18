from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
XHTML_NS = {"x": "http://www.w3.org/1999/xhtml"}


class JaCoCoReportError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate overall JaCoCo coverage from results/*/*/jacoco/* reports."
    )
    parser.add_argument(
        "--results-root",
        default="results",
        help="Root directory containing results/<dataset>/<tool_name>/jacoco/<run_id>/.",
    )
    parser.add_argument(
        "--output",
        default="coverage_results/jacoco_overall_coverage.csv",
        help="Output CSV path.",
    )
    return parser.parse_args()


def parse_xhtml(path: Path) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise JaCoCoReportError(f"Failed to parse XHTML report {path}: {exc}") from exc


def collect_run_dirs(results_root: Path) -> list[Path]:
    return sorted(path for path in results_root.glob("*/*/jacoco/*") if path.is_dir())


def path_text(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def cell_texts(row: ET.Element) -> list[str]:
    return ["".join(cell.itertext()).strip() for cell in row.findall("x:td", XHTML_NS)]


def parse_int(text: str, *, context: str) -> int:
    normalized = text.replace(",", "").strip()
    if not normalized.isdigit():
        raise JaCoCoReportError(f"Expected integer for {context}, got {text!r}.")
    return int(normalized)


def parse_missed_of_total(text: str, *, context: str) -> tuple[int, int]:
    match = re.fullmatch(r"([0-9,]+)\s+of\s+([0-9,]+)", text.strip())
    if match is None:
        raise JaCoCoReportError(
            f"Expected 'missed of total' for {context}, got {text!r}."
        )
    return parse_int(match.group(1), context=context), parse_int(
        match.group(2), context=context
    )


def format_optional_pct(covered: int, total: int) -> str:
    if total == 0:
        return ""
    return f"{(covered / total) * 100:.4f}"


def expected_display_pct(covered: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{(covered * 100) // total}%"


def format_bool(value: bool) -> str:
    return str(value).lower()


def extract_total_cells(root: ET.Element, source: Path) -> list[str]:
    row = root.find('.//x:table[@id="coveragetable"]/x:tfoot/x:tr', XHTML_NS)
    if row is None:
        raise JaCoCoReportError(f"Could not find overall Total row in {source}.")
    cells = cell_texts(row)
    if len(cells) != 13 or cells[0] != "Total":
        raise JaCoCoReportError(f"Unexpected Total row layout in {source}: {cells!r}")
    return cells


def find_table_by_headers(
    root: ET.Element, headers: list[str], source: Path
) -> ET.Element:
    for table in root.findall(".//x:table", XHTML_NS):
        header_row = table.find("x:thead/x:tr", XHTML_NS)
        if header_row is None:
            continue
        current_headers = cell_texts(header_row)
        if current_headers == headers:
            return table
    raise JaCoCoReportError(f"Could not find table {headers!r} in {source}.")


def parse_session_metadata(root: ET.Element, source: Path) -> dict[str, object]:
    session_table = find_table_by_headers(
        root, ["Session", "Start Time", "Dump Time"], source
    )
    session_rows = session_table.findall("x:tbody/x:tr", XHTML_NS)
    if not session_rows:
        raise JaCoCoReportError(f"No session rows found in {source}.")

    class_table = find_table_by_headers(root, ["Class", "Id"], source)
    class_rows = class_table.findall("x:tbody/x:tr", XHTML_NS)

    session_names: list[str] = []
    session_starts: list[str] = []
    session_dumps: list[str] = []
    for row in session_rows:
        cells = cell_texts(row)
        if len(cells) != 3:
            raise JaCoCoReportError(
                f"Unexpected session row layout in {source}: {cells!r}"
            )
        session_names.append(cells[0])
        session_starts.append(cells[1])
        session_dumps.append(cells[2])

    return {
        "session_name": "|".join(session_names),
        "session_start_text": "|".join(session_starts),
        "session_dump_text": "|".join(session_dumps),
        "sessions_count": len(session_rows),
        "classes_considered_count": len(class_rows),
    }


def parse_jacoco_version(root: ET.Element, source: Path) -> str:
    footer = root.find('.//x:div[@class="footer"]', XHTML_NS)
    footer_text = "" if footer is None else "".join(footer.itertext()).strip()
    match = re.search(r"Created with\s+JaCoCo\s+([0-9][0-9A-Za-z.\-]*)", footer_text)
    if match is None:
        raise JaCoCoReportError(f"Could not find JaCoCo version in footer of {source}.")
    return match.group(1)


def add_metric_fields(
    row: dict[str, object],
    prefix: str,
    missed: int,
    total: int,
    *,
    display: str | None = None,
) -> None:
    covered = total - missed
    row[f"{prefix}_missed"] = missed
    row[f"{prefix}_covered"] = covered
    row[f"{prefix}_total"] = total
    row[f"{prefix}_coverage_pct"] = format_optional_pct(covered, total)
    if display is not None:
        row[f"{prefix}_coverage_display"] = display
        row[f"{prefix}_display_matches_counts"] = format_bool(
            display.lower() == expected_display_pct(covered, total)
        )


def parse_overall_metrics(total_cells: list[str]) -> dict[str, object]:
    row: dict[str, object] = {}

    instruction_missed, instruction_total = parse_missed_of_total(
        total_cells[1],
        context="Missed Instructions",
    )
    add_metric_fields(
        row,
        "instruction",
        instruction_missed,
        instruction_total,
        display=total_cells[2],
    )

    branch_missed, branch_total = parse_missed_of_total(
        total_cells[3],
        context="Missed Branches",
    )
    add_metric_fields(
        row,
        "branch",
        branch_missed,
        branch_total,
        display=total_cells[4],
    )

    complexity_missed = parse_int(total_cells[5], context="Missed Complexity")
    complexity_total = parse_int(total_cells[6], context="Total Complexity")
    add_metric_fields(row, "complexity", complexity_missed, complexity_total)

    line_missed = parse_int(total_cells[7], context="Missed Lines")
    line_total = parse_int(total_cells[8], context="Total Lines")
    add_metric_fields(row, "line", line_missed, line_total)

    method_missed = parse_int(total_cells[9], context="Missed Methods")
    method_total = parse_int(total_cells[10], context="Total Methods")
    add_metric_fields(row, "method", method_missed, method_total)

    class_missed = parse_int(total_cells[11], context="Missed Classes")
    class_total = parse_int(total_cells[12], context="Total Classes")
    add_metric_fields(row, "class", class_missed, class_total)

    return row


def build_row(results_root: Path, run_dir: Path) -> dict[str, object]:
    index_html = run_dir / "index.html"
    sessions_html = run_dir / "jacoco-sessions.html"
    if not index_html.exists():
        raise JaCoCoReportError(f"Missing JaCoCo index.html under {run_dir}.")
    if not sessions_html.exists():
        raise JaCoCoReportError(f"Missing JaCoCo jacoco-sessions.html under {run_dir}.")

    relative_parts = run_dir.relative_to(results_root).parts
    if len(relative_parts) != 4:
        raise JaCoCoReportError(f"Unexpected report directory layout: {run_dir}")
    dataset, tool_name, jacoco_literal, run_id = relative_parts
    if jacoco_literal != "jacoco":
        raise JaCoCoReportError(f"Unexpected report directory layout: {run_dir}")

    index_root = parse_xhtml(index_html)
    sessions_root = parse_xhtml(sessions_html)
    total_cells = extract_total_cells(index_root, index_html)

    row: dict[str, object] = {
        "dataset": dataset,
        "tool_name": tool_name,
        "run_id": run_id,
        "report_dir": path_text(run_dir),
        "index_html": path_text(index_html),
        "sessions_html": path_text(sessions_html),
        "report_title": index_root.findtext(
            ".//x:title", default="", namespaces=XHTML_NS
        ),
        "jacoco_version": parse_jacoco_version(index_root, index_html),
    }
    row.update(parse_session_metadata(sessions_root, sessions_html))
    row.update(parse_overall_metrics(total_cells))
    return row


def write_report(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dataset",
        "tool_name",
        "run_id",
        "report_dir",
        "index_html",
        "sessions_html",
        "report_title",
        "jacoco_version",
        "session_name",
        "session_start_text",
        "session_dump_text",
        "sessions_count",
        "classes_considered_count",
        "instruction_missed",
        "instruction_covered",
        "instruction_total",
        "instruction_coverage_pct",
        "instruction_coverage_display",
        "instruction_display_matches_counts",
        "branch_missed",
        "branch_covered",
        "branch_total",
        "branch_coverage_pct",
        "branch_coverage_display",
        "branch_display_matches_counts",
        "complexity_missed",
        "complexity_covered",
        "complexity_total",
        "complexity_coverage_pct",
        "line_missed",
        "line_covered",
        "line_total",
        "line_coverage_pct",
        "method_missed",
        "method_covered",
        "method_total",
        "method_coverage_pct",
        "class_missed",
        "class_covered",
        "class_total",
        "class_coverage_pct",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    results_root = Path(args.results_root)
    output_path = Path(args.output)

    run_dirs = collect_run_dirs(results_root)
    rows = [build_row(results_root, run_dir) for run_dir in run_dirs]
    rows.sort(
        key=lambda item: (
            str(item["dataset"]),
            str(item["tool_name"]),
            str(item["run_id"]),
        )
    )
    write_report(output_path, rows)

    instruction_mismatches = sum(
        1 for row in rows if row["instruction_display_matches_counts"] != "true"
    )
    branch_mismatches = sum(
        1 for row in rows if row["branch_display_matches_counts"] != "true"
    )

    print(f"[OK] Wrote JaCoCo overall report: {output_path}")
    print(f"[OK] Parsed report folders:      {len(rows)}")
    print(f"[OK] Instruction mismatches:    {instruction_mismatches}")
    print(f"[OK] Branch mismatches:         {branch_mismatches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
