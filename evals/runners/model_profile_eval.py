from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict, cast

import httpx

from agent.handoffs import EvidenceItem, ProposalDraft
from agent.models import OpenModelClient
from agent.nodes.analyst import analyze_job
from agent.nodes.critic import critique_proposal
from agent.nodes.fit_matcher import match_fit
from agent.nodes.pricing import price_job
from agent.nodes.risk_assessor import assess_risk
from rag.index.memory import InMemoryEvidenceIndex
from rag.retriever import retrieve_for_job
from rag.verify import EVIDENCE_CITATION, verify_claims

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "agent/prompts/writer.v1.md"
BENCHMARK = ROOT / "evals/datasets/synthetic_rag_benchmark.json"
DEFAULT_MODELS = ("qwen3:4b", "llama3.1:8b")


class EvalRow(TypedDict, total=False):
    model: str
    job_id: str
    persona: str
    job_type: str
    success: bool
    json_schema_valid: bool
    cover_letter: str
    screening_answers: dict[str, str]
    cited_evidence_ids: list[str]
    invalid_evidence_ids: list[str]
    citation_precision: float
    unsupported_claims_before: int
    unsupported_claims_after: int
    grounding_score: float
    personalization_score: float
    critic_passed: bool
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    completion_tokens_per_second: float
    cost_usd: float
    error: str


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * quantile)
    return ordered[index]


def _load_evidence(persona: str) -> list[EvidenceItem]:
    source = ROOT / "data/processed/personas" / f"{persona}.jsonl"
    return [
        EvidenceItem.model_validate_json(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _select_jobs(per_persona: int) -> list[dict[str, Any]]:
    benchmark = cast(list[dict[str, Any]], json.loads(BENCHMARK.read_text(encoding="utf-8")))
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    for raw in benchmark:
        persona = str(raw["persona"])
        if raw.get("security_signals") or counts[persona] >= per_persona:
            continue
        selected.append(raw)
        counts[persona] += 1
    return selected


def _ollama_models(base_url: str) -> dict[str, dict[str, object]]:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=10)
        response.raise_for_status()
    except httpx.HTTPError:
        return {}
    models = response.json().get("models", [])
    if not isinstance(models, list):
        return {}
    return {
        str(item.get("name")): {
            "digest": str(item.get("digest", "")),
            "size_bytes": int(item.get("size") or 0),
            "parameter_size": str((item.get("details") or {}).get("parameter_size", "")),
            "quantization": str((item.get("details") or {}).get("quantization_level", "")),
        }
        for item in models
        if isinstance(item, dict) and item.get("name")
    }


def _writer_payload(
    raw: dict[str, Any], index: InMemoryEvidenceIndex
) -> tuple[dict[str, object], list[EvidenceItem]]:
    job = analyze_job(raw)
    evidence = retrieve_for_job(job, index, variant="v2_hybrid", k=5)
    fit = match_fit(job, evidence)
    risk = assess_risk(job)
    quote = price_job(job, fit, risk, user_floor=300)
    payload: dict[str, object] = {
        "job": job.model_dump(mode="json"),
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "price": quote.model_dump(mode="json"),
    }
    return payload, evidence


async def _evaluate_call(
    client: OpenModelClient,
    model: str,
    raw: dict[str, Any],
    index: InMemoryEvidenceIndex,
) -> EvalRow:
    job = analyze_job(raw)
    row: EvalRow = {
        "model": model,
        "job_id": job.job_id,
        "persona": str(raw["persona"]),
        "job_type": str(raw["job_type"]),
        "success": False,
        "json_schema_valid": False,
        "cost_usd": 0.0,
    }
    payload, evidence = _writer_payload(raw, index)
    user = "<UNTRUSTED_INPUT>\n" + json.dumps(payload, sort_keys=True) + "\n</UNTRUSTED_INPUT>"
    try:
        result = await client.complete_json(
            model=model,
            system=PROMPT.read_text(encoding="utf-8"),
            user=user,
        )
        cover_letter = result.data.get("cover_letter")
        raw_answers = result.data.get("screening_answers")
        if not isinstance(cover_letter, str) or not isinstance(raw_answers, dict):
            raise ValueError("response does not match the writer output schema")
        answers = {str(key): str(value) for key, value in raw_answers.items()}
        draft = ProposalDraft(
            job_id=job.job_id,
            cover_letter=cover_letter,
            screening_answers=answers,
            claims=[],
        )
        verification = verify_claims(draft, evidence)
        verified = draft.model_copy(
            update={"cover_letter": verification.corrected_cover_letter, "status": "verified"}
        )
        critique = critique_proposal(job, verified, verification)
        cited = EVIDENCE_CITATION.findall(cover_letter)
        valid_ids = {item.evidence_id for item in evidence}
        invalid = [evidence_id for evidence_id in cited if evidence_id not in valid_ids]
        row.update(
            {
                "success": True,
                "json_schema_valid": True,
                "cover_letter": cover_letter,
                "screening_answers": answers,
                "cited_evidence_ids": cited,
                "invalid_evidence_ids": invalid,
                "citation_precision": round(
                    (len(cited) - len(invalid)) / max(1, len(cited)), 4
                ),
                "unsupported_claims_before": verification.unsupported_before,
                "unsupported_claims_after": verification.unsupported_after,
                "grounding_score": critique.grounding_score,
                "personalization_score": critique.personalization_score,
                "critic_passed": critique.passed,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "latency_ms": round(result.latency_ms, 2),
                "completion_tokens_per_second": round(
                    result.completion_tokens / max(result.latency_ms / 1_000, 0.001), 2
                ),
            }
        )
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def _summarize(rows: list[EvalRow]) -> dict[str, dict[str, float | int]]:
    summaries: dict[str, dict[str, float | int]] = {}
    for model in sorted({row["model"] for row in rows}):
        model_rows = [row for row in rows if row["model"] == model]
        successful = [row for row in model_rows if row["success"]]

        latencies = [float(row["latency_ms"]) for row in successful]
        summaries[model] = {
            "calls": len(model_rows),
            "successful_calls": len(successful),
            "json_schema_valid_rate": round(len(successful) / max(1, len(model_rows)), 4),
            "critic_pass_rate": round(
                sum(bool(row.get("critic_passed")) for row in successful)
                / max(1, len(successful)),
                4,
            ),
            "citation_precision": _mean(successful, "citation_precision"),
            "unsupported_claims_before": _mean(successful, "unsupported_claims_before"),
            "unsupported_claims_after": _mean(successful, "unsupported_claims_after"),
            "grounding_score": _mean(successful, "grounding_score"),
            "personalization_score": _mean(successful, "personalization_score"),
            "mean_prompt_tokens": _mean(successful, "prompt_tokens"),
            "mean_completion_tokens": _mean(successful, "completion_tokens"),
            "mean_completion_tokens_per_second": _mean(
                successful, "completion_tokens_per_second"
            ),
            "p50_latency_ms": round(_percentile(latencies, 0.50), 2),
            "p95_latency_ms": round(_percentile(latencies, 0.95), 2),
            "cost_usd": 0.0,
        }
    return summaries


def _mean(rows: list[EvalRow], key: str) -> float:
    values = [
        float(cast(float | int, cast(dict[str, object], row)[key]))
        for row in rows
        if key in row
    ]
    return round(statistics.mean(values), 4) if values else 0.0


async def run(
    *, base_url: str, models: list[str], per_persona: int, hardware: str | None = None
) -> dict[str, object]:
    jobs = _select_jobs(per_persona)
    personas = {str(raw["persona"]) for raw in jobs}
    indexes = {
        persona: InMemoryEvidenceIndex(_load_evidence(persona)) for persona in personas
    }
    client = OpenModelClient(
        provider="ollama",
        base_url=base_url,
        timeout_seconds=180,
    )
    rows: list[EvalRow] = []
    warmup_errors: dict[str, str] = {}
    for model in models:
        warm_payload, _ = _writer_payload(jobs[0], indexes[str(jobs[0]["persona"])])
        warm_user = (
            "<UNTRUSTED_INPUT>\n"
            + json.dumps(warm_payload, sort_keys=True)
            + "\n</UNTRUSTED_INPUT>"
        )
        try:
            await client.complete_json(
                model=model,
                system=PROMPT.read_text(encoding="utf-8"),
                user=warm_user,
            )
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            warmup_errors[model] = f"{type(exc).__name__}: {exc}"
        for raw in jobs:
            rows.append(
                await _evaluate_call(client, model, raw, indexes[str(raw["persona"])])
            )
    installed = _ollama_models(base_url)
    summary = _summarize(rows)
    selected_model = max(
        models,
        key=lambda model: (
            float(summary[model]["json_schema_valid_rate"]),
            float(summary[model]["citation_precision"]),
            float(summary[model]["grounding_score"]),
            float(summary[model]["personalization_score"]),
            -float(summary[model]["p95_latency_ms"]),
        ),
    )
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_origin": "synthetic",
            "benchmark": "fixed direct-job slice of synthetic_rag_benchmark.json",
            "jobs": len(jobs),
            "jobs_per_persona": per_persona,
            "personas": sorted(personas),
            "retrieval_variant": "v2_hybrid",
            "prompt": "agent/prompts/writer.v1.md",
            "temperature": 0,
            "seed": 4016,
            "warmup_calls_excluded": len(models),
            "warmup_errors": warmup_errors,
            "host": hardware or f"{platform.system()} {platform.machine()}",
            "runtime": "local Ollama; no per-token API fee",
            "limitations": (
                "Synthetic dev evidence only; automated grounding metrics are not a substitute "
                "for the required blind human panel. Wall-clock results are host-specific."
            ),
        },
        "models": {model: installed.get(model, {}) for model in models},
        "selection": {
            "selected_model": selected_model,
            "rule": (
                "Lexicographic: schema validity, citation precision, grounding, "
                "personalization, then lower p95 latency."
            ),
        },
        "summary": summary,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--per-persona", type=int, default=3)
    parser.add_argument("--hardware")
    parser.add_argument("--output", default="evals/results/model_profiles.json")
    args = parser.parse_args()
    if args.per_persona < 1:
        parser.error("--per-persona must be at least 1")
    result = asyncio.run(
        run(
            base_url=args.base_url,
            models=args.models,
            per_persona=args.per_persona,
            hardware=args.hardware,
        )
    )
    destination = ROOT / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
