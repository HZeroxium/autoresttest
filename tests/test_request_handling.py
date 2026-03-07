from __future__ import annotations

import json

from autoresttest.utils import dispatch_request, extract_structured_response_content


class _StubResponse:
    def __init__(self, content: bytes, content_type: str = "") -> None:
        self.content = content
        self.headers = {}
        if content_type:
            self.headers["Content-Type"] = content_type
        self.status_code = 200
        self.json_called = False

    def json(self):
        self.json_called = True
        return json.loads(self.content)


def test_dispatch_request_stringifies_header_values() -> None:
    captured: dict[str, object] = {}

    def fake_get(full_url, params=None, headers=None, cookies=None):
        captured["full_url"] = full_url
        captured["headers"] = headers
        return _StubResponse(b"")

    dispatch_request(
        select_method=fake_get,
        full_url="http://example.test/projects",
        params={},
        body=None,
        header={"PRIVATE_TOKEN": 10, "X-Feature-Enabled": True},
    )

    assert captured["full_url"] == "http://example.test/projects"
    assert captured["headers"] == {
        "PRIVATE_TOKEN": "10",
        "X-Feature-Enabled": "True",
    }


def test_dispatch_request_serializes_wildcard_scalar_body_as_json() -> None:
    captured: dict[str, object] = {}

    def fake_get(full_url, params=None, json=None, headers=None, cookies=None):
        captured["full_url"] = full_url
        captured["params"] = params
        captured["json"] = json
        captured["headers"] = headers
        return _StubResponse(b"")

    dispatch_request(
        select_method=fake_get,
        full_url="http://example.test/issues",
        params={"scope": "all"},
        body={"*/*": 1.3117421239508809},
        header=None,
    )

    assert captured["full_url"] == "http://example.test/issues"
    assert captured["params"] == {"scope": "all"}
    assert captured["json"] == 1.3117421239508809
    assert captured["headers"] == {"Content-Type": "application/json"}


def test_dispatch_request_serializes_unknown_scalar_body_to_transport_safe_data() -> None:
    captured: dict[str, object] = {}

    def fake_post(full_url, params=None, data=None, headers=None, cookies=None):
        captured["full_url"] = full_url
        captured["params"] = params
        captured["data"] = data
        captured["headers"] = headers
        return _StubResponse(b"")

    dispatch_request(
        select_method=fake_post,
        full_url="http://example.test/issues",
        params={},
        body={"application/octet-stream": True},
        header=None,
    )

    assert captured["full_url"] == "http://example.test/issues"
    assert captured["params"] == {}
    assert captured["data"] == "true"
    assert captured["headers"] == {"Content-Type": "application/octet-stream"}


def test_extract_structured_response_content_skips_binary_payloads() -> None:
    response = _StubResponse(
        b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03",
        "application/gzip",
    )

    content = extract_structured_response_content(response)

    assert content is None
    assert response.json_called is False


def test_extract_structured_response_content_skips_tar_like_snapshot_payloads() -> None:
    response = _StubResponse(
        b"HEAD\x00\x00\x00ref: refs/heads/main\n" + (b"\x00" * 64) + b"\xff",
        "application/octet-stream",
    )

    content = extract_structured_response_content(response)

    assert content is None
    assert response.json_called is False


def test_extract_structured_response_content_parses_json_payloads() -> None:
    response = _StubResponse(
        b'{"project":"demo","items":[1,2]}',
        "application/json",
    )

    content = extract_structured_response_content(response)

    assert content == {"project": "demo", "items": [1, 2]}
    assert response.json_called is True


def test_extract_structured_response_content_sniffs_json_without_content_type() -> None:
    response = _StubResponse(b'{"ok":true}')

    content = extract_structured_response_content(response)

    assert content == {"ok": True}
    assert response.json_called is True
