import json
from pathlib import Path

from agent.handoffs import FitReport, JobSpec, RiskReport
from agent.nodes.pricing import price_job
from agent.pricing_priors import find_market_prior, load_pricing_priors


def write_priors(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "metadata": {"source": "public-contracts-test"},
                "priors": {
                    "web_development": {
                        "hourly": {
                            "count": 120,
                            "p25": 20,
                            "median": 35,
                            "p75": 50,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_market_prior_is_category_and_pricing_model_specific(tmp_path: Path) -> None:
    path = tmp_path / "priors.json"
    write_priors(path)
    load_pricing_priors.cache_clear()
    job = JobSpec(
        job_id="job-1",
        title="React API developer",
        description="Build a website backend",
        pricing_model="hourly",
    )
    prior = find_market_prior(job, path=path)
    assert prior is not None
    assert prior.category == "web_development"
    assert prior.median == 35
    assert prior.sample_size == 120


def test_pricing_uses_prior_but_never_breaks_user_floor_or_client_band(tmp_path: Path) -> None:
    path = tmp_path / "priors.json"
    write_priors(path)
    load_pricing_priors.cache_clear()
    job = JobSpec(
        job_id="job-2",
        title="React website",
        description="Build a React website",
        pricing_model="hourly",
        budget_min=40,
        budget_max=45,
    )
    prior = find_market_prior(job, path=path)
    assert prior is not None
    quote = price_job(
        job,
        FitReport(score=0.8),
        RiskReport(score=0.1, explanation="Low risk"),
        user_floor=42,
        market_prior=prior,
    )
    assert 42 <= quote.amount <= 45
    assert quote.market_prior_category == "web_development"
    assert quote.market_prior_sample_size == 120
    assert quote.market_prior_source == "public-contracts-test"
