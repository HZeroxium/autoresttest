from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT))

from openapi_export_helper import OpenApiExportError, export_openapi_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the JHipster Sample App OpenAPI document.")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "datasets" / "jhipster-sample-app.json"),
        help="Destination JSON file.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    try:
        exported = export_openapi_document(
            port=args.port,
            username=args.username,
            password=args.password,
            output_path=output_path.resolve(),
            timeout_seconds=args.timeout_seconds,
        )
    except OpenApiExportError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Exported OpenAPI document to {exported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
