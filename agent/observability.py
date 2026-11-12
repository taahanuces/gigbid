from __future__ import annotations

import json
import os
import re
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import quote
from uuid import uuid4

from prometheus_client import Counter, Histogram

from agent.security import redact_pii

TRACE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_trace_id: ContextVar[str | None] = ContextVar("gigbid_trace_id", default=None)

API_REQUESTS = Counter(
    "gigbid_api_requests_total",
    "API requests by method, route and status",
    ("method", "route", "status"),
)
API_LATENCY = Histogram(
    "gigbid_api_request_duration_seconds",
    "API request duration by method and route",
    ("method", "route"),
)
GRAPH_RUNS = Counter(
    "gigbid_graph_runs_total",
    "Graph runs by terminal or interrupt status",
    ("status",),
)
GRAPH_LATENCY = Histogram(
    "gigbid_graph_run_duration_seconds",
    "Graph invocation duration",
)


def normalize_trace_id(candidate: str | None) -> str:
    if candidate and TRACE_PATTERN.fullmatch(candidate):
        return candidate
    return uuid4().hex


def set_trace_id(trace_id: str) -> Token[str | None]:
    return _trace_id.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    _trace_id.reset(token)


def current_trace_id() -> str:
    return _trace_id.get() or uuid4().hex


def trace_url_for(trace_id: str | None) -> str | None:
    template = os.getenv("TRACE_VIEWER_URL_TEMPLATE", "").strip()
    if trace_id and template:
        return template.format(trace_id=quote(trace_id, safe=""))
    base_url = os.getenv("TRACE_VIEWER_BASE_URL", "").strip().rstrip("/")
    if not trace_id or not base_url:
        return None
    return f"{base_url}/trace/{quote(trace_id, safe='')}"


def record_graph_run(*, status: str, duration_seconds: float) -> None:
    GRAPH_RUNS.labels(status=status).inc()
    GRAPH_LATENCY.observe(duration_seconds)


class JsonTraceRecorder:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = str(path or os.getenv("TRACE_LOG_PATH", "")).strip()
        self.path = Path(configured) if configured else None

    def record_request(
        self,
        *,
        trace_id: str,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "trace_id": trace_id,
            "span": "http.request",
            "method": method,
            "route": route,
            "status_code": status_code,
            "duration_ms": round(duration_seconds * 1_000, 3),
        }
        serialized = redact_pii(json.dumps(event, sort_keys=True))
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(serialized + "\n")


class Timer:
    def __init__(self) -> None:
        self.started = perf_counter()

    @property
    def elapsed(self) -> float:
        return perf_counter() - self.started
