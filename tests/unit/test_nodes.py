import json
from pathlib import Path

from agent.handoffs import BidAction, EvidenceItem
from agent.nodes.analyst import analyze_job
from agent.nodes.decision import decide_bid
from agent.nodes.fit_matcher import match_fit
from agent.nodes.risk_assessor import assess_risk

ROOT = Path(__file__).resolve().parents[2]


def load_data() -> tuple[list[dict], list[EvidenceItem]]:
    jobs = json.loads((ROOT / "evals/datasets/smoke_jobs.json").read_text())
    evidence = [
        EvidenceItem.model_validate(item)
        for item in json.loads((ROOT / "evals/datasets/smoke_portfolio.json").read_text())
    ]
    return jobs, evidence


def test_safe_job_is_bid_candidate() -> None:
    jobs, evidence = load_data()
    spec = analyze_job(jobs[0])
    risk = assess_risk(
        spec,
        {"payment_verified": True, "average_rating": 4.8, "completed_projects": 12},
    )
    fit = match_fit(spec, evidence)
    assert decide_bid(spec, risk, fit).action == BidAction.BID


def test_risky_job_is_blocked_and_injection_is_recorded() -> None:
    jobs, evidence = load_data()
    spec = analyze_job(jobs[1])
    risk = assess_risk(
        spec,
        {"payment_verified": False, "average_rating": 2, "completed_projects": 0},
    )
    fit = match_fit(spec, evidence)
    decision = decide_bid(spec, risk, fit)
    assert risk.blocked
    assert risk.ignored_instructions
    assert decision.action == BidAction.SKIP
