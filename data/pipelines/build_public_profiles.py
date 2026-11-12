from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.pricing_priors import classify_category

ROOT = Path(__file__).resolve().parents[2]


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summary(values: list[float]) -> dict[str, int | float]:
    return {
        "count": len(values),
        "p25": round(percentile(values, 0.25), 2),
        "median": round(percentile(values, 0.50), 2),
        "p75": round(percentile(values, 0.75), 2),
    }


def iter_jsonl(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def build_profiles() -> tuple[dict[str, Any], dict[str, Any]]:
    processed = ROOT / "data/processed/kaggle"
    contract_path = processed / "pricing_history.jsonl"
    job_paths = {
        "development_2023": processed / "jobs_dev.jsonl",
        "training_2023": processed / "jobs_train.jsonl",
        "temporal_holdout_2024": processed / "jobs_temporal_holdout.jsonl",
    }
    required = [contract_path, *job_paths.values()]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing normalized public data. Run make data first: " + ", ".join(missing)
        )

    contract_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    contract_rejections: Counter[str] = Counter()
    contract_rows = 0
    for row in iter_jsonl(contract_path):
        contract_rows += 1
        category = classify_category(str(row.get("job_title", "")))
        model = str(row.get("pricing_model", ""))
        if model == "hourly":
            value = row.get("hourly_rate_usd")
            if not isinstance(value, int | float) or not 1 <= float(value) <= 500:
                contract_rejections["hourly_outside_1_to_500_usd"] += 1
                continue
        else:
            model = "fixed_or_milestone"
            value = row.get("total_paid_usd")
            if not isinstance(value, int | float) or not 1 <= float(value) <= 100_000:
                contract_rejections["fixed_outside_1_to_100000_usd"] += 1
                continue
        contract_values[(category, model)].append(float(value))
        contract_values[("all", model)].append(float(value))

    priors: dict[str, dict[str, dict[str, int | float]]] = defaultdict(dict)
    for (category, model), values in sorted(contract_values.items()):
        priors[category][model] = summary(values)

    split_profiles: dict[str, Any] = {}
    all_job_budgets: dict[str, list[float]] = defaultdict(list)
    for split, path in job_paths.items():
        categories: Counter[str] = Counter()
        pricing_models: Counter[str] = Counter()
        budget_values: dict[str, list[float]] = defaultdict(list)
        injection_flagged = 0
        payment_verified = 0
        rows = 0
        for row in iter_jsonl(path):
            rows += 1
            category = classify_category(
                " ".join(
                    [
                        str(row.get("title", "")),
                        str(row.get("description", "")),
                        " ".join(map(str, row.get("required_skills", []))),
                    ]
                )
            )
            categories[category] += 1
            model = str(row.get("pricing_model") or "unknown")
            pricing_models[model] += 1
            budget = row.get("budget") or {}
            if isinstance(budget, dict):
                maximum = budget.get("max")
                if isinstance(maximum, int | float) and 1 <= float(maximum) <= 100_000:
                    budget_values[model].append(float(maximum))
                    all_job_budgets[model].append(float(maximum))
            injection_flagged += int(bool(row.get("security_signals")))
            history = row.get("client_history") or {}
            payment_verified += int(
                isinstance(history, dict) and bool(history.get("payment_verified"))
            )
        split_profiles[split] = {
            "rows": rows,
            "category_counts": dict(categories.most_common()),
            "pricing_model_counts": dict(pricing_models.most_common()),
            "budget_max_usd": {
                model: summary(values) for model, values in sorted(budget_values.items())
            },
            "injection_signal_rate": round(injection_flagged / max(1, rows), 6),
            "payment_verified_rate": round(payment_verified / max(1, rows), 6),
        }

    generated_at = datetime.now(UTC).isoformat()
    pricing_artifact = {
        "metadata": {
            "generated_at": generated_at,
            "data_origin": "real_public_dataset",
            "source": "asaniczka/freelance-contracts-dataset-1-3-million-entries",
            "source_version": 1,
            "license": "ODC-By-1.0",
            "rows_scanned": contract_rows,
            "filtering": {
                "hourly_rate_usd": "1 <= value <= 500",
                "fixed_total_paid_usd": "1 <= value <= 100000",
                "rejected": dict(contract_rejections),
            },
            "warning": (
                "Descriptive observational priors only; not causal pricing guidance or outcomes."
            ),
        },
        "category_method": "deterministic title keyword rules in build_public_profiles.py",
        "priors": dict(priors),
    }
    public_profile = {
        "metadata": {
            "generated_at": generated_at,
            "data_origin": "real_public_dataset",
            "sources": [
                "ahmedmyalo/upwork-freelance-jobs-60k:v5",
                "asaniczka/upwork-job-postings-dataset-2024-50k-records:v1",
                "asaniczka/freelance-contracts-dataset-1-3-million-entries:v1",
            ],
            "reportable_scope": "descriptive profile; no reply, hire, or causal labels",
        },
        "job_splits": split_profiles,
        "combined_job_budget_max_usd": {
            model: summary(values) for model, values in sorted(all_job_budgets.items())
        },
        "contract_pricing": pricing_artifact,
    }
    return pricing_artifact, public_profile


def main() -> None:
    pricing_artifact, public_profile = build_profiles()
    pricing_path = ROOT / "data/derived/pricing_priors.json"
    result_path = ROOT / "evals/results/public_data_profile.json"
    pricing_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    pricing_path.write_text(json.dumps(pricing_artifact, indent=2), encoding="utf-8")
    result_path.write_text(json.dumps(public_profile, indent=2), encoding="utf-8")
    print(pricing_path)
    print(result_path)


if __name__ == "__main__":
    main()
