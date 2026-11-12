from agent.memory.promotion_rules import (
    OutcomeObservation,
    StyleEditObservation,
    promote_outcome_strategy,
    promote_style_pattern,
)


def test_style_memory_requires_repetition() -> None:
    observations = [StyleEditObservation(pattern="remove generic opening", accepted=True)] * 2
    assert promote_style_pattern(observations) is None
    observations.append(StyleEditObservation(pattern="remove generic opening", accepted=True))
    assert promote_style_pattern(observations) == "remove generic opening"


def test_outcome_memory_requires_enough_observations() -> None:
    observations = [
        OutcomeObservation(category="data", strategy="lead-with-metric", replied=True)
        for _ in range(5)
    ]
    assert promote_outcome_strategy(observations) == "lead-with-metric"
