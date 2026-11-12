from __future__ import annotations

import os
from time import perf_counter
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START

from agent.observability import current_trace_id, record_graph_run, trace_url_for
from agent.state import GigBidState
from agent.telemetry import trace_span
from apps.api.auth.security import AuthenticatedUser
from apps.api.context import AppContext
from apps.api.dependencies import get_context, get_current_user
from apps.api.portfolio_store import list_uploaded_evidence
from apps.api.profile_store import load_profile
from apps.api.run_store import list_run_summaries, save_run_summary
from apps.api.schemas.api import AnalyzeJobRequest, InboxJob, JobSummary, RunResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _async_graph_runs_enabled(context: AppContext) -> bool:
    requested = os.getenv("ASYNC_GRAPH_RUNS", "false").lower() in {"1", "true", "yes"}
    return requested and context.checkpoint_backend == "postgres"


@router.get("", response_model=list[JobSummary])
async def list_jobs(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> list[dict[str, object]]:
    return await context.marketplace.search_jobs(tenant_id=user.tenant_id, query="")


@router.get("/{job_id}", response_model=JobSummary)
async def get_job(
    job_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> dict[str, object]:
    try:
        return await context.marketplace.get_job(tenant_id=user.tenant_id, job_id=job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/ranked/inbox", response_model=list[InboxJob])
async def ranked_inbox(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> list[InboxJob]:
    jobs = await context.marketplace.search_jobs(tenant_id=user.tenant_id, query="")
    summaries = await list_run_summaries(
        context.store,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
    )
    ranked: list[InboxJob] = []
    for raw in jobs:
        summary = summaries.get(str(raw["job_id"]), {})
        action = str(summary.get("action", "pending"))
        if action not in {"pending", "bid", "watch", "skip"}:
            action = "pending"
        ranked.append(
            InboxJob.model_validate(
                {
                    **raw,
                    "thread_id": summary.get("thread_id") or None,
                    "analysis_status": summary.get("status", "pending"),
                    "action": action,
                    "fit_score": summary.get("fit_score"),
                    "risk_score": summary.get("risk_score"),
                    "recommended_price": summary.get("recommended_price"),
                    "reasons": summary.get("reasons", []),
                }
            )
        )
    priority = {"bid": 0, "watch": 1, "pending": 2, "skip": 3}
    return sorted(
        ranked,
        key=lambda item: (
            priority[item.action],
            -(item.fit_score or 0),
            item.risk_score or 0,
        ),
    )


@router.post("/{job_id}/analyze", response_model=RunResponse)
async def analyze_job(
    job_id: str,
    request: AnalyzeJobRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> RunResponse:
    profile = await load_profile(
        context.store,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
    )
    base_evidence = context.evidence_indexes.get(profile.persona, context.evidence_index).all()
    uploaded_evidence = await list_uploaded_evidence(
        context.store,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
    )
    thread_id = str(uuid4())
    trace_id = current_trace_id()
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    started = perf_counter()
    initial_state: GigBidState = {
        "trace_id": trace_id,
        "thread_id": thread_id,
        "tenant_id": user.tenant_id,
        "user_id": user.user_id,
        "user_floor": (
            request.user_floor if request.user_floor is not None else profile.fixed_price_floor
        ),
        "persona": profile.persona,
        "portfolio_evidence": [
            item for item in [*base_evidence, *uploaded_evidence] if item.persona == profile.persona
        ],
        "max_connects_per_bid": profile.max_connects_per_bid,
        "weekly_connects_budget": profile.weekly_connects_budget,
        "job_id": job_id,
        "revision_count": 0,
        "step_count": 0,
        "token_count": 0,
        "model_usage": [],
        "events": [],
        "errors": [],
    }
    if _async_graph_runs_enabled(context):
        from worker.tasks import analyze_job_task

        initial_state["status"] = "queued"
        await context.graph.aupdate_state(config, initial_state, as_node=START)
        analyze_job_task.delay(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            job_id=job_id,
            thread_id=thread_id,
            trace_id=trace_id,
        )
    else:
        with trace_span(
            "gigbid.bid_graph",
            {
                "gigbid.trace_id": trace_id,
                "gigbid.thread_id": thread_id,
                "gigbid.graph": "bid",
            },
        ):
            await context.graph.ainvoke(initial_state, config)
    snapshot = await context.graph.aget_state(config)
    values = jsonable_encoder(snapshot.values)
    await save_run_summary(context.store, values)
    status = str(values.get("status", "unknown"))
    if status != "queued":
        record_graph_run(status=status, duration_seconds=perf_counter() - started)
    return RunResponse(
        thread_id=thread_id,
        status=status,
        state=values,
        trace_id=trace_id,
        trace_url=trace_url_for(trace_id),
    )
