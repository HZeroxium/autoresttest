from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from pathlib import Path
from typing import Iterable

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize OpenAPI response status codes by dataset and operation "
            "into a CSV file."
        )
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input OpenAPI files or glob patterns (e.g. datasets/*.json).",
    )
    parser.add_argument(
        "--output",
        default="openapi_status_summary.csv",
        help="Output CSV path. Default: openapi_status_summary.csv",
    )
    return parser.parse_args()


def expand_input_patterns(patterns: Iterable[str]) -> list[Path]:
    expanded: list[Path] = []
    for pattern in patterns:
        matches = [Path(p) for p in glob.glob(pattern)]
        if matches:
            expanded.extend(matches)
        else:
            expanded.append(Path(pattern))

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in expanded:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_paths.append(path)
    return unique_paths


def load_openapi_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise ValueError(f"Unsupported file format: {path}")

    with path.open("r", encoding="utf-8") as f:
        if suffix == ".json":
            return json.load(f)
        try:
            import yaml  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise ValueError(
                "PyYAML is required to read .yaml/.yml files. Install `pyyaml`."
            ) from exc
        data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML OpenAPI content: {path}")
        return data


def classify_status_code(code: str) -> str | None:
    normalized = code.strip().upper()

    if normalized.endswith("XX") and len(normalized) == 3 and normalized[0].isdigit():
        prefix = int(normalized[0])
        if prefix == 2:
            return "2xx"
        if prefix == 4:
            return "4xx"
        return None

    if normalized.isdigit():
        value = int(normalized)
        if 200 <= value <= 299:
            return "2xx"
        if 400 <= value <= 499:
            return "4xx"

    return None


def infer_default_4xx_codes(response_data: dict) -> set[str]:
    description = str(response_data.get("description", "")).strip().lower()
    if not description:
        return set()

    phrase_to_code: list[tuple[str, str]] = [
        ("bad request", "400"),
        ("bad input", "400"),
        ("invalid", "400"),
        ("malformed", "400"),
        ("missing", "400"),
        ("unauthorized", "401"),
        ("forbidden", "403"),
        ("not found", "404"),
        ("method not allowed", "405"),
        ("not acceptable", "406"),
        ("conflict", "409"),
        ("gone", "410"),
        ("uri too long", "414"),
        ("request-uri too large", "414"),
        ("unsupported media type", "415"),
        ("unprocessable", "422"),
        ("too many requests", "429"),
        ("rate limit", "429"),
    ]
    inferred = {
        code for phrase, code in phrase_to_code if re.search(rf"\b{re.escape(phrase)}\b", description)
    }
    return inferred


def sort_codes(codes: set[str]) -> list[str]:
    def key(code: str) -> tuple[int, int | str]:
        if code.isdigit():
            return (0, int(code))
        return (1, code)

    return sorted(codes, key=key)


def operation_name(method: str, path: str, operation_data: dict) -> str:
    op_id = operation_data.get("operationId")
    if isinstance(op_id, str) and op_id.strip():
        return op_id
    return f"{method.upper()} {path}"


def extract_rows(spec: dict, dataset_name: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return rows

    for endpoint, methods in paths.items():
        if not isinstance(methods, dict):
            continue

        for method, operation_data in methods.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation_data, dict):
                continue

            responses = operation_data.get("responses")
            if not isinstance(responses, dict):
                responses = {}

            codes_2xx: set[str] = set()
            codes_4xx: set[str] = set()

            for raw_code, response_data in responses.items():
                status_code = str(raw_code)
                category = classify_status_code(status_code)
                if category == "2xx":
                    codes_2xx.add(status_code.upper())
                elif category == "4xx":
                    codes_4xx.add(status_code.upper())
                elif status_code.strip().lower() == "default" and isinstance(response_data, dict):
                    codes_4xx.update(infer_default_4xx_codes(response_data))

            rows.append(
                {
                    "dataset": dataset_name,
                    "operation": operation_name(method, endpoint, operation_data),
                    "2xx_code": "|".join(sort_codes(codes_2xx)),
                    "4xx_code": "|".join(sort_codes(codes_4xx)),
                }
            )

    return rows


def main() -> int:
    args = parse_args()
    input_paths = expand_input_patterns(args.inputs)

    all_rows: list[dict[str, str]] = []
    for input_path in input_paths:
        if not input_path.exists():
            print(f"[WARN] File not found: {input_path}")
            continue
        if not input_path.is_file():
            print(f"[WARN] Not a file: {input_path}")
            continue

        try:
            spec = load_openapi_file(input_path)
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Skip {input_path}: {exc}")
            continue

        dataset = input_path.stem
        rows = extract_rows(spec, dataset_name=dataset)
        if not rows:
            print(f"[WARN] No operations found in: {input_path}")
        all_rows.extend(rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["dataset", "operation", "2xx_code", "4xx_code"]
        )
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"[OK] Wrote {len(all_rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
