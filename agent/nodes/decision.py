from __future__ import annotations

from agent.handoffs import BidAction, BidDecision, FitReport, JobSpec, RiskReport


def decide_bid(
    job: JobSpec,
    risk: RiskReport,
    fit: FitReport,
    *,
    minimum_fit_score: float = 0.6,
    maximum_risk_score: float = 0.7,
    maximum_connects: int = 16,
) -> BidDecision:
    reasons: list[str] = []
    if risk.blocked or risk.score >= maximum_risk_score:
        return BidDecision(
            action=BidAction.SKIP,
            confidence=max(0.7, risk.score),
            reasons=[f"Risk threshold exceeded: {risk.explanation}"],
        )
    if job.connects_cost > maximum_connects:
        return BidDecision(
            action=BidAction.SKIP,
            confidence=0.85,
            reasons=["Connects cost exceeds the configured per-bid limit."],
        )
    if fit.score >= minimum_fit_score:
        reasons.append(f"Evidence supports {fit.score:.0%} of evaluated requirements.")
        return BidDecision(action=BidAction.BID, confidence=fit.score, reasons=reasons)
    if fit.score >= minimum_fit_score * 0.7:
        reasons.append("Fit is plausible but evidence coverage is incomplete.")
        return BidDecision(action=BidAction.WATCH, confidence=0.6, reasons=reasons)
    return BidDecision(
        action=BidAction.SKIP,
        confidence=max(0.6, 1 - fit.score),
        reasons=["Portfolio evidence does not support enough required work."],
    )
