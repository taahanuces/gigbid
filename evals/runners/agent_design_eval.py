from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from agent.handoffs import (
    BidDecision,
    EvidenceItem,
    FitReport,
    JobSpec,
    RiskFlag,
    RiskReport,
)
from agent.nodes.analyst import analyze_job
from agent.nodes.decision import decide_bid
from agent.nodes.fit_matcher import match_fit
from agent.nodes.risk_assessor import assess_risk
from rag.index.memory import InMemoryEvidenceIndex
from rag.retriever import retrieve_for_job

ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURES = ("hand_built", "supervisor", "react_style")


@dataclass(frozen=True, slots=True)
class ArchitectureOutput:
    job: JobSpec
    risk: RiskReport
    fit: FitReport
    decision: BidDecision
    control_steps: int
    trace: list[str]


@dataclass(frozen=True, slots=True)
class EvaluationRow:
    job_id: str
    architecture: str
    category: str
    expected_injection_signal: bool
    injection_detected: bool
    action: str
    risk_score: float
    fit_score: float
    control_steps: int
    latency_ms: float
    completed: bool
    external_writes: int
    trace: list[str]


def evaluate_nodes(
    raw: dict[str, Any], index: InMemoryEvidenceIndex
) -> tuple[JobSpec, RiskReport, FitReport, BidDecision]:
    job = analyze_job(raw)
    history = raw.get("client_history")
    risk = assess_risk(job, cast(dict[str, object], history) if isinstance(history, dict) else None)
    evidence = retrieve_for_job(job, index, variant="v0_naive", k=5)
    fit = match_fit(job, evidence)
    return job, risk, fit, decide_bid(job, risk, fit)


def hand_built(raw: dict[str, Any], index: InMemoryEvidenceIndex) -> ArchitectureOutput:
    job, risk, fit, decision = evaluate_nodes(raw, index)
    return ArchitectureOutput(
        job=job,
        risk=risk,
        fit=fit,
        decision=decision,
        control_steps=4,
        trace=["analyze", "parallel(risk,fit)", "join", "decide"],
    )


def supervisor(raw: dict[str, Any], index: InMemoryEvidenceIndex) -> ArchitectureOutput:
    trace = ["supervisor->analyst"]
    job = analyze_job(raw)
    trace.append("supervisor->risk")
    history = raw.get("client_history")
    risk = assess_risk(job, cast(dict[str, object], history) if isinstance(history, dict) else None)
    trace.append("supervisor->fit")
    evidence = retrieve_for_job(job, index, variant="v0_naive", k=5)
    fit = match_fit(job, evidence)
    trace.append("supervisor->decision")
    decision = decide_bid(job, risk, fit)
    return ArchitectureOutput(
        job=job,
        risk=risk,
        fit=fit,
        decision=decision,
        control_steps=8,
        trace=trace,
    )


def react_style(raw: dict[str, Any], index: InMemoryEvidenceIndex) -> ArchitectureOutput:
    job: JobSpec | None = None
    risk: RiskReport | None = None
    fit: FitReport | None = None
    decision: BidDecision | None = None
    trace: list[str] = []
    history = raw.get("client_history")
    while decision is None:
        if job is None:
            trace.extend(["thought:need_job_spec", "action:analyze"])
            job = analyze_job(raw)
        elif risk is None:
            trace.extend(["thought:need_safety", "action:assess_risk"])
            risk = assess_risk(
                job,
                cast(dict[str, object], history) if isinstance(history, dict) else None,
            )
        elif fit is None:
            trace.extend(["thought:need_evidence", "action:retrieve_and_match"])
            evidence = retrieve_for_job(job, index, variant="v0_naive", k=5)
            fit = match_fit(job, evidence)
        else:
            trace.extend(["thought:ready_to_decide", "action:decide"])
            decision = decide_bid(job, risk, fit)
    assert job is not None
    assert risk is not None
    assert fit is not None
    return ArchitectureOutput(
        job=job,
        risk=risk,
        fit=fit,
        decision=decision,
        control_steps=len(trace),
        trace=trace,
    )


RUNNERS: dict[str, Callable[[dict[str, Any], InMemoryEvidenceIndex], ArchitectureOutput]] = {
    "hand_built": hand_built,
    "supervisor": supervisor,
    "react_style": react_style,
}


def load_jobs() -> tuple[list[dict[str, Any]], dict[str, dict[str, object]]]:
    selection = json.loads(
        (ROOT / "evals/datasets/agent_design_jobs.json").read_text(encoding="utf-8")
    )
    labels = {str(item["job_id"]): item for item in selection["jobs"]}
    found: dict[str, dict[str, Any]] = {}
    source = ROOT / "data/processed/kaggle/jobs_dev.jsonl"
    if not source.exists():
        raise FileNotFoundError("Run make data-prepare before the agent-design evaluation")
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            job_id = str(row.get("job_id", ""))
            if job_id in labels:
                found[job_id] = cast(dict[str, Any], row)
    missing = sorted(set(labels).difference(found))
    if missing:
        raise ValueError(f"Missing {len(missing)} selected public jobs")
    return [found[job_id] for job_id in labels], labels


def load_index() -> InMemoryEvidenceIndex:
    evidence: list[EvidenceItem] = []
    for persona in ("ai-ml-engineer", "full-stack-developer", "data-analyst"):
        path = ROOT / f"data/processed/personas/{persona}.jsonl"
        if not path.exists():
            raise FileNotFoundError("Run make synthetic-data before the agent-design evaluation")
        evidence.extend(
            EvidenceItem.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return InMemoryEvidenceIndex(evidence)


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * quantile)] if ordered else 0.0


def run() -> dict[str, object]:
    jobs, labels = load_jobs()
    index = load_index()
    rows: list[EvaluationRow] = []
    decisions_by_job: dict[str, dict[str, str]] = defaultdict(dict)
    for architecture in ARCHITECTURES:
        runner = RUNNERS[architecture]
        for raw in jobs:
            job_id = str(raw["job_id"])
            started = time.perf_counter()
            output = runner(raw, index)
            latency_ms = (time.perf_counter() - started) * 1_000
            injection_detected = RiskFlag.PROMPT_INJECTION in output.risk.flags
            action = output.decision.action.value
            decisions_by_job[job_id][architecture] = action
            label = labels[job_id]
            rows.append(
                EvaluationRow(
                    job_id=job_id,
                    architecture=architecture,
                    category=str(label["category"]),
                    expected_injection_signal=bool(label["expected_injection_signal"]),
                    injection_detected=injection_detected,
                    action=action,
                    risk_score=output.risk.score,
                    fit_score=output.fit.score,
                    control_steps=output.control_steps,
                    latency_ms=latency_ms,
                    completed=True,
                    external_writes=0,
                    trace=output.trace,
                )
            )

    summary: dict[str, dict[str, object]] = {}
    for architecture in ARCHITECTURES:
        items = [row for row in rows if row.architecture == architecture]
        flagged = [row for row in items if row.expected_injection_signal]
        latencies = [row.latency_ms for row in items]
        summary[architecture] = {
            "jobs": len(items),
            "completion_rate": sum(row.completed for row in items) / len(items),
            "injection_detection_recall": (
                sum(row.injection_detected for row in flagged) / len(flagged)
            ),
            "external_writes": sum(row.external_writes for row in items),
            "mean_control_steps": statistics.mean(row.control_steps for row in items),
            "p50_latency_ms": statistics.median(latencies),
            "p95_latency_ms": percentile(latencies, 0.95),
            "action_distribution": dict(Counter(row.action for row in items)),
        }
    unanimous = sum(len(set(actions.values())) == 1 for actions in decisions_by_job.values())
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "jobs": len(jobs),
            "data_origin": "real_public_dataset jobs plus explicitly synthetic portfolio evidence",
            "execution": "read-only deterministic control-policy baseline; no external writes",
            "limitations": (
                "ReAct-style and supervisor policies use deterministic routing, not LLM planning; "
                "public data has no decision or outcome ground truth."
            ),
            "gigsim_metrics": None,
            "retrieval_variant": "v0_naive for every architecture",
        },
        "summary": summary,
        "decision_unanimity": unanimous / len(decisions_by_job),
        "rows": [asdict(row) for row in rows],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evals/results/agent_design.json")
    args = parser.parse_args()
    result = run()
    destination = ROOT / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
