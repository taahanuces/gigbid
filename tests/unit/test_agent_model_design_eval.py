from __future__ import annotations

import pytest

from agent.handoffs import RiskFlag, RiskReport
from evals.runners.agent_model_design_eval import (
    apply_safety_guard,
    validate_controller_output,
)


def test_validates_each_model_backed_control_shape() -> None:
    hand = validate_controller_output(
        "hand_built", {"action": "bid", "reason": "fit and budget are acceptable"}
    )
    supervisor = validate_controller_output(
        "supervisor",
        {
            "plan": ["analyze_job", "match_fit", "assess_risk", "decide"],
            "action": "watch",
            "reason": "risk needs review",
        },
    )
    react = validate_controller_output(
        "react_style",
        {
            "steps": [
                {"action": tool, "observation": f"inspect {tool}"}
                for tool in ("analyze_job", "assess_risk", "match_fit", "decide")
            ],
            "action": "skip",
            "reason": "material risk",
        },
    )

    assert hand.action == "bid"
    assert supervisor.action == "watch"
    assert len(react.trace) == 4


def test_rejects_unbounded_or_unknown_supervisor_plan() -> None:
    with pytest.raises(ValueError, match="each allowed tool exactly once"):
        validate_controller_output(
            "supervisor",
            {
                "plan": ["analyze_job", "browse_web", "decide"],
                "action": "bid",
                "reason": "invalid plan",
            },
        )


def test_policy_guard_overrides_unsafe_model_action() -> None:
    risk = RiskReport(
        score=0.95,
        flags=[RiskFlag.PROMPT_INJECTION],
        explanation="Untrusted job text contains instructions for the agent.",
        blocked=True,
    )

    assert apply_safety_guard("bid", risk) == ("skip", True)
    assert apply_safety_guard("skip", risk) == ("skip", False)
