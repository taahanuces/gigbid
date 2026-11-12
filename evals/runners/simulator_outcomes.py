from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent.config import load_config
from agent.graphs.bid_graph import BidGraphServices, build_bid_graph
from agent.handoffs import (
    BidDecision,
    ClaimVerificationReport,
    EvidenceItem,
    PriceQuote,
    RiskFlag,
)
from agent.persistence import checkpoint_serializer
from agent.state import GigBidState
from apps.simulator.adapter import SimulatorMarketplaceAdapter
from apps.simulator.engine import SimulatorState
from evals.metrics import precision_recall_f1
from rag.index.memory import InMemoryEvidenceIndex

ROOT = Path(__file__).resolve().parents[2]
PERSONAS = ("ai-ml-engineer", "full-stack-developer", "data-analyst")
EVALUATION_JOBS = 30


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile / 100
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _number(value: object) -> float:
    if not isinstance(value, (str, int, float)):
        raise ValueError("Expected a numeric evaluation field")
    return float(value)


def _stable_fraction(value: str) -> float:
    digest = hashlib.sha256(value.encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


@dataclass(slots=True)
class Confusion:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0


def _load_benchmark(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Expected a list of objects in {path}")
    return cast(list[dict[str, Any]], value)


def _evidence(persona: str) -> list[EvidenceItem]:
    path = ROOT / "data/processed/personas" / f"{persona}.jsonl"
    if not path.exists():
        raise FileNotFoundError("Run make synthetic-data before simulator outcome evaluation")
    return [
        EvidenceItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _outcome_fixture(persona: str, benchmark: list[dict[str, Any]]) -> dict[str, object]:
    jobs = [dict(job) for job in benchmark if job.get("persona") == persona]
    if len(jobs) != EVALUATION_JOBS:
        raise ValueError(f"Expected {EVALUATION_JOBS} jobs for {persona}, found {len(jobs)}")
    clients: dict[str, dict[str, object]] = {}
    labels: dict[str, dict[str, object]] = {}
    for job in jobs:
        client_id = str(job["client_id"])
        budget = cast(dict[str, object], job["budget"])
        variation = _stable_fraction(str(job["job_id"]))
        clients[client_id] = {
            **cast(dict[str, object], job["client_history"]),
            "client_id": client_id,
            "hidden_preferences": {
                "must_have_skills": list(job.get("required_skills", []))[:2],
                "budget_ceiling": budget["max"],
                "dislikes_generic_openings": True,
                "reply_threshold": round(0.55 + variation * 0.50, 3),
                "hire_threshold": round(0.75 + variation * 0.35, 3),
            },
            "data_origin": "synthetic",
        }
        labels[str(job["job_id"])] = {
            "bid_action": job["gold_action"],
            "scam": job["gold_scam"],
            "fair_price_band": budget,
            "label_origin": "synthetic_authored_scenario",
        }
        job["category"] = job["job_type"]
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "job_origin": "synthetic",
            "client_preferences_origin": "synthetic",
        },
        "jobs": jobs,
        "clients": clients,
        "gold_labels": labels,
    }


async def _evaluate_persona(
    persona: str, benchmark: list[dict[str, Any]]
) -> tuple[dict[str, object], list[dict[str, object]]]:
    fixture = _outcome_fixture(persona, benchmark)
    state = SimulatorState(fixture, default_connects=10_000)
    marketplace = SimulatorMarketplaceAdapter(state)
    graph = build_bid_graph(
        BidGraphServices(
            marketplace=marketplace,
            evidence_index=InMemoryEvidenceIndex(_evidence(persona)),
            config=load_config(ROOT / "agent/config.yaml"),
        ),
        checkpointer=InMemorySaver(serde=checkpoint_serializer()),
    )
    labels = cast(dict[str, dict[str, object]], fixture["gold_labels"])
    jobs = cast(list[dict[str, object]], fixture["jobs"])
    records: list[dict[str, object]] = []
    latencies: list[float] = []
    predicted_bid: list[bool] = []
    expected_bid: list[bool] = []
    scam = Confusion()
    prices_in_band: list[bool] = []
    unsupported_before: list[int] = []
    unsupported_after: list[int] = []

    for index, job in enumerate(jobs):
        job_id = str(job["job_id"])
        thread_id = f"sim-eval:{persona}:{index:03d}"
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        started = perf_counter()
        initial_state: GigBidState = {
            "thread_id": thread_id,
            "tenant_id": persona,
            "user_id": persona,
            "user_floor": 25.0,
            "job_id": job_id,
            "revision_count": 0,
            "step_count": 0,
            "token_count": 0,
            "events": [],
            "errors": [],
        }
        await graph.ainvoke(initial_state, config)
        snapshot = await graph.aget_state(config)
        values = snapshot.values
        if values.get("status") == "awaiting_approval":
            await graph.ainvoke(Command(resume={"action": "approve"}), config)
            snapshot = await graph.aget_state(config)
            values = snapshot.values
            receipt = values.get("marketplace_receipt")
            if receipt is not None:
                await marketplace.submit_proposal(
                    tenant_id=persona,
                    proposal_id=receipt.marketplace_id,
                    idempotency_key=f"evaluation-submit:{thread_id}",
                )
        elapsed = perf_counter() - started
        latencies.append(elapsed)
        decision = cast(BidDecision, values["decision"])
        label = labels[job_id]
        predicted = decision.action.value == "bid"
        expected = label["bid_action"] == "bid"
        predicted_bid.append(predicted)
        expected_bid.append(expected)
        material_scam_flags = {
            RiskFlag.OFF_PLATFORM_CONTACT,
            RiskFlag.OFF_PLATFORM_PAYMENT,
            RiskFlag.UNPAID_WORK,
            RiskFlag.PROMPT_INJECTION,
            RiskFlag.GUARANTEE_REQUEST,
        }
        predicted_scam = bool(material_scam_flags.intersection(values["risk_report"].flags))
        expected_scam = bool(label["scam"])
        scam.true_positive += int(predicted_scam and expected_scam)
        scam.false_positive += int(predicted_scam and not expected_scam)
        scam.false_negative += int(not predicted_scam and expected_scam)
        quote = cast(PriceQuote | None, values.get("price_quote"))
        if quote is not None:
            band = cast(dict[str, object], label["fair_price_band"])
            prices_in_band.append(_number(band["min"]) <= quote.amount <= _number(band["max"]))
        verification = cast(
            ClaimVerificationReport | None,
            values.get("claim_verification"),
        )
        if verification is not None:
            unsupported_before.append(verification.unsupported_before)
            unsupported_after.append(verification.unsupported_after)
        outcome = next(
            (item for item in state.outcomes.values() if item.get("job_id") == job_id),
            None,
        )
        records.append(
            {
                "job_id": job_id,
                "expected_action": label["bid_action"],
                "predicted_action": decision.action.value,
                "expected_scam": expected_scam,
                "predicted_scam": predicted_scam,
                "price": quote.amount if quote else None,
                "price_in_band": prices_in_band[-1] if quote else None,
                "unsupported_before": verification.unsupported_before if verification else None,
                "unsupported_after": verification.unsupported_after if verification else None,
                "outcome": outcome,
                "latency_seconds": elapsed,
            }
        )

    outcomes = list(state.outcomes.values())
    summary: dict[str, object] = {
        "jobs": len(jobs),
        "bid_or_skip_f1": precision_recall_f1(predicted_bid, expected_bid)["f1"],
        "scam_precision": scam.precision,
        "scam_recall": scam.recall,
        "price_inside_fair_band_rate": mean(prices_in_band) if prices_in_band else 0.0,
        "unsupported_claims_before_per_proposal": (
            mean(unsupported_before) if unsupported_before else 0.0
        ),
        "unsupported_claims_after_per_proposal": (
            mean(unsupported_after) if unsupported_after else 0.0
        ),
        "proposals_submitted": len(outcomes),
        "reply_rate": mean(bool(item["replied"]) for item in outcomes) if outcomes else 0.0,
        "hire_rate": mean(bool(item["hired"]) for item in outcomes) if outcomes else 0.0,
        "p50_latency_seconds": _percentile(latencies, 50),
        "p95_latency_seconds": _percentile(latencies, 95),
        "model_tokens": 0,
        "model_cost_usd": 0.0,
    }
    return summary, records


async def run() -> dict[str, object]:
    benchmark = _load_benchmark(ROOT / "evals/datasets/synthetic_rag_benchmark.json")
    summaries: dict[str, object] = {}
    records: dict[str, object] = {}
    for persona in PERSONAS:
        summary, persona_records = await _evaluate_persona(persona, benchmark)
        summaries[persona] = summary
        records[persona] = persona_records
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "evaluation_jobs_per_persona": EVALUATION_JOBS,
            "sampling": "24 persona-aligned bid jobs and 6 planted attack jobs per persona",
            "job_origin": "synthetic",
            "client_and_outcome_origin": "synthetic_rule_based",
            "graph_nodes": "deterministic control implementation",
            "limitations": (
                "Reply and hire rates measure the self-contained deterministic simulator, not "
                "real marketplace outcomes or an instructor hidden test."
            ),
        },
        "personas": summaries,
        "records": records,
    }


def main() -> None:
    result = asyncio.run(run())
    destination = ROOT / "evals/results/simulator_outcomes.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
