"""Managed HTTP transport for pooled requests.Session usage."""

from __future__ import annotations

import atexit
import threading
from typing import Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from autoresttest.config import get_config


_SESSION_LOCAL = threading.local()
_SESSION_REGISTRY: Dict[int, requests.Session] = {}
_SESSION_REGISTRY_LOCK = threading.Lock()


def _build_adapter() -> HTTPAdapter:
    http_config = get_config().http
    return HTTPAdapter(
        pool_connections=http_config.pool_connections,
        pool_maxsize=http_config.pool_maxsize,
        max_retries=Retry(total=0, connect=0, read=0, redirect=0, status=0),
        pool_block=True,
    )


def _build_session() -> requests.Session:
    session = requests.Session()
    adapter = _build_adapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_managed_session() -> requests.Session:
    """Return the lazily initialized session for the current thread."""

    thread_id = threading.get_ident()
    session = getattr(_SESSION_LOCAL, "session", None)
    with _SESSION_REGISTRY_LOCK:
        registered_session = _SESSION_REGISTRY.get(thread_id)
        if session is None or registered_session is not session:
            session = _build_session()
            _SESSION_LOCAL.session = session
            _SESSION_REGISTRY[thread_id] = session
    return session


def close_all_sessions() -> None:
    """Close every managed session and clear transport state."""

    with _SESSION_REGISTRY_LOCK:
        sessions = list(
            {id(session): session for session in _SESSION_REGISTRY.values()}.values()
        )
        _SESSION_REGISTRY.clear()

    for session in sessions:
        session.close()

    if hasattr(_SESSION_LOCAL, "session"):
        delattr(_SESSION_LOCAL, "session")


def reset_transport_state_for_testing() -> None:
    """Reset managed session state for tests."""

    close_all_sessions()


atexit.register(close_all_sessions)


__all__ = [
    "close_all_sessions",
    "get_managed_session",
    "reset_transport_state_for_testing",
]
