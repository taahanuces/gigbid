from __future__ import annotations

from evals.runners.simulator_outcomes import Confusion


def test_confusion_metrics_handle_positive_and_empty_cases() -> None:
    empty = Confusion()
    assert empty.precision == 0.0
    assert empty.recall == 0.0

    measured = Confusion(true_positive=8, false_positive=2, false_negative=4)
    assert measured.precision == 0.8
    assert measured.recall == 8 / 12
