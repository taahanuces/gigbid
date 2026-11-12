from __future__ import annotations

import json

from agent.observability import JsonTraceRecorder, normalize_trace_id, trace_url_for


def test_trace_id_validation_and_viewer_url(monkeypatch) -> None:
    assert normalize_trace_id("trace-valid-4016") == "trace-valid-4016"
    assert normalize_trace_id("contains spaces") != "contains spaces"

    monkeypatch.setenv("TRACE_VIEWER_BASE_URL", "https://traces.example.test/")
    assert trace_url_for("trace-valid-4016") == "https://traces.example.test/trace/trace-valid-4016"

    monkeypatch.setenv(
        "TRACE_VIEWER_URL_TEMPLATE",
        "https://phoenix.example.test/projects/gigbid?correlation={trace_id}",
    )
    assert trace_url_for("trace/valid 4016") == (
        "https://phoenix.example.test/projects/gigbid?correlation=trace%2Fvalid%204016"
    )


def test_json_trace_recorder_redacts_route_pii(tmp_path) -> None:
    trace_path = tmp_path / "traces" / "api.jsonl"
    recorder = JsonTraceRecorder(trace_path)
    recorder.record_request(
        trace_id="trace-redaction-4016",
        method="GET",
        route="/users/reviewer@example.com/01234567890",
        status_code=200,
        duration_seconds=0.0123,
    )

    raw = trace_path.read_text(encoding="utf-8")
    event = json.loads(raw)
    assert "reviewer@example.com" not in raw
    assert "01234567890" not in raw
    assert "[REDACTED_EMAIL]" in event["route"]
    assert "[REDACTED_PHONE]" in event["route"]
    assert event["trace_id"] == "trace-redaction-4016"
