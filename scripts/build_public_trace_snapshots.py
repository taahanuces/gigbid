from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from fastapi.encoders import jsonable_encoder
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.config import load_config
from agent.graphs.bid_graph import (
    BidCompiledGraph,
    BidGraphServices,
    ProposalWriter,
    build_bid_graph,
)
from agent.handoffs import (
    EvidenceItem,
    FitReport,
    JobSpec,
    MarketplaceReceipt,
    PriceQuote,
    ProposalDraft,
)
from agent.persistence import checkpoint_serializer
from agent.state import GigBidState
from mcp_servers.marketplace.adapters.memory import InMemoryMarketplaceAdapter
from rag.index.memory import InMemoryEvidenceIndex

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "apps" / "web" / "src" / "data" / "public-traces.json"


class CrashAfterAcceptedWriteMarketplace(InMemoryMarketplaceAdapter):
    """Raise once after the simulated marketplace has accepted a draft."""

    def __init__(self, *, jobs: list[dict[str, object]]) -> None:
        super().__init__(jobs=jobs)
        self.fail_after_write = True

    async def create_proposal_draft(
        self,
        *,
        tenant_id: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        receipt = await super().create_proposal_draft(
            tenant_id=tenant_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        if self.fail_after_write:
            self.fail_after_write = False
            raise RuntimeError("simulated process crash after the upstream write")
        return receipt


def _fixtures() -> tuple[list[dict[str, object]], list[EvidenceItem]]:
    jobs = cast(
        list[dict[str, object]],
        json.loads((ROOT / "evals" / "datasets" / "smoke_jobs.json").read_text()),
    )
    raw_evidence = cast(
        list[dict[str, object]],
        json.loads((ROOT / "evals" / "datasets" / "smoke_portfolio.json").read_text()),
    )
    return jobs, [EvidenceItem.model_validate(item) for item in raw_evidence]


def _graph(
    *,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    marketplace: InMemoryMarketplaceAdapter | None = None,
    proposal_writer: ProposalWriter | None = None,
) -> tuple[BidCompiledGraph, InMemoryMarketplaceAdapter]:
    jobs, evidence = _fixtures()
    active_marketplace = marketplace or InMemoryMarketplaceAdapter(jobs=jobs)
    graph = build_bid_graph(
        BidGraphServices(
            marketplace=active_marketplace,
            evidence_index=InMemoryEvidenceIndex(evidence),
            config=load_config(ROOT / "agent" / "config.yaml"),
            store=InMemoryStore(),
            proposal_writer=proposal_writer,
        ),
        checkpointer=checkpointer,
    )
    return graph, active_marketplace


def _initial_state(*, thread_id: str, trace_id: str, job_id: str) -> GigBidState:
    return {
        "thread_id": thread_id,
        "trace_id": trace_id,
        "tenant_id": "demo",
        "user_id": "reviewer",
        "job_id": job_id,
        "persona": "data-analyst",
        "events": [],
        "errors": [],
        "revision_count": 0,
        "step_count": 0,
        "token_count": 0,
    }


async def _checkpoint_count(graph: BidCompiledGraph, config: RunnableConfig) -> int:
    return len([snapshot async for snapshot in graph.aget_state_history(config)])


def _spans(events: object) -> list[dict[str, object]]:
    encoded = jsonable_encoder(events)
    if not isinstance(encoded, list):
        return []
    spans: list[dict[str, object]] = []
    for index, raw in enumerate(encoded, start=1):
        if not isinstance(raw, dict):
            continue
        node = str(raw.get("node", "unknown"))
        status = str(raw.get("status", raw.get("action", "complete")))
        attributes = {
            str(key): value for key, value in raw.items() if key not in {"node", "status"}
        }
        spans.append(
            {
                "sequence": index,
                "node": node,
                "status": status,
                "attributes": attributes,
            }
        )
    return spans


async def _scam_trace() -> dict[str, object]:
    graph, marketplace = _graph()
    thread_id = "public-scam-skip"
    trace_id = "trace-public-scam-4016"
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    started = perf_counter()
    result = await graph.ainvoke(
        _initial_state(thread_id=thread_id, trace_id=trace_id, job_id="job-risk-002"),
        config,
    )
    duration_ms = round((perf_counter() - started) * 1_000, 3)
    assert result["status"] == "skip"
    assert not marketplace.proposals
    risk = jsonable_encoder(result["risk_report"])
    return {
        "slug": "scam-injection-skip",
        "trace_id": trace_id,
        "title": "Scam and prompt-injection job skipped",
        "status": "skip",
        "summary": (
            "The risk branch treated the job post as untrusted input, recorded the injected "
            "instruction, blocked the off-platform request, and terminated with zero marketplace "
            "writes."
        ),
        "data_origin": "Synthetic GigSim smoke fixture; redacted, read-only execution snapshot",
        "metrics": {
            "duration_ms": duration_ms,
            "events": len(result.get("events", [])),
            "checkpoints": await _checkpoint_count(graph, config),
            "marketplace_writes": 0,
            "model_cost_usd": 0,
        },
        "assertions": [
            "Injected job instructions were recorded but never followed.",
            "Off-platform contact and unpaid-work signals forced a skip.",
            "No proposal draft or Connects spend occurred.",
        ],
        "evidence_refs": [
            "tests/unit/test_nodes.py::test_risky_job_is_blocked_and_injection_is_recorded",
            "tests/integration/test_bid_graph.py::test_risky_job_terminates_without_draft",
            "evals/datasets/smoke_jobs.json#job-risk-002",
        ],
        "spans": _spans(result.get("events", [])),
        "redacted_state": {
            "decision": jsonable_encoder(result["decision"]),
            "risk_report": risk,
            "proposal_created": False,
        },
    }


def _overlong_grounded_draft(
    job: JobSpec,
    _fit: FitReport,
    _evidence: list[EvidenceItem],
    _price: PriceQuote,
) -> ProposalDraft:
    opening = f"Your {job.title.lower()} project has a clear delivery scope."
    neutral_extension = " ".join(["validation"] * 255)
    return ProposalDraft(job_id=job.job_id, cover_letter=f"{opening} {neutral_extension}")


async def _critic_and_approval_trace() -> dict[str, object]:
    graph, marketplace = _graph(proposal_writer=_overlong_grounded_draft)
    try:
        thread_id = "public-critic-approval"
        trace_id = "trace-public-critic-4016"
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        started = perf_counter()
        await graph.ainvoke(
            _initial_state(
                thread_id=thread_id,
                trace_id=trace_id,
                job_id="job-forecast-001",
            ),
            config,
        )
        pending = await graph.aget_state(config)
        assert pending.values["status"] == "awaiting_approval"
        assert sum(event.get("node") == "critic" for event in pending.values["events"]) == 2
        await graph.ainvoke(Command[Any](resume={"action": "approve"}), config)
        completed = await graph.aget_state(config)
        duration_ms = round((perf_counter() - started) * 1_000, 3)
        assert completed.values["status"] == "draft_created"
        assert len(marketplace.proposals) == 1
        return {
            "slug": "approved-critic-loop",
            "trace_id": trace_id,
            "title": "Critic revision loop and approved draft",
            "status": "draft_created",
            "summary": (
                "The Critic rejected a 260-plus-word synthetic draft, the bounded revision loop "
                "trimmed it to policy, verification and compliance ran again, and a human approval "
                "created one marketplace draft."
            ),
            "data_origin": "Synthetic GigSim test harness; redacted, read-only execution snapshot",
            "metrics": {
                "duration_ms": duration_ms,
                "events": len(completed.values.get("events", [])),
                "checkpoints": await _checkpoint_count(graph, config),
                "critic_passes": 2,
                "revisions": completed.values.get("revision_count", 0),
                "marketplace_writes": len(marketplace.proposals),
                "model_cost_usd": 0,
            },
            "assertions": [
                "The first Critic pass failed for excessive length.",
                "The bounded revision loop reran claim verification and Critic checks.",
                "The graph interrupted for explicit human approval before the write.",
                "Approval created a marketplace draft only; it did not submit a final proposal.",
            ],
            "evidence_refs": [
                "scripts/build_public_trace_snapshots.py::_critic_and_approval_trace",
                "tests/integration/test_bid_graph.py::test_bid_graph_interrupts_then_writes_once",
                "agent/graphs/bid_graph.py#critic_route",
            ],
            "spans": _spans(completed.values.get("events", [])),
            "redacted_state": {
                "status": completed.values["status"],
                "revision_count": completed.values.get("revision_count", 0),
                "compliance_passed": completed.values["compliance_verdict"].passed,
                "approval": "human_approved",
                "marketplace_receipt": jsonable_encoder(completed.values["marketplace_receipt"]),
            },
        }
    finally:
        pass


async def _crash_resume_trace() -> dict[str, object]:
    jobs, _ = _fixtures()
    marketplace = CrashAfterAcceptedWriteMarketplace(jobs=jobs)
    checkpointer = InMemorySaver(serde=checkpoint_serializer())
    graph, _ = _graph(checkpointer=checkpointer, marketplace=marketplace)
    thread_id = "public-crash-resume"
    trace_id = "trace-public-resume-4016"
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    started = perf_counter()
    await graph.ainvoke(
        _initial_state(thread_id=thread_id, trace_id=trace_id, job_id="job-forecast-001"),
        config,
    )
    crashed = False
    try:
        await graph.ainvoke(Command[Any](resume={"action": "approve"}), config)
    except RuntimeError as exc:
        assert "after the upstream write" in str(exc)
        crashed = True
    assert crashed
    assert len(marketplace.proposals) == 1
    assert len(marketplace.receipts) == 1

    restarted_graph, _ = _graph(checkpointer=checkpointer, marketplace=marketplace)
    await restarted_graph.ainvoke(None, config)
    completed = await restarted_graph.aget_state(config)
    duration_ms = round((perf_counter() - started) * 1_000, 3)
    assert completed.values["status"] == "draft_created"
    assert len(marketplace.proposals) == 1
    assert len(marketplace.receipts) == 1

    spans = _spans(completed.values.get("events", []))
    submit_index = next(
        (index for index, span in enumerate(spans) if span["node"] == "submit"),
        len(spans),
    )
    recovery_spans = [
        {
            "sequence": 0,
            "node": "marketplace_write",
            "status": "accepted_before_crash",
            "attributes": {"idempotency_receipts": 1},
        },
        {
            "sequence": 0,
            "node": "process_failure",
            "status": "simulated_crash",
            "attributes": {"checkpoint_preserved": True},
        },
        {
            "sequence": 0,
            "node": "checkpoint_restore",
            "status": "resumed",
            "attributes": {"replayed_marketplace_writes": 0},
        },
    ]
    spans[submit_index:submit_index] = recovery_spans
    for sequence, span in enumerate(spans, start=1):
        span["sequence"] = sequence

    return {
        "slug": "crash-resume-exactly-once",
        "trace_id": trace_id,
        "title": "Crash, checkpoint resume, and exactly-once draft",
        "status": "draft_created",
        "summary": (
            "The marketplace accepted the draft, the worker crashed before recording completion, "
            "and a reconstructed graph resumed from the checkpoint. The idempotency key returned "
            "the original receipt, so the final write count remained one."
        ),
        "data_origin": "Synthetic fault-injection harness; redacted, read-only execution snapshot",
        "metrics": {
            "duration_ms": duration_ms,
            "events": len(spans),
            "checkpoints": await _checkpoint_count(restarted_graph, config),
            "simulated_crashes": 1,
            "marketplace_writes": len(marketplace.proposals),
            "idempotency_receipts": len(marketplace.receipts),
            "model_cost_usd": 0,
        },
        "assertions": [
            "The checkpoint remained available after graph reconstruction.",
            "The accepted marketplace write retained its original idempotency receipt.",
            "Resume completed with exactly one draft and no duplicate Connects spend.",
        ],
        "evidence_refs": [
            "tests/integration/test_bid_graph.py::test_retry_after_post_write_crash_is_exactly_once",
            "tests/integration/test_postgres_durability.py::test_postgres_checkpoint_survives_connection_restart",
            "agent/graphs/bid_graph.py#submit",
        ],
        "spans": spans,
        "redacted_state": {
            "status": completed.values["status"],
            "process_reconstructed": True,
            "marketplace_write_count": len(marketplace.proposals),
            "idempotency_receipt_count": len(marketplace.receipts),
        },
    }


async def main() -> None:
    traces = [
        await _scam_trace(),
        await _critic_and_approval_trace(),
        await _crash_resume_trace(),
    ]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "schema_version": 1,
        "disclosure": (
            "Public snapshots contain synthetic data and redacted state only. They preserve graph "
            "events, safety assertions, checkpoint counts, and write counts without prompts, "
            "private portfolio text, credentials, or PII."
        ),
        "traces": traces,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
