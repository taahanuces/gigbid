from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)


class Money(StrictModel):
    amount: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class JobSpec(StrictModel):
    job_id: str = Field(min_length=1)
    client_id: str | None = None
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    deliverables: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    pricing_model: str = "fixed"
    timeline_days: int | None = Field(default=None, ge=1)
    screening_questions: list[str] = Field(default_factory=list)
    hidden_needs: list[str] = Field(default_factory=list)
    connects_cost: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def budget_range_is_ordered(self) -> JobSpec:
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError("budget_min cannot exceed budget_max")
        return self


class RiskFlag(StrEnum):
    OFF_PLATFORM_CONTACT = "off_platform_contact"
    OFF_PLATFORM_PAYMENT = "off_platform_payment"
    UNPAID_WORK = "unpaid_work"
    PROMPT_INJECTION = "prompt_injection"
    UNVERIFIED_PAYMENT = "unverified_payment"
    POOR_CLIENT_HISTORY = "poor_client_history"
    GUARANTEE_REQUEST = "guarantee_request"


class DataOrigin(StrEnum):
    SYNTHETIC = "synthetic"
    REAL_PUBLIC_DATASET = "real_public_dataset"
    PRIVATE_USER_DATA = "private_user_data_not_committed"
    INSTRUCTOR_HIDDEN = "instructor_hidden"
    UNSPECIFIED = "unspecified"


class RiskReport(StrictModel):
    score: float = Field(ge=0, le=1)
    flags: list[RiskFlag] = Field(default_factory=list)
    client_quality_score: float = Field(default=0.5, ge=0, le=1)
    explanation: str = Field(min_length=1)
    blocked: bool = False
    ignored_instructions: list[str] = Field(default_factory=list)


class EvidenceItem(StrictModel):
    evidence_id: str
    tenant_id: str
    persona: str
    type: str
    title: str
    text: str
    source: str
    date: str | None = None
    project: str | None = None
    skills: list[str] = Field(default_factory=list)
    client_industry: str | None = None
    outcome: str | None = None
    data_origin: DataOrigin = DataOrigin.UNSPECIFIED
    generator_version: str | None = None
    relevance_score: float = Field(default=0, ge=0, le=1)


class RequirementEvidence(StrictModel):
    requirement: str
    evidence_ids: list[str] = Field(default_factory=list)
    supported: bool
    explanation: str


class FitReport(StrictModel):
    score: float = Field(ge=0, le=1)
    requirement_matrix: list[RequirementEvidence] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str = ""


class BidAction(StrEnum):
    BID = "bid"
    WATCH = "watch"
    SKIP = "skip"
    NEEDS_ATTENTION = "needs_attention"


class BidDecision(StrictModel):
    action: BidAction
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class PriceQuote(StrictModel):
    amount: float = Field(ge=0)
    currency: str = "USD"
    pricing_model: str = "fixed"
    floor_amount: float = Field(ge=0)
    fair_band_min: float = Field(ge=0)
    fair_band_max: float = Field(ge=0)
    connects_cost: int = Field(ge=0)
    expected_value_positive: bool
    rationale: str
    market_prior_category: str | None = None
    market_prior_sample_size: int | None = Field(default=None, ge=1)
    market_prior_source: str | None = None

    @model_validator(mode="after")
    def fair_band_is_ordered(self) -> PriceQuote:
        if self.fair_band_min > self.fair_band_max:
            raise ValueError("fair_band_min cannot exceed fair_band_max")
        return self


class ProposalClaim(StrictModel):
    claim_id: str
    sentence: str
    evidence_ids: list[str] = Field(default_factory=list)


class ProposalDraft(StrictModel):
    job_id: str
    cover_letter: str
    screening_answers: dict[str, str] = Field(default_factory=dict)
    claims: list[ProposalClaim] = Field(default_factory=list)
    revision: int = Field(default=0, ge=0, le=2)
    status: str = "pending_verification"


class ClaimSupport(StrEnum):
    SUPPORTED = "supported"
    PARTLY_SUPPORTED = "partly_supported"
    UNSUPPORTED = "unsupported"


class ClaimAssessment(StrictModel):
    claim_id: str
    support: ClaimSupport
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str
    replacement: str | None = None


class ClaimVerificationReport(StrictModel):
    assessments: list[ClaimAssessment] = Field(default_factory=list)
    unsupported_before: int = Field(ge=0)
    unsupported_after: int = Field(ge=0)
    corrected_cover_letter: str


class Critique(StrictModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    grounding_score: float = Field(ge=0, le=1)
    personalization_score: float = Field(ge=0, le=1)


class ComplianceVerdict(StrictModel):
    passed: bool
    blocked_rule_ids: list[str] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)
    sanitized_text: str


class DryRunPreview(StrictModel):
    tool_name: str
    payload: dict[str, object]
    connects_cost: int = Field(ge=0)
    side_effects: list[str] = Field(default_factory=list)


class ApprovalAction(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class ApprovalPayload(StrictModel):
    thread_id: str
    draft: ProposalDraft
    evidence: list[EvidenceItem]
    risk_report: RiskReport
    price_quote: PriceQuote
    compliance_verdict: ComplianceVerdict
    dry_run: DryRunPreview
    idempotency_key: str


class ApprovalDecision(StrictModel):
    action: ApprovalAction
    edited_cover_letter: str | None = None
    reason: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def action_has_required_details(self) -> ApprovalDecision:
        if self.action == ApprovalAction.EDIT and not self.edited_cover_letter:
            raise ValueError("edited_cover_letter is required for an edit")
        if self.action == ApprovalAction.REJECT and not self.reason:
            raise ValueError("reason is required for a rejection")
        return self


class MarketplaceReceipt(StrictModel):
    marketplace_id: str
    action: str
    status: str
    idempotency_key: str
    connects_spent: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Outcome(StrictModel):
    job_id: str
    category: str
    viewed: bool = False
    replied: bool = False
    interviewed: bool = False
    hired: bool = False
    final_rate: float | None = Field(default=None, ge=0)
