from __future__ import annotations

from agent.handoffs import FitReport, JobSpec, PriceQuote, RiskReport
from agent.pricing_priors import MarketPrior


def price_job(
    job: JobSpec,
    fit: FitReport,
    risk: RiskReport,
    *,
    user_floor: float,
    market_median: float | None = None,
    market_prior: MarketPrior | None = None,
) -> PriceQuote:
    if market_prior is not None:
        market_median = market_prior.median
    low = max(user_floor, job.budget_min or user_floor)
    observed_high = market_prior.p75 if market_prior is not None else market_median
    high = max(low, job.budget_max or observed_high or low * 1.35)
    anchor = market_median if market_median is not None else (low + high) / 2
    fit_adjustment = 0.9 + fit.score * 0.2
    risk_adjustment = 1 + min(risk.score, 0.5) * 0.15
    amount = min(high, max(low, anchor * fit_adjustment * risk_adjustment))
    expected_value_positive = fit.score >= 0.6 and not risk.blocked and job.connects_cost <= 16
    return PriceQuote(
        amount=round(amount, 2),
        currency=job.currency,
        floor_amount=round(user_floor, 2),
        fair_band_min=round(low, 2),
        fair_band_max=round(high, 2),
        connects_cost=job.connects_cost,
        expected_value_positive=expected_value_positive,
        rationale=(
            f"Price stays inside the observed/client band and adjusts for {fit.score:.0%} fit "
            f"and {risk.score:.0%} risk."
            + (
                f" Historical {market_prior.category} {market_prior.pricing_model} prior uses "
                f"{market_prior.sample_size:,} public contract records."
                if market_prior is not None
                else " No matching public market prior was available."
            )
        ),
        market_prior_category=market_prior.category if market_prior is not None else None,
        market_prior_sample_size=market_prior.sample_size if market_prior is not None else None,
        market_prior_source=market_prior.source if market_prior is not None else None,
    )
