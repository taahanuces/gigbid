from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import zipfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from agent.security import find_injected_instructions, redact_pii

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data/sources.yaml"
MAX_DESCRIPTION_CHARACTERS = 8_000
SPACE_PATTERN = re.compile(r"\s+")
MONEY_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def stable_id(prefix: str, *parts: object) -> str:
    joined = "\x1f".join(str(part).strip() for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def clean_text(value: object, *, limit: int = MAX_DESCRIPTION_CHARACTERS) -> str:
    decoded = html.unescape(str(value or "").replace("\ufeff", ""))
    redacted = redact_pii(decoded)
    return SPACE_PATTERN.sub(" ", redacted).strip()[:limit]


def parse_number(value: object) -> float | None:
    text = str(value or "").replace(",", "").strip()
    match = MONEY_PATTERN.search(text)
    return float(match.group(0)) if match else None


def parse_money(value: object) -> float | None:
    text = str(value or "").replace(",", "").strip().lower()
    number = parse_number(text)
    if number is None:
        return None
    if "k" in text:
        number *= 1_000
    elif "m" in text:
        number *= 1_000_000
    return max(0.0, number)


def parse_bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "verified"}


def budget_range(row: dict[str, str]) -> tuple[float | None, float | None, str]:
    payment_type = str(row.get("Payment_type") or "").lower()
    if "hour" in payment_type:
        low = parse_money(row.get("Start_rate"))
        high = parse_money(row.get("End_rate"))
        if low is None and high is None:
            values = [parse_money(item) for item in re.split(r"[-–]", row.get("Hourly_Rate", ""))]
            numbers = [value for value in values if value is not None]
            low = min(numbers) if numbers else None
            high = max(numbers) if numbers else None
        return low, high or low, "hourly"
    amount = parse_money(row.get("Job_Cost"))
    return amount, amount, "fixed"


def normalize_job_60k(row: dict[str, str]) -> dict[str, Any] | None:
    title = clean_text(row.get("Job Title"), limit=300)
    description = clean_text(row.get("Description"))
    if not title or not description:
        return None
    source_key = row.get("Job_URL") or f"{title}\x1f{description}"
    job_id = stable_id("job", "upwork_jobs_60k:v5", source_key)
    categories = [
        clean_text(row.get(f"Category_{index}"), limit=100)
        for index in range(1, 10)
        if row.get(f"Category_{index}")
    ]
    low, high, pricing_model = budget_range(row)
    payment_status = str(row.get("Payment_Situation") or "").lower()
    rating = parse_number(row.get("Rating"))
    feedback = int(parse_number(row.get("Feedback_Num")) or 0)
    connects = int(
        parse_number(row.get("New_Connects_Num")) or parse_number(row.get("Connects_Num")) or 0
    )
    return {
        "job_id": job_id,
        "client_id": stable_id("client", job_id),
        "title": title,
        "description": description,
        "deliverables": [],
        "required_skills": list(dict.fromkeys(categories)),
        "budget": {"min": low, "max": high, "currency": "USD"},
        "pricing_model": pricing_model,
        "duration_text": clean_text(row.get("Time_Limitation"), limit=100) or None,
        "screening_questions": [],
        "connects_cost": connects,
        "client_history": {
            "payment_verified": "unverified" not in payment_status and "verified" in payment_status,
            "average_rating": rating,
            "completed_projects": feedback,
            "total_spent_usd": parse_money(row.get("Spent($)")),
            "enterprise": bool(str(row.get("Enterprise_Client") or "").strip()),
            "country": clean_text(row.get("Client_Country"), limit=100) or None,
        },
        "market_signals": {
            "applicants": clean_text(row.get("Applicants_Num"), limit=100) or None,
            "freelancers_needed": int(parse_number(row.get("Freelancers_Num")) or 1),
            "experience_level": clean_text(row.get("EX_level_demand"), limit=100) or None,
            "search_keyword": clean_text(row.get("Search_Keyword"), limit=100) or None,
        },
        "security_signals": find_injected_instructions(description),
        "provenance": {
            "data_origin": "real_public_dataset",
            "source_ref": "ahmedmyalo/upwork-freelance-jobs-60k",
            "source_version": 5,
            "license": "Apache-2.0",
            "direct_url_removed": True,
            "pii_redacted": True,
        },
    }


def normalize_job_50k(row: dict[str, str]) -> dict[str, Any] | None:
    title = clean_text(row.get("title"), limit=300)
    description = clean_text(row.get("description"))
    if not title or not description:
        return None
    source_key = row.get("link") or f"{title}\x1f{description}"
    job_id = stable_id("job", "upwork_jobs_2024_50k:v1", source_key)
    is_hourly = parse_bool(row.get("is_hourly"))
    low = parse_money(row.get("hourly_low")) if is_hourly else parse_money(row.get("budget"))
    high = parse_money(row.get("hourly_high")) if is_hourly else low
    return {
        "job_id": job_id,
        "client_id": stable_id("client", job_id),
        "title": title,
        "description": description,
        "deliverables": [],
        "required_skills": [],
        "budget": {"min": low, "max": high or low, "currency": "USD"},
        "pricing_model": "hourly" if is_hourly else "fixed",
        "published_at": str(row.get("published_date") or "") or None,
        "screening_questions": [],
        "connects_cost": 0,
        "client_history": {
            "country": clean_text(row.get("country"), limit=100) or None,
        },
        "security_signals": find_injected_instructions(description),
        "provenance": {
            "data_origin": "real_public_dataset",
            "source_ref": "asaniczka/upwork-job-postings-dataset-2024-50k-records",
            "source_version": 1,
            "license": "ODC-By-1.0",
            "direct_url_removed": True,
            "pii_redacted": True,
        },
    }


def normalize_contract(row: dict[str, str]) -> dict[str, Any] | None:
    title = clean_text(row.get("job_title"), limit=300)
    rate = parse_money(row.get("hourly_rate"))
    total_paid = parse_money(row.get("total_paid"))
    if not title or total_paid is None:
        return None
    source_key = (
        row.get("job_id"),
        row.get("freelancer_id"),
        row.get("start_date"),
        row.get("end_date"),
    )
    return {
        "contract_id": stable_id("contract", "freelance_contracts_1m3:v1", *source_key),
        "job_title": title,
        "start_date": row.get("start_date") or None,
        "end_date": row.get("end_date") or None,
        "total_hours": parse_number(row.get("total_hours")),
        "total_paid_usd": total_paid,
        "hourly_rate_usd": rate,
        "pricing_model": "hourly" if rate is not None else "fixed_or_milestone",
        "provenance": {
            "data_origin": "real_public_dataset",
            "source_ref": "asaniczka/freelance-contracts-dataset-1-3-million-entries",
            "source_version": 1,
            "license": "ODC-By-1.0",
            "source_ids_removed": True,
        },
    }


def iter_archive_rows(path: Path, member: str) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        with archive.open(member) as raw:
            with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                yield from csv.DictReader(text)


def write_normalized(
    rows: Iterator[dict[str, str]],
    normalizer: Callable[[dict[str, str]], dict[str, Any] | None],
    destination: Path,
    *,
    split: bool = False,
) -> dict[str, int]:
    counts = {"read": 0, "written": 0, "rejected": 0, "train": 0, "dev": 0}
    handles: dict[str, Any] = {}
    try:
        if split:
            handles["train"] = destination.with_name("jobs_train.jsonl").open("w", encoding="utf-8")
            handles["dev"] = destination.with_name("jobs_dev.jsonl").open("w", encoding="utf-8")
        else:
            handles["all"] = destination.open("w", encoding="utf-8")
        for row in rows:
            counts["read"] += 1
            normalized = normalizer(row)
            if normalized is None:
                counts["rejected"] += 1
                continue
            bucket = "all"
            if split:
                digest = hashlib.sha256(normalized["job_id"].encode("utf-8")).digest()
                bucket = "dev" if int.from_bytes(digest[:2]) % 5 == 0 else "train"
            handles[bucket].write(json.dumps(normalized, ensure_ascii=False) + "\n")
            counts["written"] += 1
            if bucket in counts:
                counts[bucket] += 1
    finally:
        for handle in handles.values():
            handle.close()
    return counts


def load_registry() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return dict(payload["sources"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize selected Kaggle corpora for GigBid")
    parser.add_argument("--raw-dir", default="data/raw/kaggle")
    parser.add_argument("--output-dir", default="data/processed/kaggle")
    args = parser.parse_args()

    raw_dir = ROOT / args.raw_dir
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = load_registry()
    specs = (
        ("upwork_jobs_60k", normalize_job_60k, output_dir / "jobs.jsonl", True),
        (
            "upwork_jobs_2024_50k",
            normalize_job_50k,
            output_dir / "jobs_temporal_holdout.jsonl",
            False,
        ),
        (
            "freelance_contracts_1m3",
            normalize_contract,
            output_dir / "pricing_history.jsonl",
            False,
        ),
    )
    results: dict[str, dict[str, int]] = {}
    for source_name, normalizer, destination, split in specs:
        source = sources[source_name]
        archive = raw_dir / str(source["archive_name"])
        if not archive.exists():
            raise SystemExit(f"Missing {archive}. Run python -m data.pipelines.fetch_kaggle first.")
        rows = iter_archive_rows(archive, str(source["csv_member"]))
        results[source_name] = write_normalized(
            rows,
            normalizer,
            destination,
            split=split,
        )
        print(f"normalized {source_name}: {results[source_name]}")

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "classification": {
            "selected_kaggle_sources": "real_public_dataset",
            "smoke_fixtures": "synthetic",
            "user_portfolios": "private_user_data_not_committed",
        },
        "transformations": [
            "remove direct job URLs and raw source identifiers",
            "hash record identifiers with SHA-256",
            "redact email, phone and payment-like strings",
            f"truncate descriptions to {MAX_DESCRIPTION_CHARACTERS} characters",
            "split the 2023 jobs deterministically 80/20 by hashed job ID",
            "reserve the 2024 jobs as an out-of-period holdout",
        ],
        "counts": results,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
