from __future__ import annotations

import json

from evals.runners.check_regression import check


def test_regression_gate_reports_quality_failures(tmp_path) -> None:
    outcomes = tmp_path / "outcomes.json"
    rag = tmp_path / "rag.json"
    outcomes.write_text(
        json.dumps(
            {
                "personas": {
                    "demo": {
                        "bid_or_skip_f1": 0.2,
                        "scam_recall": 0.9,
                        "reply_rate": 0.6,
                        "unsupported_claims_after_per_proposal": 0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    rag.write_text(
        json.dumps(
            {
                "overall": {
                    "v0": {
                        "evidence_recall_at_5": 0.5,
                        "seeded_attack_unsupported_after": 0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    assert check(outcomes_path=outcomes, rag_path=rag) == ["demo bid-or-skip F1 fell below 0.80"]


def test_regression_gate_checks_model_backed_agent_safety(tmp_path) -> None:
    outcomes = tmp_path / "outcomes.json"
    rag = tmp_path / "rag.json"
    agent_model = tmp_path / "agent_model.json"
    outcomes.write_text(
        json.dumps(
            {
                "personas": {
                    "demo": {
                        "bid_or_skip_f1": 1,
                        "scam_recall": 1,
                        "reply_rate": 1,
                        "unsupported_claims_after_per_proposal": 0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    rag.write_text(
        json.dumps(
            {
                "overall": {
                    "v0": {
                        "evidence_recall_at_5": 0.5,
                        "seeded_attack_unsupported_after": 0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    agent_model.write_text(
        json.dumps(
            {
                "metadata": {
                    "jobs": 1,
                    "models": ["demo"],
                    "architectures": ["hand_built"],
                },
                "summary": {
                    "demo": {
                        "hand_built": {
                            "bid_or_skip_f1": 1,
                            "completion_rate": 1,
                            "final_safety_violation_rate": 0.5,
                        }
                    }
                },
                "rows": [{}],
            }
        ),
        encoding="utf-8",
    )

    assert check(
        outcomes_path=outcomes,
        rag_path=rag,
        agent_model_path=agent_model,
    ) == ["demo/hand_built produced a final safety violation"]
