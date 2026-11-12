from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import interrupt

from agent.config import AppConfig, load_config
from agent.handoffs import (
    ApprovalAction,
    ApprovalDecision,
    ApprovalPayload,
    BidAction,
    ProposalDraft,
)
from agent.marketplace_port import MarketplacePort
from agent.memory import LongTermMemory, infer_style_patterns
from agent.models import ModelRouter
from agent.nodes.analyst import analyze_job
from agent.nodes.compliance import check_compliance
from agent.nodes.critic import critique_proposal
from agent.nodes.decision import decide_bid
from agent.nodes.fit_matcher import match_fit
from agent.nodes.pricing import price_job
from agent.nodes.risk_assessor import assess_risk
from agent.nodes.writer import draft_proposal
from agent.persistence import checkpoint_serializer
from agent.pricing_priors import find_market_prior
from agent.state import GigBidState
from rag.index.memory import InMemoryEvidenceIndex
from rag.retriever import retrieve_for_job
from rag.verify import verify_claims

BidCompiledGraph: TypeAlias = CompiledStateGraph[GigBidState, None, GigBidState, GigBidState]


@dataclass(slots=True)
class BidGraphServices:
    marketplace: MarketplacePort
    evidence_index: InMemoryEvidenceIndex
    config: AppConfig
    evidence_indexes: dict[str, InMemoryEvidenceIndex] | None = None
    model_router: ModelRouter | None = None
    user_floor: float = 300
    store: BaseStore | None = None


def build_bid_graph(
    services: BidGraphServices,
    *,
    checkpointer: BaseCheckpointSaver[str] | None = None,
) -> BidCompiledGraph:
    def budget_exhausted(state: GigBidState) -> bool:
        return (
            state.get("step_count", 0) >= services.config.budgets.max_graph_steps
            or state.get("token_count", 0) >= services.config.budgets.max_tokens_per_job
        )

    async def load_job(state: GigBidState) -> dict[str, object]:
        raw_job = state.get("raw_job")
        if raw_job is None:
            raw_job = await services.marketplace.get_job(
                tenant_id=state["tenant_id"], job_id=state["job_id"]
            )
        connects_balance = await services.marketplace.get_connects_balance(
            tenant_id=state["tenant_id"]
        )
        return {
            "raw_job": raw_job,
            "connects_balance": connects_balance,
            "status": "analysing",
            "step_count": 1,
            "events": [{"node": "load_job", "status": "complete"}],
        }

    def analyst(state: GigBidState) -> dict[str, object]:
        return {
            "job_spec": analyze_job(state["raw_job"]),
            "step_count": 1,
            "events": [{"node": "analyst", "status": "complete"}],
        }

    async def risk(state: GigBidState) -> dict[str, object]:
        job = analyze_job(state["raw_job"])
        history = (
            await services.marketplace.get_client_history(
                tenant_id=state["tenant_id"], client_id=job.client_id
            )
            if job.client_id
            else {}
        )
        return {
            "risk_report": assess_risk(job, history),
            "step_count": 1,
            "events": [{"node": "risk_assessor", "status": "complete"}],
        }

    def fit(state: GigBidState) -> dict[str, object]:
        job = analyze_job(state["raw_job"])
        evidence_index = services.evidence_index
        if state.get("portfolio_evidence"):
            evidence_index = InMemoryEvidenceIndex(state["portfolio_evidence"])
        elif services.evidence_indexes is not None:
            evidence_index = services.evidence_indexes.get(
                state.get("persona", ""),
                evidence_index,
            )
        evidence = retrieve_for_job(
            job,
            evidence_index,
            variant=services.config.rag.variant,
            k=services.config.rag.top_k,
        )
        return {
            "evidence": evidence,
            "fit_report": match_fit(job, evidence),
            "step_count": 1,
            "events": [{"node": "fit_matcher", "status": "complete"}],
        }

    def decision(state: GigBidState) -> dict[str, object]:
        maximum_connects = min(
            services.config.thresholds.maximum_connects_per_bid,
            state.get(
                "max_connects_per_bid",
                services.config.thresholds.maximum_connects_per_bid,
            ),
            state.get("weekly_connects_budget", 10_000),
            state.get("connects_balance", 0),
        )
        decision_result = decide_bid(
            state["job_spec"],
            state["risk_report"],
            state["fit_report"],
            minimum_fit_score=services.config.thresholds.minimum_fit_score,
            maximum_risk_score=services.config.thresholds.maximum_risk_score,
            maximum_connects=maximum_connects,
        )
        return {
            "decision": decision_result,
            "status": decision_result.action.value,
            "step_count": 1,
            "events": [
                {"node": "decision", "status": "complete", "action": decision_result.action}
            ],
        }

    def decision_route(state: GigBidState) -> Literal["pricing", "done", "attention"]:
        if budget_exhausted(state):
            return "attention"
        return "pricing" if state["decision"].action == BidAction.BID else "done"

    def pricing(state: GigBidState) -> dict[str, object]:
        market_prior = find_market_prior(state["job_spec"])
        quote = price_job(
            state["job_spec"],
            state["fit_report"],
            state["risk_report"],
            user_floor=float(state.get("user_floor", services.user_floor)),
            market_prior=market_prior,
        )
        return {
            "price_quote": quote,
            "step_count": 1,
            "events": [{"node": "pricing", "status": "complete"}],
        }

    async def writer(state: GigBidState) -> dict[str, object]:
        draft = draft_proposal(
            state["job_spec"], state["fit_report"], state["evidence"], state["price_quote"]
        )
        usage: list[dict[str, object]] = []
        token_count = 0
        if services.model_router is not None:
            try:
                model_result = await services.model_router.generate_json(
                    node="writer",
                    prompt_name="writer.v1.md",
                    payload={
                        "job": state["job_spec"].model_dump(mode="json"),
                        "evidence": [
                            item.model_dump(mode="json") for item in state["evidence"]
                        ],
                        "price": state["price_quote"].model_dump(mode="json"),
                    },
                )
                cover_letter = model_result.data.get("cover_letter")
                raw_answers = model_result.data.get("screening_answers", {})
                if not isinstance(cover_letter, str) or not isinstance(raw_answers, dict):
                    raise ValueError("Writer model returned an invalid proposal object")
                draft = ProposalDraft(
                    job_id=state["job_spec"].job_id,
                    cover_letter=cover_letter,
                    screening_answers={
                        str(key): str(value) for key, value in raw_answers.items()
                    },
                    claims=[],
                    status="pending_verification",
                )
                token_count = model_result.tokens
                usage.append(
                    {
                        "node": "writer",
                        "model": model_result.model,
                        "prompt_tokens": model_result.prompt_tokens,
                        "completion_tokens": model_result.completion_tokens,
                        "latency_ms": model_result.latency_ms,
                        "cost_usd": 0.0,
                        "fallback_used": model_result.fallback_used,
                    }
                )
            except Exception as exc:
                usage.append(
                    {
                        "node": "writer",
                        "model": "deterministic_fallback",
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "latency_ms": 0.0,
                        "cost_usd": 0.0,
                        "fallback_used": True,
                        "error": type(exc).__name__,
                    }
                )
        if state.get("revision_count", 0):
            draft = draft.model_copy(update={"revision": state["revision_count"]})
        return {
            "proposal_draft": draft,
            "step_count": 1,
            "token_count": token_count,
            "model_usage": usage,
            "events": [
                {
                    "node": "writer",
                    "status": "complete",
                    "execution": "model" if token_count else "deterministic_fallback",
                }
            ],
        }

    def verifier(state: GigBidState) -> dict[str, object]:
        report = verify_claims(state["proposal_draft"], state["evidence"])
        corrected = state["proposal_draft"].model_copy(
            update={"cover_letter": report.corrected_cover_letter, "status": "verified"}
        )
        return {
            "claim_verification": report,
            "proposal_draft": corrected,
            "step_count": 1,
            "events": [{"node": "claim_verifier", "status": "complete"}],
        }

    def critic(state: GigBidState) -> dict[str, object]:
        result = critique_proposal(
            state["job_spec"], state["proposal_draft"], state["claim_verification"]
        )
        return {
            "critique": result,
            "step_count": 1,
            "events": [{"node": "critic", "status": "complete", "passed": result.passed}],
        }

    def critic_route(state: GigBidState) -> Literal["compliance", "revise", "attention"]:
        if budget_exhausted(state):
            return "attention"
        if state["critique"].passed:
            return "compliance"
        if state.get("revision_count", 0) < services.config.budgets.max_revisions:
            return "revise"
        return "attention"

    def revise(state: GigBidState) -> dict[str, object]:
        draft = state["proposal_draft"]
        words = draft.cover_letter.split()
        revised_text = " ".join(words[:250])
        revised = draft.model_copy(
            update={
                "cover_letter": revised_text,
                "revision": state.get("revision_count", 0) + 1,
                "status": "revised",
            }
        )
        return {
            "proposal_draft": revised,
            "revision_count": revised.revision,
            "step_count": 1,
            "events": [{"node": "revise", "status": "complete"}],
        }

    def needs_attention(state: GigBidState) -> dict[str, object]:
        return {
            "status": "needs_attention",
            "step_count": 1,
            "events": [{"node": "needs_attention", "status": "blocked"}],
        }

    def compliance(state: GigBidState) -> dict[str, object]:
        verdict = check_compliance(state["proposal_draft"])
        sanitized = state["proposal_draft"].model_copy(
            update={"cover_letter": verdict.sanitized_text, "status": "compliance_checked"}
        )
        return {
            "compliance_verdict": verdict,
            "proposal_draft": sanitized,
            "step_count": 1,
            "events": [{"node": "compliance", "status": "complete", "passed": verdict.passed}],
        }

    def compliance_route(state: GigBidState) -> Literal["prepare_approval", "attention"]:
        if budget_exhausted(state):
            return "attention"
        return "prepare_approval" if state["compliance_verdict"].passed else "attention"

    async def prepare_approval(state: GigBidState) -> dict[str, object]:
        payload = {
            "job_id": state["job_spec"].job_id,
            "cover_letter": state["proposal_draft"].cover_letter,
            "screening_answers": state["proposal_draft"].screening_answers,
            "connects_cost": state["job_spec"].connects_cost,
        }
        dry_run = await services.marketplace.preview_proposal(
            tenant_id=state["tenant_id"], payload=payload
        )
        approval = ApprovalPayload(
            thread_id=state["thread_id"],
            draft=state["proposal_draft"],
            evidence=state["evidence"],
            risk_report=state["risk_report"],
            price_quote=state["price_quote"],
            compliance_verdict=state["compliance_verdict"],
            dry_run=dry_run,
            idempotency_key=f"proposal:{state['tenant_id']}:{state['job_id']}:{uuid4()}",
        )
        return {
            "approval_payload": approval,
            "status": "awaiting_approval",
            "step_count": 1,
            "events": [{"node": "prepare_approval", "status": "complete"}],
        }

    def approval(state: GigBidState) -> dict[str, object]:
        response = interrupt(state["approval_payload"].model_dump(mode="json"))
        decision_result = ApprovalDecision.model_validate(response)
        updates: dict[str, object] = {
            "approval_decision": decision_result,
            "status": decision_result.action.value,
            "step_count": 1,
            "events": [{"node": "approval", "status": decision_result.action.value}],
        }
        if decision_result.action == ApprovalAction.EDIT:
            edited_text = decision_result.edited_cover_letter or ""
            updates["style_edit_patterns"] = infer_style_patterns(
                state["proposal_draft"].cover_letter,
                edited_text,
            )
            updates["proposal_draft"] = state["proposal_draft"].model_copy(
                update={
                    "cover_letter": edited_text,
                    "status": "user_edited",
                }
            )
        return updates

    def approval_route(
        state: GigBidState,
    ) -> Literal["record_memory", "compliance", "done", "attention"]:
        if budget_exhausted(state):
            return "attention"
        action = state["approval_decision"].action
        if action == ApprovalAction.APPROVE:
            return "record_memory"
        if action == ApprovalAction.EDIT:
            return "compliance"
        return "done"

    async def record_memory(state: GigBidState) -> dict[str, object]:
        patterns = list(dict.fromkeys(state.get("style_edit_patterns", [])))
        if services.store is not None and patterns:
            memory = LongTermMemory(
                services.store,
                tenant_id=state["tenant_id"],
                user_id=state["user_id"],
                style_minimum_consistent_edits=(
                    services.config.memory.style_minimum_consistent_edits
                ),
                outcome_minimum_observations=(services.config.memory.outcome_minimum_observations),
                outcome_minimum_reply_rate=(services.config.memory.outcome_minimum_reply_rate),
            )
            for pattern in patterns:
                await memory.record_style_observation(
                    thread_id=state["thread_id"],
                    pattern=pattern,
                )
        return {
            "step_count": 1,
            "events": [
                {
                    "node": "record_memory",
                    "status": "complete",
                    "observations": len(patterns),
                }
            ],
        }

    async def submit(state: GigBidState) -> dict[str, object]:
        payload = state["approval_payload"]
        receipt = await services.marketplace.create_proposal_draft(
            tenant_id=state["tenant_id"],
            payload={
                "job_id": payload.draft.job_id,
                "cover_letter": state["proposal_draft"].cover_letter,
                "screening_answers": state["proposal_draft"].screening_answers,
                "connects_cost": payload.dry_run.connects_cost,
            },
            idempotency_key=payload.idempotency_key,
        )
        return {
            "marketplace_receipt": receipt,
            "status": receipt.status,
            "step_count": 1,
            "events": [{"node": "submit", "status": receipt.status}],
        }

    builder = StateGraph(GigBidState)
    builder.add_node("load_job", load_job)
    builder.add_node("analyst", analyst)
    builder.add_node("risk", risk)
    builder.add_node("fit", fit)
    builder.add_node("decision", decision)
    builder.add_node("pricing", pricing)
    builder.add_node("writer", writer)
    builder.add_node("verifier", verifier)
    builder.add_node("critic", critic)
    builder.add_node("revise", revise)
    builder.add_node("compliance", compliance)
    builder.add_node("prepare_approval", prepare_approval)
    builder.add_node("approval", approval)
    builder.add_node("record_memory", record_memory)
    builder.add_node("submit", submit)
    builder.add_node("needs_attention", needs_attention)

    builder.add_edge(START, "load_job")
    builder.add_edge("load_job", "analyst")
    builder.add_edge("load_job", "risk")
    builder.add_edge("load_job", "fit")
    builder.add_edge(["analyst", "risk", "fit"], "decision")
    builder.add_conditional_edges(
        "decision",
        decision_route,
        {"pricing": "pricing", "done": END, "attention": "needs_attention"},
    )
    builder.add_edge("pricing", "writer")
    builder.add_edge("writer", "verifier")
    builder.add_edge("verifier", "critic")
    builder.add_conditional_edges(
        "critic",
        critic_route,
        {"compliance": "compliance", "revise": "revise", "attention": "needs_attention"},
    )
    builder.add_edge("revise", "verifier")
    builder.add_conditional_edges(
        "compliance",
        compliance_route,
        {"prepare_approval": "prepare_approval", "attention": "needs_attention"},
    )
    builder.add_edge("prepare_approval", "approval")
    builder.add_conditional_edges(
        "approval",
        approval_route,
        {
            "record_memory": "record_memory",
            "compliance": "compliance",
            "done": END,
            "attention": "needs_attention",
        },
    )
    builder.add_edge("record_memory", "submit")
    builder.add_edge("submit", END)
    builder.add_edge("needs_attention", END)
    active_checkpointer = checkpointer or InMemorySaver(serde=checkpoint_serializer())
    return builder.compile(checkpointer=active_checkpointer, store=services.store)


def build_default_bid_graph(
    marketplace: MarketplacePort, evidence: InMemoryEvidenceIndex
) -> BidCompiledGraph:
    return build_bid_graph(
        BidGraphServices(marketplace=marketplace, evidence_index=evidence, config=load_config())
    )
