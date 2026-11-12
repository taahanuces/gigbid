from __future__ import annotations

from evals.runners.model_profile_eval import EvalRow, _select_jobs, _summarize


def test_model_profile_job_slice_is_balanced_and_safe() -> None:
    jobs = _select_jobs(per_persona=1)

    assert len(jobs) == 3
    assert len({str(job["persona"]) for job in jobs}) == 3
    assert all(not job["security_signals"] for job in jobs)


def test_model_profile_summary_counts_failures_without_inventing_metrics() -> None:
    rows: list[EvalRow] = [
        {
            "model": "model-a",
            "job_id": "job-1",
            "persona": "persona",
            "job_type": "type",
            "success": True,
            "json_schema_valid": True,
            "citation_precision": 1.0,
            "unsupported_claims_before": 1,
            "unsupported_claims_after": 0,
            "grounding_score": 1.0,
            "personalization_score": 0.5,
            "critic_passed": True,
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "latency_ms": 2000,
            "completion_tokens_per_second": 10,
            "cost_usd": 0,
        },
        {
            "model": "model-a",
            "job_id": "job-2",
            "persona": "persona",
            "job_type": "type",
            "success": False,
            "json_schema_valid": False,
            "cost_usd": 0,
            "error": "ValueError: invalid",
        },
    ]

    summary = _summarize(rows)["model-a"]

    assert summary["calls"] == 2
    assert summary["successful_calls"] == 1
    assert summary["json_schema_valid_rate"] == 0.5
    assert summary["citation_precision"] == 1.0
    assert summary["p95_latency_ms"] == 2000
