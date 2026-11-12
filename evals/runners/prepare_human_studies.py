from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.handoffs import EvidenceItem
from agent.nodes.analyst import analyze_job
from agent.nodes.critic import critique_proposal
from agent.nodes.fit_matcher import match_fit
from agent.nodes.pricing import price_job
from agent.nodes.risk_assessor import assess_risk
from agent.nodes.writer import draft_proposal
from rag.index.memory import InMemoryEvidenceIndex
from rag.retriever import retrieve_for_job
from rag.verify import verify_claims

ROOT = Path(__file__).resolve().parents[2]


def _indexes(personas: set[str]) -> dict[str, InMemoryEvidenceIndex]:
    result: dict[str, InMemoryEvidenceIndex] = {}
    for persona in personas:
        source = ROOT / "data/processed/personas" / f"{persona}.jsonl"
        result[persona] = InMemoryEvidenceIndex(
            [
                EvidenceItem.model_validate_json(line)
                for line in source.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        )
    return result


def _proposal(raw: dict[str, Any], index: InMemoryEvidenceIndex, variant: str) -> dict[str, Any]:
    job = analyze_job(raw)
    evidence = retrieve_for_job(job, index, variant=variant, k=10)
    fit = match_fit(job, evidence)
    risk = assess_risk(job)
    draft = draft_proposal(job, fit, evidence, price_job(job, fit, risk, user_floor=300))
    verification = verify_claims(draft, evidence)
    verified = draft.model_copy(update={"cover_letter": verification.corrected_cover_letter})
    critique = critique_proposal(job, verified, verification)
    return {
        "text": verified.cover_letter,
        "evidence_ids": [item.evidence_id for item in evidence],
        "unsupported_claims": verification.unsupported_after,
        "critic_passed": critique.passed,
        "grounding_score": critique.grounding_score,
        "personalization_score": critique.personalization_score,
    }


def run() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    benchmark = json.loads(
        (ROOT / "evals/datasets/synthetic_rag_benchmark.json").read_text(encoding="utf-8")
    )
    selected: list[dict[str, Any]] = []
    per_persona: dict[str, int] = defaultdict(int)
    for raw in benchmark:
        persona = str(raw["persona"])
        if per_persona[persona] < 10:
            selected.append(raw)
            per_persona[persona] += 1
    indexes = _indexes(set(per_persona))
    randomizer = random.Random(4016)  # noqa: S311 - deterministic study randomisation
    panel_items: list[dict[str, Any]] = []
    key_items: list[dict[str, str]] = []
    calibration_items: list[dict[str, Any]] = []
    for item_number, raw in enumerate(selected, start=1):
        persona = str(raw["persona"])
        proposals = {
            "v0_naive": _proposal(raw, indexes[persona], "v0_naive"),
            "v2_hybrid": _proposal(raw, indexes[persona], "v2_hybrid"),
        }
        variants = ["v0_naive", "v2_hybrid"]
        randomizer.shuffle(variants)
        panel_id = f"panel-{item_number:02d}"
        panel_items.append(
            {
                "panel_id": panel_id,
                "persona": persona,
                "job_title": raw["title"],
                "job_description": raw["description"],
                "proposal_a": proposals[variants[0]]["text"],
                "proposal_b": proposals[variants[1]]["text"],
                "preferred": None,
                "grounding_winner": None,
                "personalization_winner": None,
                "rationale": None,
            }
        )
        key_items.append(
            {"panel_id": panel_id, "proposal_a": variants[0], "proposal_b": variants[1]}
        )
        proposal = proposals["v2_hybrid"]
        calibration_items.append(
            {
                "item_id": f"calibration-{item_number:02d}",
                "persona": persona,
                "job_title": raw["title"],
                "proposal": proposal["text"],
                "evidence_ids": proposal["evidence_ids"],
                "machine_label": "pass" if proposal["critic_passed"] else "fail",
                "human_label": None,
                "human_notes": None,
            }
        )
    generated_at = datetime.now(UTC).isoformat()
    panel = {
        "metadata": {
            "generated_at": generated_at,
            "data_origin": "synthetic",
            "items": len(panel_items),
            "status": "awaiting_blind_human_ratings",
            "instructions": "Rate A or B without opening the separate key file.",
        },
        "items": panel_items,
    }
    key = {
        "metadata": {"generated_at": generated_at, "keep_hidden_until_ratings_complete": True},
        "items": key_items,
    }
    calibration = {
        "metadata": {
            "generated_at": generated_at,
            "data_origin": "synthetic",
            "items": len(calibration_items),
            "status": "awaiting_author_labels",
            "allowed_labels": ["pass", "fail"],
        },
        "items": calibration_items,
    }
    return panel, key, calibration


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="evals/human_studies")
    args = parser.parse_args()
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    panel, key, calibration = run()
    outputs = {
        "proposal_pairwise_panel.json": panel,
        "proposal_pairwise_key.json": key,
        "judge_calibration.json": calibration,
    }
    for name, payload in outputs.items():
        (output_dir / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(output_dir)


if __name__ == "__main__":
    main()
