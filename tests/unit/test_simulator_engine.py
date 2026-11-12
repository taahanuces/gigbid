from __future__ import annotations

from apps.simulator.engine import SimulatorState, evaluate_proposal


def _job() -> dict[str, object]:
    return {
        "job_id": "job-1",
        "client_id": "client-1",
        "title": "Python forecasting pipeline",
        "required_skills": ["Python", "Forecasting"],
        "connects_cost": 8,
        "category": "ai_ml",
        "security_signals": [],
    }


def _client() -> dict[str, object]:
    return {
        "client_id": "client-1",
        "hidden_preferences": {
            "must_have_skills": ["Python"],
            "budget_ceiling": 700,
            "reply_threshold": 0.5,
            "hire_threshold": 0.7,
        },
    }


def test_outcome_engine_rewards_specific_grounded_proposal() -> None:
    outcome = evaluate_proposal(
        proposal={
            "cover_letter": (
                "Your Python forecasting pipeline needs reproducible evaluation. "
                "I built the matching workflow [case-1] and can deliver the first milestone "
                "after confirming the data schema and metrics. " * 4 + "I can deliver at 650 USD."
            )
        },
        job=_job(),
        client=_client(),
    )
    assert outcome["replied"] is True
    assert outcome["hired"] is True
    assert outcome["data_origin"] == "synthetic_rule_based"


def test_state_writes_are_idempotent_and_connects_are_spent_once() -> None:
    fixture = {"jobs": [_job()], "clients": {"client-1": _client()}}
    state = SimulatorState(fixture)
    payload = {"job_id": "job-1", "cover_letter": "A" * 30}
    first = state.create_draft(tenant_id="demo", payload=payload, idempotency_key="draft-key-0001")
    second = state.create_draft(tenant_id="demo", payload=payload, idempotency_key="draft-key-0001")
    assert first == second
    assert state.balance("demo") == 112
    assert len(state.proposals) == 1
