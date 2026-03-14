from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class OpenApiExportError(RuntimeError):
    pass


def build_base_url(port: int) -> str:
    return f"http://localhost:{port}"


def authenticate(base_url: str, username: str, password: str, timeout_seconds: int) -> str:
    payload = {
        "username": username,
        "password": password,
        "rememberMe": False,
    }
    response = request_json(
        f"{base_url}/api/authenticate",
        method="POST",
        payload=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout_seconds=timeout_seconds,
    )
    body = response["body"]
    if isinstance(body, dict):
        token = body.get("id_token")
        if isinstance(token, str) and token.strip():
            return token.strip()
    authorization_header = response["headers"].get("Authorization") or response["headers"].get("authorization")
    if authorization_header:
        bearer_prefix = "Bearer "
        if authorization_header.startswith(bearer_prefix):
            return authorization_header[len(bearer_prefix) :].strip()
        return authorization_header.strip()
    raise OpenApiExportError("Authentication succeeded but no JWT token was returned in the body or headers.")


def fetch_openapi_document(base_url: str, token: str, timeout_seconds: int) -> dict[str, Any]:
    response = request_json(
        f"{base_url}/v3/api-docs",
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout_seconds=timeout_seconds,
    )
    body = response["body"]
    if not isinstance(body, dict):
        raise OpenApiExportError("Expected /v3/api-docs to return a JSON object.")
    return body


def normalize_openapi_document(document: dict[str, Any], base_url: str) -> dict[str, Any]:
    normalized = json.loads(json.dumps(document))
    normalized["servers"] = [{"url": base_url}]
    return normalized


def export_openapi_document(port: int, username: str, password: str, output_path: Path, timeout_seconds: int) -> Path:
    base_url = build_base_url(port)
    token = authenticate(base_url, username, password, timeout_seconds)
    document = fetch_openapi_document(base_url, token, timeout_seconds)
    normalized = normalize_openapi_document(document, base_url)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return output_path


def request_json(
    url: str,
    *,
    method: str,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout_seconds: int,
) -> dict[str, Any]:
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")
            body = json.loads(raw_body) if raw_body else None
            return {
                "status": response.status,
                "headers": dict(response.headers.items()),
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        raise OpenApiExportError(
            f"HTTP {exc.code} calling {url}: {raw_body.strip() or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise OpenApiExportError(f"Could not reach {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise OpenApiExportError(f"Invalid JSON returned by {url}: {exc}") from exc
