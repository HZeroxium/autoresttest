from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from .config import AppContext, InspectorSettings, build_context, get_settings
from .routers import artifacts, compare, datasets, graph, health, qtables, runs, traces
from .schemas import ApiError
from .static import serve_spa


def create_app(settings: InspectorSettings | None = None) -> FastAPI:
    context = build_context(settings)
    app = FastAPI(
        title="AutoRestTest Inspector",
        version="0.1.0",
        default_response_class=ORJSONResponse,
    )
    app.state.inspector_context = context
    _configure_middleware(app, context)
    _configure_routes(app)
    _configure_exception_handlers(app)
    return app


def _configure_middleware(app: FastAPI, context: AppContext) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(context.settings.allowed_origins),
        allow_methods=["GET"],
        allow_headers=["*"],
        allow_credentials=False,
    )


def _configure_routes(app: FastAPI) -> None:
    app.include_router(health.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")
    app.include_router(qtables.router, prefix="/api")
    app.include_router(traces.router, prefix="/api")
    app.include_router(artifacts.router, prefix="/api")
    app.include_router(compare.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def serve_root(request: Request) -> Any:
        context: AppContext = request.app.state.inspector_context
        return serve_spa(context.settings.static_root, "")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str, request: Request) -> Any:
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail={"code": "api_not_found", "message": "API route not found."})
        context: AppContext = request.app.state.inspector_context
        return serve_spa(context.settings.static_root, full_path)


def _configure_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> ORJSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "code": "http_error",
            "message": str(exc.detail),
        }
        error = ApiError(
            code=str(detail.get("code", "http_error")),
            message=str(detail.get("message", "Request failed.")),
            details=detail.get("details"),
        )
        return ORJSONResponse(status_code=exc.status_code, content={"error": error.model_dump(mode="json", by_alias=True)})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> ORJSONResponse:
        error = ApiError(
            code="validation_error",
            message="Request validation failed.",
            details={"errors": exc.errors()},
        )
        return ORJSONResponse(status_code=422, content={"error": error.model_dump(mode="json", by_alias=True)})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> ORJSONResponse:
        error = ApiError(
            code="internal_error",
            message="An unexpected error occurred.",
            details={"type": type(exc).__name__, "message": str(exc)},
        )
        return ORJSONResponse(status_code=500, content={"error": error.model_dump(mode="json", by_alias=True)})


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "autoresttest.inspector_api.app:create_app",
        host=settings.host,
        port=settings.port,
        factory=True,
    )


def dev_main() -> None:
    settings = get_settings()
    uvicorn.run(
        "autoresttest.inspector_api.app:create_app",
        host=settings.host,
        port=settings.port,
        factory=True,
        reload=True,
    )
