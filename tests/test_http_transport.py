from __future__ import annotations

from types import SimpleNamespace

import pytest
import requests

import autoresttest.http_transport as http_transport
import autoresttest.utils.utils as utils_module


def _make_config(
    *,
    connect_timeout_seconds: float = 3.0,
    read_timeout_seconds: float = 30.0,
    pool_connections: int = 10,
    pool_maxsize: int = 64,
    transport_retry_attempts: int = 1,
    transport_retry_backoff_seconds: float = 0.25,
):
    return SimpleNamespace(
        http=SimpleNamespace(
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            transport_retry_attempts=transport_retry_attempts,
            transport_retry_backoff_seconds=transport_retry_backoff_seconds,
        )
    )


def _make_response(status_code: int = 200) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = b"{}"
    response.headers = {}
    response.url = "http://example.test"
    return response


@pytest.fixture(autouse=True)
def _reset_transport_state():
    http_transport.reset_transport_state_for_testing()
    yield
    http_transport.reset_transport_state_for_testing()


def test_get_managed_session_reuses_same_session_within_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http_transport, "get_config", lambda: _make_config())

    session1 = http_transport.get_managed_session()
    session2 = http_transport.get_managed_session()

    assert session1 is session2


def test_get_managed_session_mounts_adapters_with_expected_pool_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        http_transport,
        "get_config",
        lambda: _make_config(pool_connections=12, pool_maxsize=48),
    )

    session = http_transport.get_managed_session()
    http_adapter = session.adapters["http://"]
    https_adapter = session.adapters["https://"]

    assert http_adapter._pool_connections == 12
    assert http_adapter._pool_maxsize == 48
    assert http_adapter._pool_block is True
    assert http_adapter.max_retries.total == 0
    assert https_adapter._pool_connections == 12
    assert https_adapter._pool_maxsize == 48
    assert https_adapter._pool_block is True
    assert https_adapter.max_retries.total == 0


def test_dispatch_request_passes_configured_timeouts_to_managed_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeSession:
        def request(self, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["timeout"] = kwargs.get("timeout")
            return _make_response()

    monkeypatch.setattr(
        utils_module,
        "get_config",
        lambda: _make_config(connect_timeout_seconds=1.5, read_timeout_seconds=9.0),
    )
    monkeypatch.setattr(utils_module, "get_managed_session", lambda: _FakeSession())

    response = utils_module.dispatch_request(
        method_name="get",
        full_url="http://example.test/items",
        params={},
        body=None,
    )

    assert response is not None
    assert captured["method"] == "get"
    assert captured["url"] == "http://example.test/items"
    assert captured["timeout"] == (1.5, 9.0)


def test_dispatch_request_retries_safe_method_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []

    class _FakeSession:
        def request(self, method, url, **kwargs):
            attempts.append(method)
            if len(attempts) == 1:
                raise requests.exceptions.ConnectionError("boom")
            return _make_response()

    monkeypatch.setattr(utils_module, "get_config", lambda: _make_config())
    monkeypatch.setattr(utils_module, "get_managed_session", lambda: _FakeSession())
    monkeypatch.setattr(utils_module.time, "sleep", lambda _: None)

    response = utils_module.dispatch_request(
        method_name="get",
        full_url="http://example.test/items",
        params={},
        body=None,
    )

    assert response is not None
    assert len(attempts) == 2


def test_dispatch_request_does_not_retry_non_safe_method_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []

    class _FakeSession:
        def request(self, method, url, **kwargs):
            attempts.append(method)
            raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(utils_module, "get_config", lambda: _make_config())
    monkeypatch.setattr(utils_module, "get_managed_session", lambda: _FakeSession())
    monkeypatch.setattr(utils_module.time, "sleep", lambda _: None)

    with pytest.raises(requests.exceptions.ConnectionError):
        utils_module.dispatch_request(
            method_name="post",
            full_url="http://example.test/items",
            params={},
            body=None,
        )

    assert len(attempts) == 1


def test_close_all_sessions_closes_cached_session_and_allows_recreation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_sessions = []

    class _FakeSession:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    def _build_session():
        session = _FakeSession()
        created_sessions.append(session)
        return session

    monkeypatch.setattr(http_transport, "_build_session", _build_session)

    session1 = http_transport.get_managed_session()
    http_transport.close_all_sessions()
    session2 = http_transport.get_managed_session()

    assert session1.closed is True
    assert session2 is not session1
    assert len(created_sessions) == 2
