from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse


def serve_spa(static_root: Path, path: str) -> FileResponse | JSONResponse:
    if not static_root.exists():
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "frontend_not_built",
                    "message": "Frontend assets are not built. Run 'pnpm --dir apps/autoresttest-inspector/web build' first.",
                }
            },
        )

    if path and path != "/":
        candidate = static_root / path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)

    index_path = static_root / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend entrypoint not found.")
    return FileResponse(index_path)
