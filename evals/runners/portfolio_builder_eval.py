from __future__ import annotations

import argparse
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.nodes.portfolio_builder import build_case_study_candidate

ROOT = Path(__file__).resolve().parents[2]


def _fixtures() -> list[dict[str, Any]]:
    technologies = [
        ("python-fastapi", ["Python", "FastAPI", "Postgres"], ["app.py", "db.py"]),
        ("next-dashboard", ["TypeScript", "React", "Next.js"], ["page.tsx"]),
        ("celery-worker", ["Python", "Celery", "Redis"], ["tasks.py"]),
        ("ml-pipeline", ["Python", "Pandas", "scikit-learn"], ["train.py"]),
        ("docker-api", ["Python", "FastAPI", "Docker"], ["Dockerfile", "main.py"]),
        ("node-service", ["TypeScript", "Node.js", "Postgres"], ["server.ts"]),
    ]
    rows: list[dict[str, Any]] = []
    for index in range(12):
        name, expected, paths = technologies[index % len(technologies)]
        claim = "\nReduced processing time by 42% for 10,000 users." if index % 2 == 0 else ""
        readme = (
            f"# {name.replace('-', ' ').title()}\n"
            f"A repository using {', '.join(expected)}.{claim}"
        )
        manifest = {
            path: f"Implementation for {name} with {', '.join(expected)}" for path in paths
        }
        rows.append(
            {
                "repository": f"synthetic/{name}-{index}",
                "readme": readme,
                "code_manifest": manifest,
                "gold_technologies": expected,
                "has_unsupported_outcome_claim": index % 2 == 0,
            }
        )
    return rows


def run() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for fixture in _fixtures():
        candidate = build_case_study_candidate(
            repository=str(fixture["repository"]),
            readme=str(fixture["readme"]),
            code_manifest=dict(fixture["code_manifest"]),
        )
        expected = set(map(str, fixture["gold_technologies"]))
        predicted = set(candidate.verified_technologies)
        true_positive = len(expected.intersection(predicted))
        precision = true_positive / max(1, len(predicted))
        recall = true_positive / max(1, len(expected))
        claim_detected = bool(candidate.unsupported_claims)
        rows.append(
            {
                "repository": fixture["repository"],
                "technology_precision": precision,
                "technology_recall": recall,
                "expected_claim_flag": fixture["has_unsupported_outcome_claim"],
                "claim_flag_detected": claim_detected,
                "evidence_paths": len(candidate.evidence_paths),
                "status": candidate.status,
            }
        )
    positives = [row for row in rows if row["expected_claim_flag"]]
    negatives = [row for row in rows if not row["expected_claim_flag"]]
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_origin": "authored_synthetic_repository_snapshots",
            "repositories": len(rows),
            "live_github_validation": False,
        },
        "summary": {
            "technology_precision": statistics.mean(row["technology_precision"] for row in rows),
            "technology_recall": statistics.mean(row["technology_recall"] for row in rows),
            "unsupported_claim_recall": sum(row["claim_flag_detected"] for row in positives)
            / len(positives),
            "unsupported_claim_false_positive_rate": sum(
                row["claim_flag_detected"] for row in negatives
            )
            / len(negatives),
            "human_approval_required_rate": sum(
                row["status"] == "pending_human_approval" for row in rows
            )
            / len(rows),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evals/results/portfolio_builder.json")
    args = parser.parse_args()
    destination = ROOT / args.output
    destination.write_text(json.dumps(run(), indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
