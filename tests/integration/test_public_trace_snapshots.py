from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACE_DATA = ROOT / "apps" / "web" / "src" / "data" / "public-traces.json"


def test_public_trace_snapshots_cover_required_scenarios_without_private_content() -> None:
    payload = json.loads(TRACE_DATA.read_text(encoding="utf-8"))
    traces = {trace["slug"]: trace for trace in payload["traces"]}
    assert set(traces) == {
        "scam-injection-skip",
        "approved-critic-loop",
        "crash-resume-exactly-once",
    }

    scam = traces["scam-injection-skip"]
    assert scam["status"] == "skip"
    assert scam["metrics"]["marketplace_writes"] == 0
    assert scam["redacted_state"]["risk_report"]["ignored_instructions"]

    critic = traces["approved-critic-loop"]
    assert critic["metrics"]["critic_passes"] == 2
    assert critic["metrics"]["revisions"] == 1
    assert critic["metrics"]["marketplace_writes"] == 1
    assert [span["node"] for span in critic["spans"]].count("critic") == 2

    resumed = traces["crash-resume-exactly-once"]
    assert resumed["metrics"]["simulated_crashes"] == 1
    assert resumed["metrics"]["marketplace_writes"] == 1
    assert resumed["metrics"]["idempotency_receipts"] == 1
    assert {span["node"] for span in resumed["spans"]}.issuperset(
        {"process_failure", "checkpoint_restore", "submit"}
    )

    serialized = TRACE_DATA.read_text(encoding="utf-8").lower()
    assert "@" not in serialized
    assert "password" not in serialized
    assert "bearer" not in serialized
    assert "cover_letter" not in serialized
