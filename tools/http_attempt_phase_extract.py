from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACE_RELATIVE_PATH = Path("metadata") / "trace" / "http_attempts.jsonl"
PHASE_OUTPUT_FILES = {
    "value_agent_q_table_generation": "value_agent_q_table_generation.json",
    "marl_request_generation": "marl.json",
}


class HttpAttemptPhaseExtractError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract minimal HTTP attempt traces for value-agent bootstrap and "
            "MARL request-generation phases."
        )
    )
    parser.add_argument(
        "run_dir",
        help="Run directory like data/{datasetId}/{runId}.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for extracted phase JSON files. Defaults to the run directory.",
    )
    return parser.parse_args()


def path_text(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def normalize_status_code(raw_status_code: Any) -> int | None:
    if isinstance(raw_status_code, bool):
        return None
    if isinstance(raw_status_code, int):
        return raw_status_code
    if isinstance(raw_status_code, float) and raw_status_code.is_integer():
        return int(raw_status_code)
    if isinstance(raw_status_code, str) and raw_status_code.strip().isdigit():
        return int(raw_status_code.strip())
    return None


def normalize_operation_id(event: dict[str, Any]) -> str | None:
    for key in ("logical_operation_id", "operation_id"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def normalize_url(event: dict[str, Any]) -> str | None:
    value = event.get("url")
    if isinstance(value, str) and value.strip():
        return value
    return None


def extract_status_code(event: dict[str, Any]) -> int | None:
    response_payload = event.get("response")
    if isinstance(response_payload, dict):
        normalized = normalize_status_code(response_payload.get("status_code"))
        if normalized is not None:
            return normalized
    return normalize_status_code(event.get("status_code"))


def extract_minimal_attempt(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation_id": normalize_operation_id(event),
        "url": normalize_url(event),
        "status_code": extract_status_code(event),
    }


def collect_phase_attempts(trace_path: Path) -> dict[str, list[dict[str, Any]]]:
    collected = {phase: [] for phase in PHASE_OUTPUT_FILES}
    with trace_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HttpAttemptPhaseExtractError(
                    f"Invalid JSON at {trace_path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(payload, dict):
                raise HttpAttemptPhaseExtractError(
                    f"Expected JSON object at {trace_path}:{line_number}, got {type(payload).__name__}."
                )

            trace_kind = payload.get("trace_kind")
            if trace_kind is not None and trace_kind != "http_attempt":
                continue

            phase = payload.get("phase")
            if phase not in collected:
                continue

            collected[phase].append(extract_minimal_attempt(payload))
    return collected


def write_outputs(output_dir: Path, phase_attempts: dict[str, list[dict[str, Any]]]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    for phase, filename in PHASE_OUTPUT_FILES.items():
        output_path = output_dir / filename
        output_path.write_text(
            json.dumps(phase_attempts[phase], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written_paths.append(output_path)
    return written_paths


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)
    output_dir = Path(args.output_dir) if args.output_dir else run_dir

    if not run_dir.exists() or not run_dir.is_dir():
        raise HttpAttemptPhaseExtractError(f"Run directory does not exist: {run_dir}")

    trace_path = run_dir / TRACE_RELATIVE_PATH
    if not trace_path.exists() or not trace_path.is_file():
        raise HttpAttemptPhaseExtractError(f"Missing http_attempts trace: {trace_path}")

    phase_attempts = collect_phase_attempts(trace_path)
    written_paths = write_outputs(output_dir, phase_attempts)

    for phase, output_path in zip(PHASE_OUTPUT_FILES, written_paths):
        print(
            f"[OK] Wrote {len(phase_attempts[phase])} {phase} rows: {path_text(output_path)}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HttpAttemptPhaseExtractError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
