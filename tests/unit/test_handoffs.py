import pytest
from pydantic import ValidationError

from agent.handoffs import ApprovalAction, ApprovalDecision, JobSpec, RiskReport


def test_job_spec_rejects_inverted_budget() -> None:
    with pytest.raises(ValidationError):
        JobSpec(
            job_id="job-1",
            title="Example",
            description="Example work",
            budget_min=500,
            budget_max=100,
        )


def test_risk_score_is_bounded() -> None:
    with pytest.raises(ValidationError):
        RiskReport(score=1.2, explanation="invalid")


def test_rejection_requires_reason() -> None:
    with pytest.raises(ValidationError):
        ApprovalDecision(action=ApprovalAction.REJECT)
