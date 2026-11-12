from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from data.pipelines.build_agent_design_dataset import (
    category_for,
    iter_jobs,
    round_robin_sample,
)

ROOT = Path(__file__).resolve().parents[2]
GENERATOR_VERSION = "gigbid-simulator-v1"


def _stable_fraction(value: str) -> float:
    digest = hashlib.sha256(value.encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _safe_float(value: object, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def _client(job: dict[str, Any]) -> dict[str, object]:
    raw_history = job.get("client_history")
    history: dict[str, Any] = raw_history if isinstance(raw_history, dict) else {}
    skills = [str(skill) for skill in job.get("required_skills", [])]
    raw_budget = job.get("budget")
    budget: dict[str, Any] = raw_budget if isinstance(raw_budget, dict) else {}
    client_id = str(job["client_id"])
    variation = _stable_fraction(client_id)
    return {
        "client_id": client_id,
        "payment_verified": bool(history.get("payment_verified", False)),
        "average_rating": history.get("average_rating"),
        "completed_projects": int(history.get("completed_projects") or 0),
        "total_spent_usd": _safe_float(history.get("total_spent_usd"), 0.0),
        "country": str(history.get("country") or "Unknown"),
        "hidden_preferences": {
            "must_have_skills": skills[:2],
            "budget_ceiling": _safe_float(budget.get("max"), 0.0),
            "dislikes_generic_openings": variation >= 0.35,
            "reply_threshold": round(0.48 + variation * 0.12, 3),
            "hire_threshold": round(0.70 + variation * 0.10, 3),
        },
        "data_origin": "synthetic",
        "generator_version": GENERATOR_VERSION,
    }


def _gold(job: dict[str, Any]) -> dict[str, object]:
    raw_history = job.get("client_history")
    history: dict[str, Any] = raw_history if isinstance(raw_history, dict) else {}
    raw_budget = job.get("budget")
    budget: dict[str, Any] = raw_budget if isinstance(raw_budget, dict) else {}
    scam = bool(job.get("security_signals"))
    maximum = _safe_float(budget.get("max"), 0.0)
    minimum = _safe_float(budget.get("min"), 0.0)
    bid = not scam and bool(history.get("payment_verified")) and maximum > 0
    return {
        "bid_action": "bid" if bid else "skip",
        "scam": scam,
        "fair_price_band": {"min": minimum, "max": maximum, "currency": "USD"},
        "label_origin": "synthetic_rule_based",
        "generator_version": GENERATOR_VERSION,
    }


def build(*, count: int = 300) -> dict[str, object]:
    source = ROOT / "data/processed/kaggle/jobs_dev.jsonl"
    if not source.exists():
        raise FileNotFoundError("Run make data-prepare before building the simulator fixture")
    rows = iter_jobs(source)
    flagged = [row for row in rows if row.get("security_signals")]
    ordinary = [row for row in rows if not row.get("security_signals")]
    flagged_count = min(60, count // 5, len(flagged))
    selected = [
        *round_robin_sample(flagged, flagged_count),
        *round_robin_sample(ordinary, count - flagged_count),
    ]
    jobs: list[dict[str, object]] = []
    clients: dict[str, dict[str, object]] = {}
    labels: dict[str, dict[str, object]] = {}
    for row in selected:
        job = {
            key: value
            for key, value in row.items()
            if key not in {"client_history", "security_signals"}
        }
        job["category"] = category_for(row)
        job["security_signals"] = list(row.get("security_signals") or [])
        jobs.append(job)
        clients[str(row["client_id"])] = _client(row)
        labels[str(row["job_id"])] = _gold(row)
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "generator_version": GENERATOR_VERSION,
            "public_job_source": "ahmedmyalo/upwork-freelance-jobs-60k",
            "public_job_source_version": 5,
            "public_job_license": "Apache-2.0",
            "public_job_origin": "real_public_dataset",
            "client_preferences_origin": "synthetic",
            "outcome_labels_origin": "synthetic_rule_based",
            "sampling": (
                f"{flagged_count} security-flagged and {count - flagged_count} ordinary "
                "development jobs"
            ),
            "limitations": (
                "Client preferences and outcomes are deterministic synthetic labels, not real "
                "marketplace behaviour."
            ),
        },
        "jobs": jobs,
        "clients": clients,
        "gold_labels": labels,
    }


def main() -> None:
    destination = ROOT / "evals/datasets/simulator_fixture.json"
    destination.write_text(json.dumps(build(), indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
