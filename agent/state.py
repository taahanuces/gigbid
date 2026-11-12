from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from agent.handoffs import (
    ApprovalDecision,
    ApprovalPayload,
    BidDecision,
    ClaimVerificationReport,
    ComplianceVerdict,
    Critique,
    EvidenceItem,
    FitReport,
    JobSpec,
    MarketplaceReceipt,
    Outcome,
    PriceQuote,
    ProposalDraft,
    RiskReport,
)


class GigBidState(TypedDict, total=False):
    trace_id: str
    thread_id: str
    tenant_id: str
    user_id: str
    user_floor: float
    persona: str
    max_connects_per_bid: int
    weekly_connects_budget: int
    connects_balance: int
    job_id: str
    raw_job: dict[str, Any]
    job_spec: JobSpec
    risk_report: RiskReport
    fit_report: FitReport
    evidence: list[EvidenceItem]
    portfolio_evidence: list[EvidenceItem]
    decision: BidDecision
    price_quote: PriceQuote
    proposal_draft: ProposalDraft
    claim_verification: ClaimVerificationReport
    critique: Critique
    compliance_verdict: ComplianceVerdict
    approval_payload: ApprovalPayload
    approval_decision: ApprovalDecision
    marketplace_receipt: MarketplaceReceipt
    outcome: Outcome
    revision_count: int
    step_count: Annotated[int, operator.add]
    token_count: Annotated[int, operator.add]
    model_usage: Annotated[list[dict[str, Any]], operator.add]
    style_edit_patterns: Annotated[list[str], operator.add]
    status: str
    events: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]
