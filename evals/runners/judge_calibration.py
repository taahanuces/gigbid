from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def cohen_kappa(left: list[str], right: list[str]) -> float:
    if not left or len(left) != len(right):
        raise ValueError("Two non-empty label lists of equal length are required")
    labels = sorted(set(left).union(right))
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    left_counts = Counter(left)
    right_counts = Counter(right)
    expected = sum(
        left_counts[label] / len(left) * right_counts[label] / len(right)
        for label in labels
    )
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def evaluate(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    items = source["items"]
    labelled = [item for item in items if item.get("human_label") in {"pass", "fail"}]
    if len(labelled) != 30:
        return {
            "status": "awaiting_author_labels",
            "required": 30,
            "labelled": len(labelled),
            "cohen_kappa": None,
            "note": "Human labels cannot be generated or inferred by this script.",
        }
    human = [str(item["human_label"]) for item in labelled]
    machine = [str(item["machine_label"]) for item in labelled]
    pairs = Counter(zip(human, machine, strict=True))
    return {
        "status": "complete",
        "required": 30,
        "labelled": 30,
        "agreement": sum(a == b for a, b in zip(human, machine, strict=True)) / 30,
        "cohen_kappa": cohen_kappa(human, machine),
        "confusion": {f"human={a},machine={b}": count for (a, b), count in pairs.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="evals/human_studies/judge_calibration.json")
    parser.add_argument("--output", default="evals/results/judge_calibration.json")
    args = parser.parse_args()
    result = evaluate(ROOT / args.input)
    destination = ROOT / args.output
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
