from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import httpx
from fastapi import APIRouter, Depends

from apps.api.auth.security import AuthenticatedUser
from apps.api.context import AppContext
from apps.api.dependencies import get_context, get_current_user
from apps.api.schemas.api import (
    AnalyticsCategory,
    AnalyticsPersona,
    AnalyticsResponse,
    ConversationSummary,
    MessagesResponse,
    PipelineCard,
    PipelineResponse,
    RagVariantMetric,
)
from mcp_servers.marketplace.adapters.memory import InMemoryMarketplaceAdapter

ROOT = Path(__file__).resolve().parents[3]
router = APIRouter(tags=["product"])


def _result(path: str) -> dict[str, Any]:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path}")
    return cast(dict[str, Any], value)


def _analytics_breakdowns(
    outcomes: dict[str, Any],
) -> tuple[dict[str, AnalyticsCategory], int, dict[str, int]]:
    dataset_value = json.loads(
        (ROOT / "evals/datasets/synthetic_rag_benchmark.json").read_text(encoding="utf-8")
    )
    if not isinstance(dataset_value, list) or not all(
        isinstance(item, dict) for item in dataset_value
    ):
        raise ValueError("Synthetic RAG benchmark must be a list of objects")
    jobs = {str(item["job_id"]): cast(dict[str, Any], item) for item in dataset_value}
    raw_records = outcomes.get("records")
    if not isinstance(raw_records, dict):
        raise ValueError("Simulator outcomes must contain persona records")

    category_counts: dict[str, dict[str, int]] = {}
    rejection_reasons: Counter[str] = Counter()
    connects_spent = 0
    for persona_records in raw_records.values():
        if not isinstance(persona_records, list):
            continue
        for untyped_record in persona_records:
            if not isinstance(untyped_record, dict):
                continue
            record = cast(dict[str, Any], untyped_record)
            job = jobs.get(str(record.get("job_id")), {})
            action = str(record.get("predicted_action", ""))
            if action == "bid":
                raw_connects = job.get("connects_cost", 0)
                if isinstance(raw_connects, (int, float)):
                    connects_spent += int(raw_connects)
            elif action == "skip":
                signals = job.get("security_signals", [])
                if isinstance(signals, list):
                    rejection_reasons.update(str(signal) for signal in signals)

            outcome = record.get("outcome")
            if not isinstance(outcome, dict):
                continue
            category = str(outcome.get("category") or job.get("job_type") or "unknown")
            counts = category_counts.setdefault(
                category,
                {"proposals": 0, "replies": 0, "hires": 0, "connects": 0},
            )
            counts["proposals"] += 1
            counts["replies"] += int(bool(outcome.get("replied")))
            counts["hires"] += int(bool(outcome.get("hired")))
            raw_connects = job.get("connects_cost", 0)
            if isinstance(raw_connects, (int, float)):
                counts["connects"] += int(raw_connects)

    categories = {
        name: AnalyticsCategory(
            proposals=counts["proposals"],
            reply_rate=counts["replies"] / max(1, counts["proposals"]),
            hire_rate=counts["hires"] / max(1, counts["proposals"]),
            connects_spent=counts["connects"],
        )
        for name, counts in sorted(
            category_counts.items(), key=lambda item: (-item[1]["proposals"], item[0])
        )
    }
    return categories, connects_spent, dict(rejection_reasons.most_common())


async def _simulator_get(path: str) -> list[dict[str, object]]:
    base_url = os.getenv("GIGSIM_BASE_URL", "http://gigsim:8081").rstrip("/")
    token = os.getenv("GIGSIM_API_TOKEN", "gigsim-development-token")
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
        response = await client.get(path, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
    value = response.json()
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Simulator {path} response must be a list of objects")
    return [{str(key): item for key, item in record.items()} for record in value]


@router.get("/analytics", response_model=AnalyticsResponse)
async def analytics(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AnalyticsResponse:
    del user
    outcomes = _result("evals/results/simulator_outcomes.json")
    rag = _result("evals/results/synthetic_rag.json")
    raw_personas = cast(dict[str, dict[str, object]], outcomes["personas"])
    raw_variants = cast(dict[str, dict[str, object]], rag["overall"])
    categories, connects_spent, top_rejection_reasons = _analytics_breakdowns(outcomes)
    return AnalyticsResponse(
        generated_at=str(cast(dict[str, object], outcomes["metadata"])["generated_at"]),
        scope="Synthetic simulator outcomes and synthetic persona retrieval benchmark",
        personas={
            name: AnalyticsPersona.model_validate(values) for name, values in raw_personas.items()
        },
        rag_variants={
            name: RagVariantMetric.model_validate(values) for name, values in raw_variants.items()
        },
        categories=categories,
        connects_spent=connects_spent,
        top_rejection_reasons=top_rejection_reasons,
    )


@router.get("/pipeline", response_model=PipelineResponse)
async def pipeline(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> PipelineResponse:
    cards: list[PipelineCard] = []
    if isinstance(context.marketplace, InMemoryMarketplaceAdapter):
        proposals = [
            {**payload, "proposal_id": proposal_id, "status": "drafted"}
            for proposal_id, payload in context.marketplace.proposals.items()
        ]
        outcomes: list[dict[str, object]] = []
    else:
        proposals = await _simulator_get("/proposals")
        outcomes = await _simulator_get("/outcomes")
    outcome_by_proposal = {str(item["proposal_id"]): item for item in outcomes}
    for proposal in proposals:
        if str(proposal.get("tenant_id", user.tenant_id)) != user.tenant_id:
            continue
        proposal_id = str(proposal["proposal_id"])
        job_id = str(proposal["job_id"])
        job = await context.marketplace.get_job(tenant_id=user.tenant_id, job_id=job_id)
        outcome = outcome_by_proposal.get(proposal_id)
        status = _pipeline_status(str(proposal.get("status", "drafted")), outcome)
        cards.append(
            PipelineCard(
                proposal_id=proposal_id,
                job_id=job_id,
                title=str(job.get("title", job_id)),
                status=status,
                connects_spent=_as_int(job.get("connects_cost", 0)),
                data_origin=(
                    str(outcome.get("data_origin")) if outcome else "local_application_state"
                ),
            )
        )
    return PipelineResponse(cards=cards)


def _pipeline_status(
    proposal_status: str, outcome: dict[str, object] | None
) -> Literal["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]:
    if outcome:
        if outcome.get("hired"):
            return "hired"
        if outcome.get("interviewed"):
            return "interview"
        if outcome.get("replied"):
            return "replied"
        if outcome.get("viewed"):
            return "viewed"
    return "submitted" if proposal_status == "submitted" else "drafted"


def _as_int(value: object) -> int:
    if not isinstance(value, (str, int, float)):
        raise ValueError("Expected a numeric pipeline field")
    return int(value)


@router.get("/messages", response_model=MessagesResponse)
async def messages(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> MessagesResponse:
    raw_threads: list[dict[str, object]]
    if isinstance(context.marketplace, InMemoryMarketplaceAdapter):
        raw_threads = [
            {"conversation_id": key, "messages": value}
            for key, value in context.marketplace.messages.items()
        ]
    else:
        raw_threads = await _simulator_get("/conversations")
    threads = [
        ConversationSummary(
            conversation_id=str(item["conversation_id"]),
            proposal_id=(str(item["proposal_id"]) if item.get("proposal_id") else None),
            client_name="Synthetic marketplace client",
            messages=cast(list[dict[str, object]], item.get("messages", [])),
        )
        for item in raw_threads
    ]
    del user
    return MessagesResponse(threads=threads)
