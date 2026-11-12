from agent.nodes.portfolio_builder import (
    approve_case_study_candidate,
    build_case_study_candidate,
)
from evals.runners.portfolio_builder_eval import run


def test_portfolio_builder_verifies_code_and_quarantines_outcome_claims() -> None:
    candidate = build_case_study_candidate(
        repository="owner/repo",
        readme="# Demand API\nBuilt with FastAPI. Improved revenue by 75%.",
        code_manifest={"app.py": "from fastapi import FastAPI", "Dockerfile": "FROM python"},
    )

    assert {"Python", "FastAPI", "Docker"}.issubset(candidate.verified_technologies)
    assert candidate.unsupported_claims == ["Built with FastAPI. Improved revenue by 75%."]
    assert candidate.status == "pending_human_approval"

    approved = approve_case_study_candidate(
        candidate,
        evidence_id="github-owner-repo",
        tenant_id="demo",
        persona="ai-ml-engineer",
    )
    assert approved.source == "github://owner/repo"
    assert "75%" not in approved.text
    assert approved.outcome == "repository_verified_human_approved"


def test_portfolio_builder_evaluation_is_complete_and_synthetic() -> None:
    result = run()
    assert result["metadata"]["repositories"] == 12
    assert result["metadata"]["live_github_validation"] is False
    assert result["summary"]["technology_recall"] == 1
    assert result["summary"]["unsupported_claim_recall"] == 1
