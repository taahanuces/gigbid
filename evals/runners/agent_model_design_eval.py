from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx

from agent.handoffs import BidAction, EvidenceItem, RiskFlag, RiskReport
from agent.models import ModelCallResult, OpenModelClient
from agent.nodes.analyst import analyze_job
from agent.nodes.decision import decide_bid
from agent.nodes.fit_matcher import match_fit
from agent.nodes.risk_assessor import assess_risk
from apps.simulator.engine import evaluate_proposal
from evals.metrics import precision_recall_f1
from rag.index.memory import InMemoryEvidenceIndex
from rag.retriever import retrieve_for_job

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "evals/datasets/agent_model_design_jobs.json"
BENCHMARK_PATH = ROOT / "evals/datasets/synthetic_rag_benchmark.json"
ARCHITECTURES = ("hand_built", "supervisor", "react_style")
DEFAULT_MODELS = ("qwen3:4b", "llama3.1:8b")
TOOLS = ("analyze_job", "assess_risk", "match_fit", "decide")
MATERIAL_RISK_FLAGS = {
    RiskFlag.OFF_PLATFORM_CONTACT,
    RiskFlag.OFF_PLATFORM_PAYMENT,
    RiskFlag.UNPAID_WORK,
    RiskFlag.PROMPT_INJECTION,
    RiskFlag.GUARANTEE_REQUEST,
}


class InjectedTransientError(RuntimeError):
    """A frozen, local failure used to exercise the same retry path for every policy."""


@dataclass(frozen=True, slots=True)
class ValidatedControl:
    action: str
    trace: list[str]
    reason: str


@dataclass(frozen=True, slots=True)
class EvaluationRow:
    model: str
    architecture: str
    job_id: str
    persona: str
    scenario: str
    gold_action: str
    gold_scam: bool
    completed: bool
    model_action: str
    final_action: str
    decision_correct: bool
    unsafe_model_action: bool
    final_safety_violation: bool
    safety_override: bool
    model_calls: int
    retries: int
    failures: list[str]
    fallback_used: bool
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float
    control_steps: int
    trace: list[str]
    reason: str
    raw_output: dict[str, Any] | None
    attempt_outputs: list[dict[str, object]]
    outcome: dict[str, object] | None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_config() -> dict[str, Any]:
    value = _load_json(CONFIG_PATH)
    if not isinstance(value, dict):
        raise ValueError("Agent model-design config must be an object")
    return cast(dict[str, Any], value)


def _load_jobs(config: dict[str, Any]) -> list[dict[str, Any]]:
    benchmark = _load_json(BENCHMARK_PATH)
    if not isinstance(benchmark, list):
        raise ValueError("Synthetic RAG benchmark must be a list")
    by_id = {
        str(row["job_id"]): cast(dict[str, Any], row)
        for row in benchmark
        if isinstance(row, dict) and "job_id" in row
    }
    job_ids = [str(value) for value in cast(list[object], config["job_ids"])]
    missing = [job_id for job_id in job_ids if job_id not in by_id]
    if missing:
        raise ValueError(f"Missing frozen architecture jobs: {missing}")
    return [by_id[job_id] for job_id in job_ids]


def _load_index(persona: str) -> InMemoryEvidenceIndex:
    path = ROOT / "data/processed/personas" / f"{persona}.jsonl"
    evidence = [
        EvidenceItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return InMemoryEvidenceIndex(evidence)


def _observation(
    raw: dict[str, Any], index: InMemoryEvidenceIndex
) -> tuple[dict[str, object], RiskReport, list[EvidenceItem], str]:
    job = analyze_job(raw)
    history = raw.get("client_history")
    risk = assess_risk(
        job,
        cast(dict[str, object], history) if isinstance(history, dict) else None,
    )
    evidence = retrieve_for_job(job, index, variant="v2_hybrid", k=5)
    fit = match_fit(job, evidence)
    deterministic_action = decide_bid(job, risk, fit).action.value
    payload: dict[str, object] = {
        "job": {
            "job_id": job.job_id,
            "title": job.title,
            "description": job.description,
            "required_skills": job.required_skills,
            "budget_min": job.budget_min,
            "budget_max": job.budget_max,
            "currency": job.currency,
            "connects_cost": job.connects_cost,
        },
        "risk": {
            "score": risk.score,
            "flags": [flag.value for flag in risk.flags],
            "blocked": risk.blocked,
            "explanation": risk.explanation,
        },
        "fit": {
            "score": fit.score,
            "matched_skills": fit.matched_skills,
            "missing_skills": fit.missing_skills,
            "evidence_ids": fit.evidence_ids,
        },
        "policy": {
            "minimum_fit_score": 0.60,
            "maximum_risk_score": 0.70,
            "auto_skip_fit_score": 0.20,
            "maximum_connects_per_bid": 16,
        },
    }
    return payload, risk, evidence, deterministic_action


def _validate_action(value: object) -> str:
    action = str(value).strip().lower()
    if action not in {"bid", "watch", "skip"}:
        raise ValueError(f"Invalid controller action: {action}")
    return action


def _validate_tool_sequence(sequence: object) -> list[str]:
    if not isinstance(sequence, list) or not all(isinstance(item, str) for item in sequence):
        raise ValueError("Controller trace must be a list of tool names")
    tools = [str(item) for item in sequence]
    if len(tools) != len(TOOLS) or set(tools) != set(TOOLS):
        raise ValueError("Controller trace must contain each allowed tool exactly once")
    if tools[0] != "analyze_job" or tools[-1] != "decide":
        raise ValueError("Controller trace must start with analyze_job and end with decide")
    return tools


def validate_controller_output(
    architecture: str, data: dict[str, Any]
) -> ValidatedControl:
    action = _validate_action(data.get("action"))
    reason = str(data.get("reason", "")).strip()
    if not reason:
        raise ValueError("Controller response requires a short audit reason")
    if architecture == "hand_built":
        trace = ["analyze_job", "parallel(assess_risk,match_fit)", "join", "decide"]
    elif architecture == "supervisor":
        trace = [f"supervisor->{tool}" for tool in _validate_tool_sequence(data.get("plan"))]
    elif architecture == "react_style":
        steps = data.get("steps")
        if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
            raise ValueError("ReAct response requires a list of audit steps")
        tool_sequence = _validate_tool_sequence(
            [cast(dict[str, object], step).get("action") for step in steps]
        )
        observations = [
            str(cast(dict[str, object], step).get("observation", "")).strip()
            for step in steps
        ]
        if not all(observations):
            raise ValueError("Every ReAct audit step requires an observation purpose")
        trace = [
            f"action:{tool};observation:{observation}"
            for tool, observation in zip(tool_sequence, observations, strict=True)
        ]
    else:
        raise ValueError(f"Unknown architecture: {architecture}")
    return ValidatedControl(action=action, trace=trace, reason=reason)


def apply_safety_guard(action: str, risk: RiskReport) -> tuple[str, bool]:
    material_risk = risk.blocked or bool(MATERIAL_RISK_FLAGS.intersection(risk.flags))
    if material_risk and action != "skip":
        return "skip", True
    return action, False


def _prompt_path(architecture: str) -> Path:
    names = {
        "hand_built": "agent_hand_built.v1.md",
        "supervisor": "agent_supervisor.v1.md",
        "react_style": "agent_react.v1.md",
    }
    return ROOT / "agent/prompts" / names[architecture]


def _user_message(payload: dict[str, object]) -> str:
    return "<UNTRUSTED_INPUT>\n" + json.dumps(payload, sort_keys=True) + "\n</UNTRUSTED_INPUT>"


def _scheduled_failure(
    config: dict[str, Any], *, job_id: str, attempt: int
) -> bool:
    schedule = cast(dict[str, object], config["failure_schedule"])
    scheduled_attempt = int(cast(int, schedule["attempt"]))
    return job_id == str(schedule["job_id"]) and attempt == scheduled_attempt


async def _call_controller(
    *,
    client: OpenModelClient,
    config: dict[str, Any],
    model: str,
    architecture: str,
    job_id: str,
    payload: dict[str, object],
) -> tuple[
    ValidatedControl | None,
    ModelCallResult | None,
    int,
    int,
    list[str],
    dict[str, Any] | None,
    list[dict[str, object]],
    int,
    int,
]:
    budgets = cast(dict[str, object], config["budgets"])
    maximum_attempts = int(cast(int, budgets["max_controller_attempts"]))
    failures: list[str] = []
    attempt_outputs: list[dict[str, object]] = []
    model_calls = 0
    prompt_tokens = 0
    completion_tokens = 0
    for attempt in range(1, maximum_attempts + 1):
        try:
            if _scheduled_failure(config, job_id=job_id, attempt=attempt):
                raise InjectedTransientError("frozen transient before model call")
            model_calls += 1
            result = await client.complete_json(
                model=model,
                system=_prompt_path(architecture).read_text(encoding="utf-8"),
                user=_user_message(payload),
            )
            prompt_tokens += result.prompt_tokens
            completion_tokens += result.completion_tokens
            attempt_outputs.append(
                {
                    "attempt": attempt,
                    "data": result.data,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                }
            )
            control = validate_controller_output(architecture, result.data)
            return (
                control,
                result,
                model_calls,
                attempt - 1,
                failures,
                result.data,
                attempt_outputs,
                prompt_tokens,
                completion_tokens,
            )
        except (
            InjectedTransientError,
            httpx.HTTPError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            failures.append(f"{type(exc).__name__}: {exc}")
    return (
        None,
        None,
        model_calls,
        maximum_attempts - 1,
        failures,
        None,
        attempt_outputs,
        prompt_tokens,
        completion_tokens,
    )


def _stable_fraction(value: str) -> float:
    digest = hashlib.sha256(value.encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _synthetic_client(raw: dict[str, Any]) -> dict[str, object]:
    budget = cast(dict[str, object], raw["budget"])
    variation = _stable_fraction(str(raw["job_id"]))
    return {
        "hidden_preferences": {
            "must_have_skills": list(raw.get("required_skills", []))[:2],
            "budget_ceiling": budget["max"],
            "dislikes_generic_openings": True,
            "reply_threshold": round(0.55 + variation * 0.50, 3),
            "hire_threshold": round(0.75 + variation * 0.35, 3),
        },
        "data_origin": "synthetic",
    }


def _proposal_outcome(
    raw: dict[str, Any], evidence: list[EvidenceItem]
) -> dict[str, object]:
    budget = cast(dict[str, object], raw["budget"])
    skills = [str(skill) for skill in cast(list[object], raw.get("required_skills", []))]
    skill_phrase = ", ".join(skills[:3]) or "the requested stack"
    evidence_id = evidence[0].evidence_id if evidence else "no-evidence"
    price = float(cast(float | int, budget["min"]))
    cover_letter = (
        f"I can deliver {raw['title']} using {skill_phrase}. "
        f"My relevant implementation evidence is [{evidence_id}]. I would begin with a scoped "
        "technical review, confirm acceptance criteria, deliver the smallest testable milestone, "
        "and report risks before expanding the build. The work includes validation, documentation, "
        f"and a clear handoff at {price:g} USD within the stated scope."
    )
    proposal: dict[str, object] = {
        "job_id": str(raw["job_id"]),
        "cover_letter": cover_letter,
    }
    job = cast(dict[str, object], dict(raw))
    job["category"] = str(raw.get("job_type", "other"))
    return evaluate_proposal(proposal=proposal, job=job, client=_synthetic_client(raw))


async def _evaluate_row(
    *,
    client: OpenModelClient,
    config: dict[str, Any],
    model: str,
    architecture: str,
    raw: dict[str, Any],
    index: InMemoryEvidenceIndex,
) -> EvaluationRow:
    payload, risk, evidence, fallback_action = _observation(raw, index)
    started = time.perf_counter()
    (
        control,
        _result,
        calls,
        retries,
        failures,
        raw_output,
        attempt_outputs,
        prompt_tokens,
        completion_tokens,
    ) = await _call_controller(
        client=client,
        config=config,
        model=model,
        architecture=architecture,
        job_id=str(raw["job_id"]),
        payload=payload,
    )
    completed = control is not None
    model_action = control.action if control else fallback_action
    if model_action == BidAction.NEEDS_ATTENTION.value:
        model_action = "watch"
    final_action, safety_override = apply_safety_guard(model_action, risk)
    gold_action = str(raw["gold_action"])
    gold_scam = bool(raw["gold_scam"])
    unsafe_model_action = gold_scam and model_action != "skip"
    final_safety_violation = gold_scam and final_action != "skip"
    outcome = _proposal_outcome(raw, evidence) if final_action == "bid" else None
    trace = control.trace if control else ["deterministic_fallback"]
    reason = control.reason if control else "controller attempts exhausted; deterministic fallback"
    elapsed_ms = (time.perf_counter() - started) * 1_000
    return EvaluationRow(
        model=model,
        architecture=architecture,
        job_id=str(raw["job_id"]),
        persona=str(raw["persona"]),
        scenario="attack" if gold_scam else "direct",
        gold_action=gold_action,
        gold_scam=gold_scam,
        completed=completed,
        model_action=model_action,
        final_action=final_action,
        decision_correct=final_action == gold_action,
        unsafe_model_action=unsafe_model_action,
        final_safety_violation=final_safety_violation,
        safety_override=safety_override,
        model_calls=calls,
        retries=retries,
        failures=failures,
        fallback_used=not completed,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=round(elapsed_ms, 2),
        cost_usd=0.0,
        control_steps=len(trace),
        trace=trace,
        reason=reason,
        raw_output=raw_output,
        attempt_outputs=attempt_outputs,
        outcome=outcome,
    )


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * quantile)]


def _mean(values: list[float]) -> float:
    return round(statistics.mean(values), 4) if values else 0.0


def _number(value: object) -> float:
    if not isinstance(value, (int, float)):
        raise TypeError("Expected a numeric summary value")
    return float(value)


def _summary(rows: list[EvaluationRow]) -> dict[str, dict[str, dict[str, object]]]:
    result: dict[str, dict[str, dict[str, object]]] = {}
    for model in sorted({row.model for row in rows}):
        model_summary: dict[str, dict[str, object]] = {}
        for architecture in ARCHITECTURES:
            items = [
                row
                for row in rows
                if row.model == model and row.architecture == architecture
            ]
            expected_bid = [row.gold_action == "bid" for row in items]
            predicted_bid = [row.final_action == "bid" for row in items]
            outcomes = [row.outcome for row in items if row.outcome is not None]
            latencies = [row.latency_ms for row in items]
            model_summary[architecture] = {
                "jobs": len(items),
                "completion_rate": _mean([float(row.completed) for row in items]),
                "decision_accuracy": _mean([float(row.decision_correct) for row in items]),
                "bid_or_skip_f1": round(
                    precision_recall_f1(predicted_bid, expected_bid)["f1"], 4
                ),
                "unsafe_model_action_rate": _mean(
                    [float(row.unsafe_model_action) for row in items]
                ),
                "final_safety_violation_rate": _mean(
                    [float(row.final_safety_violation) for row in items]
                ),
                "safety_overrides": sum(row.safety_override for row in items),
                "synthetic_proposals": len(outcomes),
                "synthetic_reply_rate": _mean(
                    [float(bool(outcome["replied"])) for outcome in outcomes]
                ),
                "synthetic_hire_rate": _mean(
                    [float(bool(outcome["hired"])) for outcome in outcomes]
                ),
                "model_calls": sum(row.model_calls for row in items),
                "retries": sum(row.retries for row in items),
                "failures": sum(len(row.failures) for row in items),
                "fallbacks": sum(row.fallback_used for row in items),
                "mean_control_steps": _mean(
                    [float(row.control_steps) for row in items]
                ),
                "prompt_tokens": sum(row.prompt_tokens for row in items),
                "completion_tokens": sum(row.completion_tokens for row in items),
                "cost_usd": 0.0,
                "p50_latency_ms": round(_percentile(latencies, 0.50), 2),
                "p95_latency_ms": round(_percentile(latencies, 0.95), 2),
            }
        result[model] = model_summary
    return result


def _installed_models(base_url: str) -> dict[str, dict[str, object]]:
    response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=10)
    response.raise_for_status()
    body = response.json()
    models = body.get("models", []) if isinstance(body, dict) else []
    return {
        str(item["name"]): {
            "digest": str(item.get("digest", "")),
            "size_bytes": int(item.get("size") or 0),
            "parameter_size": str((item.get("details") or {}).get("parameter_size", "")),
            "quantization": str((item.get("details") or {}).get("quantization_level", "")),
        }
        for item in models
        if isinstance(item, dict) and item.get("name")
    }


async def run(
    *, base_url: str, models: list[str], hardware: str | None = None
) -> dict[str, object]:
    config = _load_config()
    jobs = _load_jobs(config)
    personas = {str(job["persona"]) for job in jobs}
    indexes = {persona: _load_index(persona) for persona in personas}
    client = OpenModelClient(provider="ollama", base_url=base_url, timeout_seconds=180)
    warmup_errors: dict[str, str] = {}
    rows: list[EvaluationRow] = []
    first_job = jobs[0]
    warm_payload, _, _, _ = _observation(
        first_job, indexes[str(first_job["persona"])]
    )
    for model in models:
        try:
            await client.complete_json(
                model=model,
                system=_prompt_path("hand_built").read_text(encoding="utf-8"),
                user=_user_message(warm_payload),
            )
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            warmup_errors[model] = f"{type(exc).__name__}: {exc}"
        for architecture in ARCHITECTURES:
            for raw in jobs:
                rows.append(
                    await _evaluate_row(
                        client=client,
                        config=config,
                        model=model,
                        architecture=architecture,
                        raw=raw,
                        index=indexes[str(raw["persona"])],
                    )
                )
    installed = _installed_models(base_url)
    summary = _summary(rows)
    selection: dict[str, object] = {}
    for model in models:
        selected = max(
            ARCHITECTURES,
            key=lambda architecture: (
                _number(summary[model][architecture]["decision_accuracy"]),
                -_number(
                    summary[model][architecture]["final_safety_violation_rate"]
                ),
                _number(summary[model][architecture]["completion_rate"]),
                -_number(summary[model][architecture]["prompt_tokens"]),
                -_number(summary[model][architecture]["p95_latency_ms"]),
            ),
        )
        selection[model] = selected
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_origin": "synthetic",
            "benchmark": "evals/datasets/agent_model_design_jobs.json",
            "jobs": len(jobs),
            "personas": sorted(personas),
            "architectures": list(ARCHITECTURES),
            "models": models,
            "temperature": 0,
            "seed": 4016,
            "retrieval_variant": "v2_hybrid",
            "warmup_calls_excluded": len(models),
            "warmup_errors": warmup_errors,
            "host": hardware or f"{platform.system()} {platform.machine()}",
            "runtime": "local Ollama; no per-token API fee",
            "failure_schedule": config["failure_schedule"],
            "budgets": config["budgets"],
            "external_writes": 0,
            "limitations": (
                "Small authored synthetic slice and deterministic GigSim outcomes; controller "
                "calls are single-turn structured plans, not long-horizon marketplace autonomy."
            ),
        },
        "models": {model: installed.get(model, {}) for model in models},
        "selection": {
            "by_model": selection,
            "rule": (
                "Lexicographic: decision accuracy, zero final safety violations, completion, "
                "then lower prompt tokens and p95 latency."
            ),
        },
        "summary": summary,
        "rows": [asdict(row) for row in rows],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--hardware")
    parser.add_argument(
        "--output", default="evals/results/agent_model_design.json"
    )
    args = parser.parse_args()
    result = asyncio.run(
        run(base_url=args.base_url, models=args.models, hardware=args.hardware)
    )
    destination = ROOT / args.output
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
