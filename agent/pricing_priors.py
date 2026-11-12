from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import cast

from agent.handoffs import JobSpec

ROOT = Path(__file__).resolve().parents[1]

CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "ai_ml": (
        "machine learning",
        "artificial intelligence",
        "data science",
        "deep learning",
        "computer vision",
        "natural language",
        "pytorch",
        "tensorflow",
        "llm",
        " ai ",
        " ml ",
    ),
    "web_development": (
        "website",
        "web developer",
        "react",
        "next.js",
        "wordpress",
        "shopify",
        "frontend",
        "backend",
        "javascript",
        "api",
    ),
    "data_analytics": (
        "data analyst",
        "data analysis",
        "power bi",
        "tableau",
        "dashboard",
        "excel",
        "sql",
        "analytics",
    ),
    "design_creative": (
        "graphic design",
        "designer",
        "figma",
        "illustration",
        "video editing",
        "logo",
        "ui/ux",
    ),
    "writing_translation": (
        "writer",
        "writing",
        "translation",
        "translator",
        "copywriting",
        "proofread",
        "content",
    ),
    "marketing_sales": (
        "marketing",
        "seo",
        "sales",
        "lead generation",
        "social media",
        "advertising",
    ),
    "admin_support": (
        "virtual assistant",
        "data entry",
        "customer support",
        "administrative",
        "bookkeeping",
    ),
}


def classify_category(text: str) -> str:
    normalized = f" {text.casefold()} "
    scores = {
        category: sum(term in normalized for term in terms)
        for category, terms in CATEGORY_TERMS.items()
    }
    best_category, best_score = max(scores.items(), key=lambda item: item[1])
    return best_category if best_score else "other"


@dataclass(frozen=True, slots=True)
class MarketPrior:
    category: str
    pricing_model: str
    sample_size: int
    p25: float
    median: float
    p75: float
    source: str


@lru_cache(maxsize=4)
def load_pricing_priors(
    path: str | Path = ROOT / "data/derived/pricing_priors.json",
) -> dict[str, object]:
    artifact_path = Path(path)
    if not artifact_path.exists():
        return {}
    raw = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return cast(dict[str, object], raw)


def find_market_prior(
    job: JobSpec,
    *,
    path: str | Path = ROOT / "data/derived/pricing_priors.json",
) -> MarketPrior | None:
    artifact = load_pricing_priors(path)
    raw_priors = artifact.get("priors")
    metadata = artifact.get("metadata")
    if not isinstance(raw_priors, dict) or not isinstance(metadata, dict):
        return None
    category = classify_category(" ".join([job.title, job.description, *job.required_skills]))
    pricing_model = "hourly" if job.pricing_model == "hourly" else "fixed_or_milestone"
    category_priors = raw_priors.get(category) or raw_priors.get("all")
    if not isinstance(category_priors, dict):
        return None
    raw = category_priors.get(pricing_model)
    if not isinstance(raw, dict):
        return None
    source = metadata.get("source")
    required = (raw.get("count"), raw.get("p25"), raw.get("median"), raw.get("p75"))
    if not all(isinstance(value, int | float) for value in required) or not isinstance(source, str):
        return None
    return MarketPrior(
        category=category,
        pricing_model=pricing_model,
        sample_size=int(raw["count"]),
        p25=float(raw["p25"]),
        median=float(raw["median"]),
        p75=float(raw["p75"]),
        source=source,
    )
