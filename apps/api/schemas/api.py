from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from agent.handoffs import ApprovalAction


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a credential


class AnalyzeJobRequest(BaseModel):
    user_floor: float | None = Field(default=None, ge=0)


PersonaSlug = Literal["ai-ml-engineer", "full-stack-developer", "data-analyst"]


class ProfileSettings(BaseModel):
    persona: PersonaSlug = "data-analyst"
    hourly_rate: float = Field(default=35, ge=0, le=10_000)
    fixed_price_floor: float = Field(default=300, ge=0, le=1_000_000)
    weekly_connects_budget: int = Field(default=80, ge=0, le=10_000)
    max_connects_per_bid: int = Field(default=16, ge=0, le=100)
    search_keywords: list[str] = Field(
        default_factory=lambda: ["python", "analytics", "automation"],
        max_length=20,
    )
    approval_required: Literal[True] = True
    onboarding_complete: bool = False


class ProfileResponse(BaseModel):
    settings: ProfileSettings
    marketplace_mode: str
    evidence_count: int = Field(ge=0)
    data_origin: str


class ApprovalRequest(BaseModel):
    action: ApprovalAction
    edited_cover_letter: str | None = Field(default=None, max_length=5000)
    reason: str | None = Field(default=None, max_length=1000)


class RunResponse(BaseModel):
    thread_id: str
    status: str
    state: dict[str, object]
    trace_id: str | None = None
    trace_url: str | None = None


class CheckpointSummary(BaseModel):
    checkpoint_id: str
    created_at: str | None = None
    status: str
    next_nodes: list[str] = Field(default_factory=list)
    step_count: int = Field(default=0, ge=0)


class CheckpointHistoryResponse(BaseModel):
    thread_id: str
    checkpoints: list[CheckpointSummary]


class CheckpointReplayResponse(BaseModel):
    thread_id: str
    checkpoint_id: str
    read_only: bool = True
    status: str
    next_nodes: list[str] = Field(default_factory=list)
    state: dict[str, object]


class ParagraphRegenerateRequest(BaseModel):
    paragraph_index: int = Field(ge=0, le=50)


class ParagraphRegenerateResponse(BaseModel):
    paragraph_index: int = Field(ge=0)
    replacement: str
    reasons: list[str]


class BudgetRange(BaseModel):
    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)
    currency: str = Field(min_length=3, max_length=3)


class JobSummary(BaseModel):
    job_id: str
    client_id: str
    title: str
    description: str
    required_skills: list[str]
    connects_cost: int = Field(ge=0)
    budget: BudgetRange


class InboxJob(JobSummary):
    thread_id: str | None = None
    analysis_status: str = "pending"
    action: Literal["pending", "bid", "watch", "skip"] = "pending"
    fit_score: float | None = Field(default=None, ge=0, le=1)
    risk_score: float | None = Field(default=None, ge=0, le=1)
    recommended_price: float | None = Field(default=None, ge=0)
    reasons: list[str] = Field(default_factory=list)


class DependencyHealth(BaseModel):
    marketplace: str
    checkpointer: str


class HealthResponse(BaseModel):
    status: str
    service: str
    dependencies: DependencyHealth


class MemoryItem(BaseModel):
    key: str
    kind: Literal["style", "outcome"]
    value: str
    evidence_count: int = Field(ge=1)
    category: str | None = None
    promoted_at: datetime


class OutcomeRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    strategy: str = Field(min_length=1, max_length=200)
    replied: bool
    hired: bool = False


class OutcomeResponse(BaseModel):
    recorded: bool = True
    promoted: MemoryItem | None = None


class AnalyticsPersona(BaseModel):
    jobs: int = Field(ge=0)
    bid_or_skip_f1: float = Field(ge=0, le=1)
    scam_precision: float = Field(ge=0, le=1)
    scam_recall: float = Field(ge=0, le=1)
    reply_rate: float = Field(ge=0, le=1)
    hire_rate: float = Field(ge=0, le=1)
    p95_latency_seconds: float = Field(ge=0)
    proposals_submitted: int = Field(default=0, ge=0)
    model_tokens: int = Field(default=0, ge=0)
    model_cost_usd: float = Field(default=0, ge=0)


class AnalyticsCategory(BaseModel):
    proposals: int = Field(ge=0)
    reply_rate: float = Field(ge=0, le=1)
    hire_rate: float = Field(ge=0, le=1)
    connects_spent: int = Field(ge=0)


class RagVariantMetric(BaseModel):
    evidence_recall_at_5: float = Field(ge=0, le=1)
    ndcg_at_10: float = Field(ge=0, le=1)
    unsupported_claims_after: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)


class AnalyticsResponse(BaseModel):
    generated_at: str
    scope: str
    personas: dict[str, AnalyticsPersona]
    rag_variants: dict[str, RagVariantMetric]
    categories: dict[str, AnalyticsCategory] = Field(default_factory=dict)
    connects_spent: int = Field(default=0, ge=0)
    top_rejection_reasons: dict[str, int] = Field(default_factory=dict)


class PipelineCard(BaseModel):
    proposal_id: str
    job_id: str
    title: str
    status: Literal["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]
    connects_spent: int = Field(default=0, ge=0)
    data_origin: str


class PipelineResponse(BaseModel):
    cards: list[PipelineCard]


class ConversationSummary(BaseModel):
    conversation_id: str
    proposal_id: str | None = None
    client_name: str
    messages: list[dict[str, object]]


class MessagesResponse(BaseModel):
    threads: list[ConversationSummary]


class ConversationStartRequest(BaseModel):
    inbound_message: str = Field(min_length=1, max_length=5000)
    free_slots: list[str] = Field(default_factory=list, max_length=20)


class ConversationRunResponse(BaseModel):
    thread_id: str
    conversation_id: str
    status: str
    state: dict[str, object]
