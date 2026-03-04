from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

from autoresttest.config import get_config
from autoresttest.models import to_dict_helper
from autoresttest.run_artifacts import (
    atomic_write_json,
    build_report_title,
    ensure_output_dir,
    ensure_runtime_dir,
    ensure_trace_dir,
    write_standard_output_snapshot,
)


_ACTIVE_RUN_RECORDER: contextvars.ContextVar[Optional["RunRecorder"]] = (
    contextvars.ContextVar("autoresttest_active_run_recorder", default=None)
)
_LOGICAL_REQUEST_CONTEXT: contextvars.ContextVar[Optional[dict[str, Any]]] = (
    contextvars.ContextVar("autoresttest_logical_request_context", default=None)
)

_SENSITIVE_FIELD_PATTERNS = (
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "password",
)


@dataclass(frozen=True)
class LogicalRequestHandle:
    logical_request_id: int
    context_token: Any


@dataclass(frozen=True)
class RunRecorderPaths:
    output_dir: Path
    trace_dir: Path
    runtime_dir: Path
    http_attempts_path: Path
    logical_requests_path: Path
    llm_calls_path: Path
    run_manifest_path: Path
    latest_manifest_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return slug or "run"


def _looks_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(pattern in lowered for pattern in _SENSITIVE_FIELD_PATTERNS)


def _redact_value(value: Any) -> str:
    if value is None:
        return "<redacted>"
    value_text = str(value)
    if len(value_text) <= 8:
        return "<redacted>"
    return f"{value_text[:4]}...<redacted>"


def _sanitize_mapping(data: Any) -> Any:
    converted = to_dict_helper(data)
    if isinstance(converted, dict):
        sanitized: dict[str, Any] = {}
        for key, value in converted.items():
            key_text = str(key)
            if _looks_sensitive(key_text):
                sanitized[key_text] = _redact_value(value)
            else:
                sanitized[key_text] = _sanitize_mapping(value)
        return sanitized
    if isinstance(converted, list):
        return [_sanitize_mapping(item) for item in converted]
    return converted


def _serialize_preview(value: Any, max_chars: int) -> dict[str, Any] | None:
    if value is None:
        return None

    converted = _sanitize_mapping(value)
    try:
        serialized = json.dumps(converted, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        serialized = str(converted)

    preview = serialized[:max_chars]
    return {
        "preview": preview,
        "truncated": len(serialized) > max_chars,
        "length": len(serialized),
        "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    }


def _extract_body_payload(body: dict[str, Any] | None) -> dict[str, Any] | None:
    if not body:
        return None
    mime_type, payload = next(iter(body.items()))
    return {
        "mime_type": mime_type,
        "payload": payload,
    }


def _summarize_request_body(body: dict[str, Any] | None, max_chars: int) -> dict[str, Any] | None:
    if not body:
        return None

    extracted = _extract_body_payload(body)
    if extracted is None:
        return None

    return {
        "mime_type": extracted["mime_type"],
        "payload": _serialize_preview(extracted["payload"], max_chars),
    }


def _response_preview(response: requests.Response, max_chars: int) -> dict[str, Any] | None:
    if not response.content:
        return None

    content_type = response.headers.get("Content-Type", "")
    is_text_like = any(
        token in content_type.lower()
        for token in ("json", "text", "xml", "html", "javascript")
    )

    if not is_text_like:
        raw_bytes = response.content
        preview = raw_bytes[: min(max_chars, len(raw_bytes))].hex()
        return {
            "encoding": "hex",
            "preview": preview,
            "truncated": len(raw_bytes) > max_chars,
            "length": len(raw_bytes),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        }

    text = response.text
    preview = text[:max_chars]
    return {
        "encoding": "text",
        "preview": preview,
        "truncated": len(text) > max_chars,
        "length": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest(),
    }


def set_active_run_recorder(recorder: Optional["RunRecorder"]) -> Any:
    return _ACTIVE_RUN_RECORDER.set(recorder)


def reset_active_run_recorder(token: Any) -> None:
    _ACTIVE_RUN_RECORDER.reset(token)


def get_active_run_recorder() -> Optional["RunRecorder"]:
    return _ACTIVE_RUN_RECORDER.get()


class RunRecorder:
    def __init__(self, spec_name: str, report_title: str) -> None:
        observability_config = get_config().observability

        self.enabled = observability_config.enabled
        self.spec_name = spec_name
        self.report_title = report_title
        self.snapshot_interval_seconds = max(
            1, observability_config.snapshot_interval_seconds
        )
        self.snapshot_interval_requests = max(
            1, observability_config.snapshot_interval_requests
        )
        self.max_preview_chars = max(256, observability_config.max_preview_chars)
        self.trace_flush_on_write = observability_config.trace_flush_on_write
        self._lock = threading.RLock()
        self._closed = False
        self._status = "running"
        self._started_at = _utc_now_iso()
        self._run_id = (
            f"{_slugify(spec_name)}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-"
            f"{os.getpid()}"
        )
        self._attempt_sequence = 0
        self._logical_sequence = 0
        self._event_sequence = 0
        self._checkpoint_count = 0
        self._aggregate_dirty = False
        self._last_snapshot_at = self._started_at
        self._last_snapshot_reason = "initialized"
        self._last_snapshot_monotonic = time.monotonic()
        self._last_snapshot_attempt_sequence = 0
        self._active_logical_requests: dict[int, dict[str, Any]] = {}

        output_dir = ensure_output_dir(spec_name)
        trace_dir = ensure_trace_dir(spec_name)
        runtime_dir = ensure_runtime_dir(spec_name)

        self.paths = RunRecorderPaths(
            output_dir=output_dir,
            trace_dir=trace_dir,
            runtime_dir=runtime_dir,
            http_attempts_path=trace_dir / f"{self._run_id}.http_attempts.jsonl",
            logical_requests_path=trace_dir / f"{self._run_id}.logical_requests.jsonl",
            llm_calls_path=trace_dir / f"{self._run_id}.llm_calls.jsonl",
            run_manifest_path=runtime_dir / f"{self._run_id}.manifest.json",
            latest_manifest_path=runtime_dir / "latest_run_manifest.json",
        )

        self._http_attempts_handle = None
        self._logical_requests_handle = None
        self._llm_calls_handle = None
        self._llm_call_sequence = 0

        if self.enabled:
            self._http_attempts_handle = self.paths.http_attempts_path.open(
                "a",
                encoding="utf-8",
                buffering=1,
            )
            self._logical_requests_handle = self.paths.logical_requests_path.open(
                "a",
                encoding="utf-8",
                buffering=1,
            )
            self._llm_calls_handle = self.paths.llm_calls_path.open(
                "a",
                encoding="utf-8",
                buffering=1,
            )
            self._write_manifest()

    @classmethod
    def from_api_title(cls, spec_name: str, api_title: str | None) -> "RunRecorder":
        return cls(spec_name=spec_name, report_title=build_report_title(spec_name, api_title))

    @property
    def run_id(self) -> str:
        return self._run_id

    def begin_logical_request(self, metadata: dict[str, Any]) -> Optional[LogicalRequestHandle]:
        if not self.enabled or self._closed:
            return None

        with self._lock:
            self._logical_sequence += 1
            logical_request_id = self._logical_sequence
            started_monotonic = time.perf_counter()
            started_at = _utc_now_iso()
            normalized_metadata = _sanitize_mapping(metadata)
            self._active_logical_requests[logical_request_id] = {
                "metadata": normalized_metadata,
                "started_monotonic": started_monotonic,
                "started_at": started_at,
                "attempt_count": 0,
                "first_attempt_sequence_id": None,
                "last_attempt_sequence_id": None,
                "llm_call_count": 0,
                "first_llm_call_id": None,
                "last_llm_call_id": None,
            }

            bound_context = {
                "run_id": self._run_id,
                "logical_request_id": logical_request_id,
                "operation_id": normalized_metadata.get("operation_id"),
                "data_source": normalized_metadata.get("data_source"),
                "dependency_type": normalized_metadata.get("dependency_type"),
                "mutated": normalized_metadata.get("mutated"),
                "phase": normalized_metadata.get("phase"),
                "component": normalized_metadata.get("component"),
                "event_type": normalized_metadata.get("event_type"),
            }
            context_token = _LOGICAL_REQUEST_CONTEXT.set(bound_context)
            return LogicalRequestHandle(
                logical_request_id=logical_request_id,
                context_token=context_token,
            )

    def complete_logical_request(
        self,
        handle: Optional[LogicalRequestHandle],
        response: requests.Response | None,
        *,
        good_reward: int | None = None,
        bad_reward: int | None = None,
        skipped_reason: str | None = None,
        state_changed: bool = False,
        request_failed: bool = False,
        result_metadata: dict[str, Any] | None = None,
        response_summary: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled or self._closed or handle is None:
            return

        with self._lock:
            try:
                active_request = self._active_logical_requests.pop(
                    handle.logical_request_id, None
                )
                if active_request is None:
                    return

                duration_ms = round(
                    (time.perf_counter() - active_request["started_monotonic"]) * 1000,
                    3,
                )
                self._event_sequence += 1

                event = {
                    "schema_version": 1,
                    "trace_kind": "logical_request",
                    "event_sequence_id": self._event_sequence,
                    "run_id": self._run_id,
                    "logical_request_id": handle.logical_request_id,
                    "started_at": active_request["started_at"],
                    "completed_at": _utc_now_iso(),
                    "duration_ms": duration_ms,
                    "request_failed": request_failed,
                    "state_changed": state_changed,
                    "skipped_reason": skipped_reason,
                    "good_response_reward": good_reward,
                    "bad_response_reward": bad_reward,
                    "attempt_count": active_request["attempt_count"],
                    "first_attempt_sequence_id": active_request[
                        "first_attempt_sequence_id"
                    ],
                    "last_attempt_sequence_id": active_request["last_attempt_sequence_id"],
                    "llm_call_count": active_request["llm_call_count"],
                    "first_llm_call_id": active_request["first_llm_call_id"],
                    "last_llm_call_id": active_request["last_llm_call_id"],
                    "response": (
                        _sanitize_mapping(response_summary)
                        if response_summary is not None
                        else (
                            {
                                "status_code": response.status_code,
                                "ok": response.ok,
                            }
                            if response is not None
                            else None
                        )
                    ),
                }
                event.update(active_request["metadata"])
                if result_metadata:
                    event.update(_sanitize_mapping(result_metadata))
                self._append_jsonl(self._logical_requests_handle, event)
            finally:
                _LOGICAL_REQUEST_CONTEXT.reset(handle.context_token)

    def record_http_attempt(
        self,
        *,
        method: str,
        full_url: str,
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
        headers: dict[str, Any] | None,
        cookies: dict[str, Any] | None,
        response: requests.Response | None,
        duration_ms: float,
        attempt_index: int,
        max_retries: int,
        will_retry: bool,
        retry_delay_s: float | None = None,
        transport_error: BaseException | None = None,
    ) -> None:
        if not self.enabled or self._closed:
            return

        with self._lock:
            self._event_sequence += 1
            self._attempt_sequence += 1
            event_sequence_id = self._event_sequence
            attempt_sequence_id = self._attempt_sequence
            logical_context = _LOGICAL_REQUEST_CONTEXT.get()

            if logical_context is not None:
                logical_request_id = logical_context["logical_request_id"]
                active_request = self._active_logical_requests.get(logical_request_id)
                if active_request is not None:
                    active_request["attempt_count"] += 1
                    if active_request["first_attempt_sequence_id"] is None:
                        active_request["first_attempt_sequence_id"] = attempt_sequence_id
                    active_request["last_attempt_sequence_id"] = attempt_sequence_id

            event = {
                "schema_version": 1,
                "trace_kind": "http_attempt",
                "event_sequence_id": event_sequence_id,
                "run_id": self._run_id,
                "attempt_sequence_id": attempt_sequence_id,
                "recorded_at": _utc_now_iso(),
                "phase": (
                    logical_context.get("phase") if logical_context is not None else None
                ),
                "component": (
                    logical_context.get("component")
                    if logical_context is not None
                    else None
                ),
                "logical_event_type": (
                    logical_context.get("event_type")
                    if logical_context is not None
                    else None
                ),
                "logical_request_id": (
                    logical_context.get("logical_request_id")
                    if logical_context is not None
                    else None
                ),
                "logical_operation_id": (
                    logical_context.get("operation_id")
                    if logical_context is not None
                    else None
                ),
                "logical_data_source": (
                    logical_context.get("data_source")
                    if logical_context is not None
                    else None
                ),
                "logical_dependency_type": (
                    logical_context.get("dependency_type")
                    if logical_context is not None
                    else None
                ),
                "logical_mutated": (
                    logical_context.get("mutated")
                    if logical_context is not None
                    else None
                ),
                "http_method": method.upper(),
                "url": full_url,
                "query_params": _sanitize_mapping(params or {}),
                "request_headers": _sanitize_mapping(headers or {}),
                "request_cookies": _sanitize_mapping(cookies or {}),
                "request_body": _summarize_request_body(body, self.max_preview_chars),
                "attempt_index": attempt_index,
                "max_retries": max_retries,
                "will_retry": will_retry,
                "retry_delay_s": retry_delay_s,
                "duration_ms": round(duration_ms, 3),
                "transport_error": None,
                "response": None,
            }

            if transport_error is not None:
                event["transport_error"] = {
                    "type": type(transport_error).__name__,
                    "message": str(transport_error),
                }

            if response is not None:
                event["response"] = {
                    "status_code": response.status_code,
                    "ok": response.ok,
                    "headers": _sanitize_mapping(dict(response.headers)),
                    "body": _response_preview(response, self.max_preview_chars),
                }

            self._append_jsonl(self._http_attempts_handle, event)

    def record_llm_call(
        self,
        *,
        model: str,
        cache_hit: bool,
        json_mode: bool,
        temperature: float,
        max_tokens: int,
        prompt: str,
        system_prompt: str,
        response_text: str,
        duration_ms: float,
        attempt_count: int,
        input_tokens: int,
        output_tokens: int,
        trace_metadata: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        if not self.enabled or self._closed:
            return

        with self._lock:
            self._event_sequence += 1
            self._llm_call_sequence += 1
            event_sequence_id = self._event_sequence
            llm_call_id = self._llm_call_sequence
            logical_context = _LOGICAL_REQUEST_CONTEXT.get()

            if logical_context is not None:
                logical_request_id = logical_context["logical_request_id"]
                active_request = self._active_logical_requests.get(logical_request_id)
                if active_request is not None:
                    active_request["llm_call_count"] += 1
                    if active_request["first_llm_call_id"] is None:
                        active_request["first_llm_call_id"] = llm_call_id
                    active_request["last_llm_call_id"] = llm_call_id

            event = {
                "schema_version": 1,
                "trace_kind": "llm_call",
                "event_sequence_id": event_sequence_id,
                "run_id": self._run_id,
                "llm_call_id": llm_call_id,
                "recorded_at": _utc_now_iso(),
                "phase": (
                    logical_context.get("phase") if logical_context is not None else None
                ),
                "component": (
                    logical_context.get("component")
                    if logical_context is not None
                    else None
                ),
                "logical_event_type": (
                    logical_context.get("event_type")
                    if logical_context is not None
                    else None
                ),
                "logical_request_id": (
                    logical_context.get("logical_request_id")
                    if logical_context is not None
                    else None
                ),
                "logical_operation_id": (
                    logical_context.get("operation_id")
                    if logical_context is not None
                    else None
                ),
                "llm": {
                    "model": model,
                    "cache_hit": cache_hit,
                    "json_mode": json_mode,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "attempt_count": attempt_count,
                    "duration_ms": round(duration_ms, 3),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "result_empty": not bool(response_text),
                },
                "prompt": _serialize_preview(prompt, self.max_preview_chars),
                "system_prompt": _serialize_preview(
                    system_prompt,
                    min(self.max_preview_chars, 1000),
                ),
                "response": _serialize_preview(response_text, self.max_preview_chars),
                "error": (
                    {
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                    if error is not None
                    else None
                ),
            }

            if trace_metadata:
                event["metadata"] = _sanitize_mapping(trace_metadata)

            self._append_jsonl(self._llm_calls_handle, event)

    def mark_aggregate_dirty(self) -> None:
        if not self.enabled or self._closed:
            return
        with self._lock:
            self._aggregate_dirty = True

    def maybe_checkpoint(
        self,
        q_learning: Any,
        *,
        force: bool = False,
        reason: str = "interval",
    ) -> bool:
        if not self.enabled or self._closed:
            return False

        with self._lock:
            attempts_since_snapshot = (
                self._attempt_sequence - self._last_snapshot_attempt_sequence
            )
            interval_elapsed = (
                time.monotonic() - self._last_snapshot_monotonic
                >= self.snapshot_interval_seconds
            )
            request_threshold_reached = (
                attempts_since_snapshot >= self.snapshot_interval_requests
            )

            if not force:
                if not self._aggregate_dirty:
                    return False
                if not interval_elapsed and not request_threshold_reached:
                    return False

            try:
                write_standard_output_snapshot(self.spec_name, q_learning, self.report_title)
                self._checkpoint_count += 1
                self._aggregate_dirty = False
                self._last_snapshot_monotonic = time.monotonic()
                self._last_snapshot_attempt_sequence = self._attempt_sequence
                self._last_snapshot_at = _utc_now_iso()
                self._last_snapshot_reason = reason
                self._flush_trace_handles(sync_to_disk=True)
                self._write_manifest()
                return True
            except Exception as exc:  # pragma: no cover - best-effort observability
                print(f"Checkpoint save failed: {exc}")
                return False

    def set_status(self, status: str) -> None:
        if not self.enabled or self._closed:
            return
        with self._lock:
            self._status = status
            self._write_manifest()

    def close(self, status: str | None = None) -> None:
        if self._closed:
            return

        if not self.enabled:
            self._closed = True
            return

        with self._lock:
            if status is not None:
                self._status = status

            self._flush_trace_handles(sync_to_disk=True)
            self._write_manifest(completed_at=_utc_now_iso())

            self._http_attempts_handle.close()
            self._logical_requests_handle.close()
            self._llm_calls_handle.close()
            self._closed = True

    def _append_jsonl(self, handle: Any, payload: dict[str, Any]) -> None:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        if self.trace_flush_on_write:
            handle.flush()

    def _flush_trace_handles(self, *, sync_to_disk: bool) -> None:
        if (
            self._http_attempts_handle is None
            or self._logical_requests_handle is None
            or self._llm_calls_handle is None
        ):
            return
        self._http_attempts_handle.flush()
        self._logical_requests_handle.flush()
        self._llm_calls_handle.flush()
        if sync_to_disk:
            os.fsync(self._http_attempts_handle.fileno())
            os.fsync(self._logical_requests_handle.fileno())
            os.fsync(self._llm_calls_handle.fileno())

    def _manifest_payload(self, completed_at: str | None = None) -> dict[str, Any]:
        return {
            "run_id": self._run_id,
            "dataset_name": self.spec_name,
            "report_title": self.report_title,
            "status": self._status,
            "started_at": self._started_at,
            "updated_at": _utc_now_iso(),
            "completed_at": completed_at,
            "paths": {
                "output_dir": str(self.paths.output_dir),
                "http_attempts_trace": str(self.paths.http_attempts_path),
                "logical_requests_trace": str(self.paths.logical_requests_path),
                "llm_calls_trace": str(self.paths.llm_calls_path),
                "latest_snapshot_report": str(self.paths.output_dir / "report.json"),
            },
            "counters": {
                "event_sequence": self._event_sequence,
                "attempt_sequence": self._attempt_sequence,
                "logical_sequence": self._logical_sequence,
                "llm_call_sequence": self._llm_call_sequence,
                "checkpoint_count": self._checkpoint_count,
                "last_snapshot_at": self._last_snapshot_at,
                "last_snapshot_reason": self._last_snapshot_reason,
                "attempts_since_snapshot": (
                    self._attempt_sequence - self._last_snapshot_attempt_sequence
                ),
            },
        }

    def _write_manifest(self, completed_at: str | None = None) -> None:
        payload = self._manifest_payload(completed_at=completed_at)
        for manifest_path in (
            self.paths.run_manifest_path,
            self.paths.latest_manifest_path,
        ):
            try:
                atomic_write_json(manifest_path, payload)
            except PermissionError as exc:  # pragma: no cover - Windows file lock race
                print(f"Manifest write skipped for {manifest_path.name}: {exc}")
