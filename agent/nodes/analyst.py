from __future__ import annotations

from typing import Any

from agent.handoffs import JobSpec


def analyze_job(job: dict[str, Any]) -> JobSpec:
    budget = job.get("budget") or {}
    if not isinstance(budget, dict):
        budget = {}
    description = str(job.get("description") or job.get("body") or "").strip()
    skills = job.get("required_skills") or job.get("skills") or []
    deliverables = job.get("deliverables") or []
    if not deliverables and description:
        deliverables = [part.strip() for part in description.split(".")[:2] if part.strip()]
    return JobSpec(
        job_id=str(job.get("job_id") or job.get("id") or ""),
        client_id=str(job["client_id"]) if job.get("client_id") else None,
        title=str(job.get("title") or "Untitled job"),
        description=description,
        deliverables=[str(item) for item in deliverables],
        required_skills=[str(item) for item in skills],
        preferred_skills=[str(item) for item in job.get("preferred_skills", [])],
        budget_min=_optional_float(budget.get("min", job.get("budget_min"))),
        budget_max=_optional_float(budget.get("max", job.get("budget_max"))),
        currency=str(budget.get("currency") or job.get("currency") or "USD"),
        pricing_model=str(job.get("pricing_model") or "fixed"),
        timeline_days=_optional_int(job.get("duration_days") or job.get("timeline_days")),
        screening_questions=[str(item) for item in job.get("screening_questions", [])],
        hidden_needs=[str(item) for item in job.get("hidden_needs", [])],
        connects_cost=int(job.get("connects_cost") or 0),
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float)):
        raise ValueError("Expected a numeric budget value")
    return float(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, (str, int, float)):
        raise ValueError("Expected an integer duration value")
    return int(value)
