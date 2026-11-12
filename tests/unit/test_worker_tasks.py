from __future__ import annotations

import json

from pytest import MonkeyPatch

from worker.tasks import dead_letter_payload, enqueue_job_once, record_dead_letter


class ScriptRedis:
    def __init__(self, result: int) -> None:
        self.result = result
        self.calls: list[tuple[str, int, tuple[object, ...]]] = []

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        self.calls.append((script, numkeys, keys_and_args))
        return self.result


class DeadLetterRedis:
    def __init__(self) -> None:
        self.pushed: list[tuple[str, str]] = []
        self.trimmed: list[tuple[str, int, int]] = []
        self.expirations: list[tuple[str, int]] = []

    def lpush(self, key: str, value: str) -> object:
        self.pushed.append((key, value))
        return 1

    def ltrim(self, key: str, start: int, end: int) -> object:
        self.trimmed.append((key, start, end))
        return True

    def expire(self, key: str, seconds: int) -> object:
        self.expirations.append((key, seconds))
        return True


def test_enqueue_job_once_uses_atomic_lock_and_publish_script() -> None:
    redis = ScriptRedis(1)
    assert enqueue_job_once(
        redis,
        tenant_id="tenant-1",
        job_id="job-1",
        trace_id="trace-worker-4016",
    )
    _, numkeys, arguments = redis.calls[0]
    assert numkeys == 1
    assert arguments[1:4] == ("processing", 1800, "gigbid:runs")
    event = json.loads(str(arguments[4]))
    assert event["trace_id"] == "trace-worker-4016"

    duplicate = ScriptRedis(0)
    assert not enqueue_job_once(duplicate, tenant_id="tenant-1", job_id="job-1")


def test_dead_letter_is_redacted_bounded_and_expiring(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DEAD_LETTER_MAX", "25")
    monkeypatch.setenv("DEAD_LETTER_RETENTION_SECONDS", "3600")
    redis = DeadLetterRedis()
    payload = dead_letter_payload(
        task_name="gigbid.analyze_job",
        task_id="task-1",
        exception=RuntimeError("failed for reviewer@example.com"),
        args=("reviewer@example.com",),
        kwargs={"phone": "+92 300 1234567"},
    )
    record_dead_letter(payload, redis)

    key, serialized = redis.pushed[0]
    assert key == "gigbid:dead-letter"
    assert "reviewer@example.com" not in serialized
    assert "+92 300 1234567" not in serialized
    assert "[REDACTED_EMAIL]" in serialized
    assert "[REDACTED_PHONE]" in serialized
    assert redis.trimmed == [(key, 0, 24)]
    assert redis.expirations == [(key, 3600)]
