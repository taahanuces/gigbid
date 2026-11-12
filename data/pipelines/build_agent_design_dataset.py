from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from agent.pricing_priors import classify_category

ROOT = Path(__file__).resolve().parents[2]


def iter_jobs(path: Path) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    jobs.append(cast(dict[str, Any], value))
    return jobs


def category_for(row: dict[str, Any]) -> str:
    return classify_category(
        " ".join(
            [
                str(row.get("title", "")),
                str(row.get("description", "")),
                " ".join(map(str, row.get("required_skills", []))),
            ]
        )
    )


def round_robin_sample(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=lambda item: str(item["job_id"])):
        groups[category_for(row)].append(row)
    selected: list[dict[str, Any]] = []
    categories = sorted(groups)
    while len(selected) < count and categories:
        remaining: list[str] = []
        for category in categories:
            if groups[category] and len(selected) < count:
                selected.append(groups[category].pop(0))
            if groups[category]:
                remaining.append(category)
        categories = remaining
    if len(selected) != count:
        raise ValueError(f"Needed {count} records, found {len(selected)}")
    return selected


def build() -> dict[str, object]:
    source = ROOT / "data/processed/kaggle/jobs_dev.jsonl"
    if not source.exists():
        raise FileNotFoundError("Run make data-prepare before building the agent design dataset")
    rows = iter_jobs(source)
    flagged = [row for row in rows if row.get("security_signals")]
    ordinary = [row for row in rows if not row.get("security_signals")]
    selected = [*round_robin_sample(flagged, 10), *round_robin_sample(ordinary, 40)]
    jobs = [
        {
            "job_id": str(row["job_id"]),
            "category": category_for(row),
            "expected_injection_signal": bool(row.get("security_signals")),
            "source_split": "development_2023",
        }
        for row in selected
    ]
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_origin": "real_public_dataset",
            "source": "ahmedmyalo/upwork-freelance-jobs-60k",
            "source_version": 5,
            "license": "Apache-2.0",
            "sampling": "10 injection-flagged plus 40 ordinary jobs, category round-robin",
            "warning": "No bid, reply, hire or proposal-quality ground truth is available.",
        },
        "jobs": jobs,
    }


def main() -> None:
    destination = ROOT / "evals/datasets/agent_design_jobs.json"
    destination.write_text(json.dumps(build(), indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
