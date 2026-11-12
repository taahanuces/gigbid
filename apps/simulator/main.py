from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.base import RequestResponseEndpoint

from agent.handoffs import DryRunPreview, MarketplaceReceipt
from apps.simulator.engine import SimulatorState

ROOT = Path(__file__).resolve().parents[2]


class SimulatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(min_length=1)


class ProposalDraftRequest(SimulatorRequest):
    job_id: str = Field(min_length=1)
    cover_letter: str = Field(min_length=20, max_length=5_000)
    screening_answers: dict[str, str] = Field(default_factory=dict)
    connects_cost: int = Field(default=0, ge=0)
    dry_run: bool = True


class SubmitRequest(SimulatorRequest):
    pass


class MessageRequest(SimulatorRequest):
    body: str = Field(min_length=1, max_length=5_000)


def _fixture() -> dict[str, Any]:
    configured = os.getenv("SIMULATOR_FIXTURE", "").strip()
    path = Path(configured) if configured else ROOT / "evals/datasets/simulator_fixture.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Simulator fixture must be a JSON object")
    return value


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.simulator = SimulatorState(_fixture())
    yield


app = FastAPI(
    title="GigBid Simulator",
    version="1.0.0",
    description=(
        "Deterministic GigSim-compatible service built from public jobs and synthetic client "
        "behaviour."
    ),
    lifespan=lifespan,
)


def simulator(request: Request) -> SimulatorState:
    return cast(SimulatorState, request.app.state.simulator)


def authorized(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("GIGSIM_API_TOKEN", "gigsim-development-token")
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid simulator bearer token")


Auth = Annotated[None, Depends(authorized)]
State = Annotated[SimulatorState, Depends(simulator)]


@app.middleware("http")
async def deterministic_faults(request: Request, call_next: RequestResponseEndpoint) -> Response:
    fault = request.headers.get("X-GigSim-Fault")
    if fault in {"429", "500", "503"}:
        return JSONResponse(
            status_code=int(fault),
            content={"detail": "Injected simulator fault"},
        )
    return await call_next(request)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "gigbid-simulator"}


@app.get("/metadata", dependencies=[Depends(authorized)])
async def metadata(state: State) -> dict[str, object]:
    return dict(state.fixture["metadata"])


@app.get("/jobs", dependencies=[Depends(authorized)])
async def search_jobs(
    state: State,
    tenant_id: Annotated[str, Query(min_length=1)],
    q: str = "",
    limit: Annotated[int, Query(ge=1, le=300)] = 100,
) -> list[dict[str, object]]:
    del tenant_id
    terms = q.lower().split()
    return [
        dict(job)
        for job in state.jobs.values()
        if not terms or all(term in json.dumps(job).lower() for term in terms)
    ][:limit]


@app.get("/jobs/{job_id}", dependencies=[Depends(authorized)])
async def get_job(
    job_id: str,
    state: State,
    tenant_id: Annotated[str, Query(min_length=1)],
) -> dict[str, object]:
    del tenant_id
    try:
        return dict(state.jobs[job_id])
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Unknown job") from error


@app.get("/clients/{client_id}", dependencies=[Depends(authorized)])
async def get_client(
    client_id: str,
    state: State,
    tenant_id: Annotated[str, Query(min_length=1)],
) -> dict[str, object]:
    del tenant_id
    try:
        client = dict(state.clients[client_id])
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Unknown client") from error
    client.pop("hidden_preferences", None)
    return client


@app.get("/connects", dependencies=[Depends(authorized)])
async def get_connects(
    state: State, tenant_id: Annotated[str, Query(min_length=1)]
) -> dict[str, int]:
    return {"balance": state.balance(tenant_id)}


@app.get(
    "/conversations/{conversation_id}/messages",
    dependencies=[Depends(authorized)],
)
async def list_messages(
    conversation_id: str,
    state: State,
    tenant_id: Annotated[str, Query(min_length=1)],
) -> list[dict[str, object]]:
    del tenant_id
    return list(state.messages.get(conversation_id, []))


@app.post(
    "/proposals/draft",
    response_model=DryRunPreview | MarketplaceReceipt,
    dependencies=[Depends(authorized)],
)
async def create_proposal_draft(
    body: ProposalDraftRequest,
    state: State,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DryRunPreview | MarketplaceReceipt:
    try:
        job = state.jobs[body.job_id]
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Unknown job") from error
    raw_cost = job.get("connects_cost", 0)
    if not isinstance(raw_cost, (str, int, float)):
        raise HTTPException(status_code=500, detail="Job connects_cost must be numeric")
    cost = int(raw_cost)
    payload = body.model_dump(exclude={"tenant_id", "dry_run"})
    payload["connects_cost"] = cost
    if body.dry_run:
        return DryRunPreview(
            tool_name="create_proposal_draft",
            payload=payload,
            connects_cost=cost,
            side_effects=["Creates a simulator proposal draft", f"Reserves {cost} Connects"],
        )
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key is required")
    try:
        return state.create_draft(
            tenant_id=body.tenant_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post(
    "/proposals/{proposal_id}/submit",
    response_model=MarketplaceReceipt,
    dependencies=[Depends(authorized)],
)
async def submit_proposal(
    proposal_id: str,
    body: SubmitRequest,
    state: State,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MarketplaceReceipt:
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key is required")
    try:
        return state.submit(
            tenant_id=body.tenant_id,
            proposal_id=proposal_id,
            idempotency_key=idempotency_key,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Unknown proposal") from error


@app.post(
    "/conversations/{conversation_id}/messages",
    response_model=MarketplaceReceipt,
    dependencies=[Depends(authorized)],
)
async def send_message(
    conversation_id: str,
    body: MessageRequest,
    state: State,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MarketplaceReceipt:
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key is required")
    return state.send_message(
        tenant_id=body.tenant_id,
        conversation_id=conversation_id,
        body=body.body,
        idempotency_key=idempotency_key,
    )


@app.get("/proposals", dependencies=[Depends(authorized)])
async def list_proposals(state: State) -> list[dict[str, object]]:
    return list(state.proposals.values())


@app.get("/outcomes", dependencies=[Depends(authorized)])
async def list_outcomes(state: State) -> list[dict[str, object]]:
    return [
        dict(proposal_id=proposal_id, **outcome) for proposal_id, outcome in state.outcomes.items()
    ]


@app.get("/events", dependencies=[Depends(authorized)])
async def list_events(state: State) -> list[dict[str, object]]:
    return list(state.events)


@app.get("/conversations", dependencies=[Depends(authorized)])
async def list_conversations(state: State) -> list[dict[str, object]]:
    return [
        {
            "conversation_id": conversation_id,
            "proposal_id": conversation_id.removeprefix("conversation-"),
            "messages": list(messages),
        }
        for conversation_id, messages in state.messages.items()
    ]
