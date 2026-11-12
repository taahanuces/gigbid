from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from agent.config import AppConfig, load_config
from agent.graphs.bid_graph import BidCompiledGraph, BidGraphServices, build_bid_graph
from agent.graphs.conversation_graph import (
    ConversationCompiledGraph,
    build_conversation_graph,
)
from agent.handoffs import EvidenceItem
from agent.marketplace_port import MarketplacePort
from agent.models import ModelRouter
from apps.api.auth.security import AuthenticatedUser, hash_password
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.adapters.memory import InMemoryMarketplaceAdapter
from rag.index.memory import InMemoryEvidenceIndex

ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class UserRecord:
    user: AuthenticatedUser
    password_hash: str


@dataclass(slots=True)
class AppContext:
    marketplace: MarketplacePort
    evidence_index: InMemoryEvidenceIndex
    evidence_indexes: dict[str, InMemoryEvidenceIndex]
    graph: BidCompiledGraph
    conversation_graph: ConversationCompiledGraph
    config: AppConfig
    users: dict[str, UserRecord]
    secret: str
    checkpoint_backend: str
    marketplace_mode: str
    store: BaseStore | None = None


def build_context(
    *,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    store: BaseStore | None = None,
    checkpoint_backend: str = "memory",
) -> AppContext:
    marketplace_mode = os.getenv("MARKETPLACE_MODE", "memory")
    jobs = json.loads((ROOT / "evals/datasets/smoke_jobs.json").read_text(encoding="utf-8"))
    if marketplace_mode == "gigsim":
        marketplace: MarketplacePort = GigSimAdapter(
            base_url=os.getenv("GIGSIM_BASE_URL", "http://gigsim:8081"),
            api_token=os.getenv("GIGSIM_API_TOKEN", "gigsim-development-token"),
            requests_per_minute=int(os.getenv("GIGSIM_REQUESTS_PER_MINUTE", "18")),
        )
        evidence = _persona_evidence(os.getenv("ACTIVE_PERSONA", "data-analyst"))
    elif marketplace_mode == "memory":
        evidence = [
            EvidenceItem.model_validate(item)
            for item in json.loads(
                (ROOT / "evals/datasets/smoke_portfolio.json").read_text(encoding="utf-8")
            )
        ]
        marketplace = InMemoryMarketplaceAdapter(
            jobs=jobs,
            clients={
                "client-001": {
                    "client_id": "client-001",
                    "payment_verified": True,
                    "average_rating": 4.8,
                    "completed_projects": 12,
                },
                "client-002": {
                    "client_id": "client-002",
                    "payment_verified": False,
                    "average_rating": 2.0,
                    "completed_projects": 0,
                },
            },
        )
    else:
        raise ValueError(f"Unsupported API marketplace mode: {marketplace_mode}")
    evidence_index = InMemoryEvidenceIndex(evidence)
    evidence_indexes = _persona_indexes()
    config = load_config(ROOT / "agent/config.yaml")
    model_router = (
        ModelRouter.from_config(config.models)
        if os.getenv("MODEL_EXECUTION", "deterministic").lower() == "llm"
        else None
    )
    graph = build_bid_graph(
        BidGraphServices(
            marketplace=marketplace,
            evidence_index=evidence_index,
            evidence_indexes=evidence_indexes,
            model_router=model_router,
            config=config,
            store=store,
        ),
        checkpointer=checkpointer,
    )
    conversation_graph = build_conversation_graph(
        marketplace,
        checkpointer=checkpointer,
        store=store,
    )
    reviewer = AuthenticatedUser(
        user_id="reviewer-001",
        tenant_id="demo",
        email="reviewer@gigbid.local",
        role="reviewer",
    )
    users = {
        reviewer.email: UserRecord(
            user=reviewer,
            password_hash=hash_password(os.getenv("REVIEWER_PASSWORD", "GigBidDemo2026!")),
        )
    }
    secret = os.getenv("APP_SECRET_KEY", "local-development-secret-change-before-deploy")
    return AppContext(
        marketplace=marketplace,
        evidence_index=evidence_index,
        evidence_indexes=evidence_indexes,
        graph=graph,
        conversation_graph=conversation_graph,
        config=config,
        users=users,
        secret=secret,
        checkpoint_backend=checkpoint_backend,
        marketplace_mode=marketplace_mode,
        store=store,
    )


def _persona_evidence(persona: str) -> list[EvidenceItem]:
    allowed = {"ai-ml-engineer", "full-stack-developer", "data-analyst"}
    if persona not in allowed:
        raise ValueError(f"Unknown ACTIVE_PERSONA: {persona}")
    path = ROOT / "data/processed/personas" / f"{persona}.jsonl"
    if not path.exists():
        raise FileNotFoundError("Run make synthetic-data before starting GigSim mode")
    return [
        EvidenceItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _persona_indexes() -> dict[str, InMemoryEvidenceIndex]:
    personas = ("ai-ml-engineer", "full-stack-developer", "data-analyst")
    return {
        persona: InMemoryEvidenceIndex(_persona_evidence(persona))
        for persona in personas
        if (ROOT / "data/processed/personas" / f"{persona}.jsonl").exists()
    }
