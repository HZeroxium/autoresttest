from __future__ import annotations

from fastapi import Request

from .config import AppContext


def get_context(request: Request) -> AppContext:
    return request.app.state.inspector_context
