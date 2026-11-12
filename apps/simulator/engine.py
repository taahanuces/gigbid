from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, cast
from uuid import uuid4

from agent.handoffs import MarketplaceReceipt

PRICE_PATTERN = re.compile(r"\bat\s+([0-9]+(?:\.[0-9]+)?)\s+USD\b", re.IGNORECASE)
GENERIC_OPENINGS = ("i am excited", "dear hiring manager", "to whom it may concern")


@dataclass(slots=True)
class SimulatorState:
    fixture: dict[str, Any]
    default_connects: int = 120
    connects: dict[str, int] = field(default_factory=dict)
    proposals: dict[str, dict[str, object]] = field(default_factory=dict)
    receipts: dict[str, MarketplaceReceipt] = field(default_factory=dict)
    messages: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    outcomes: dict[str, dict[str, object]] = field(default_factory=dict)
    events: list[dict[str, object]] = field(default_factory=list)

    @property
    def jobs(self) -> dict[str, dict[str, object]]:
        jobs = self.fixture.get("jobs")
        if not isinstance(jobs, list) or not all(isinstance(job, dict) for job in jobs):
            raise ValueError("Simulator fixture jobs must be a list of objects")
        return {str(job["job_id"]): cast(dict[str, object], job) for job in jobs if "job_id" in job}

    @property
    def clients(self) -> dict[str, dict[str, object]]:
        clients = self.fixture.get("clients")
        if not isinstance(clients, dict) or not all(
            isinstance(value, dict) for value in clients.values()
        ):
            raise ValueError("Simulator fixture clients must be an object of objects")
        return {str(key): cast(dict[str, object], value) for key, value in clients.items()}

    def balance(self, tenant_id: str) -> int:
        return self.connects.setdefault(tenant_id, self.default_connects)

    def create_draft(
        self,
        *,
        tenant_id: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        if idempotency_key in self.receipts:
            return self.receipts[idempotency_key]
        job_id = str(payload["job_id"])
        job = self.jobs[job_id]
        raw_cost = job.get("connects_cost", 0)
        if not isinstance(raw_cost, (str, int, float)):
            raise ValueError("Job connects_cost must be numeric")
        cost = int(raw_cost)
        if self.balance(tenant_id) < cost:
            raise ValueError("Insufficient Connects")
        proposal_id = f"proposal-{uuid4().hex[:16]}"
        self.connects[tenant_id] = self.balance(tenant_id) - cost
        self.proposals[proposal_id] = {
            **payload,
            "proposal_id": proposal_id,
            "tenant_id": tenant_id,
            "status": "drafted",
        }
        receipt = MarketplaceReceipt(
            marketplace_id=proposal_id,
            action="create_proposal_draft",
            status="draft_created",
            idempotency_key=idempotency_key,
            connects_spent=cost,
        )
        self.receipts[idempotency_key] = receipt
        self.events.append(
            {"type": "proposal_drafted", "proposal_id": proposal_id, "job_id": job_id}
        )
        return receipt

    def submit(
        self, *, tenant_id: str, proposal_id: str, idempotency_key: str
    ) -> MarketplaceReceipt:
        if idempotency_key in self.receipts:
            return self.receipts[idempotency_key]
        proposal = self.proposals[proposal_id]
        if proposal["tenant_id"] != tenant_id:
            raise KeyError(proposal_id)
        proposal["status"] = "submitted"
        outcome = evaluate_proposal(
            proposal=proposal,
            job=self.jobs[str(proposal["job_id"])],
            client=self.clients[str(self.jobs[str(proposal["job_id"])]["client_id"])],
        )
        self.outcomes[proposal_id] = outcome
        conversation_id = f"conversation-{proposal_id}"
        if outcome["replied"]:
            self.messages.setdefault(conversation_id, []).append(
                {
                    "message_id": f"message-{uuid4().hex[:12]}",
                    "direction": "inbound",
                    "body": (
                        "Thanks for the specific proposal. Can you confirm your first "
                        "milestone and availability?"
                    ),
                    "data_origin": "synthetic",
                }
            )
        receipt = MarketplaceReceipt(
            marketplace_id=proposal_id,
            action="submit_proposal",
            status="submitted",
            idempotency_key=idempotency_key,
        )
        self.receipts[idempotency_key] = receipt
        self.events.append({"type": "proposal_submitted", "proposal_id": proposal_id, **outcome})
        return receipt

    def send_message(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
        body: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        if idempotency_key in self.receipts:
            return self.receipts[idempotency_key]
        message_id = f"message-{uuid4().hex[:12]}"
        self.messages.setdefault(conversation_id, []).append(
            {
                "message_id": message_id,
                "direction": "outbound",
                "body": body,
                "tenant_id": tenant_id,
            }
        )
        receipt = MarketplaceReceipt(
            marketplace_id=message_id,
            action="send_message",
            status="sent",
            idempotency_key=idempotency_key,
        )
        self.receipts[idempotency_key] = receipt
        self.events.append(
            {"type": "message_sent", "message_id": message_id, "conversation_id": conversation_id}
        )
        return receipt


def evaluate_proposal(
    *, proposal: dict[str, object], job: dict[str, object], client: dict[str, object]
) -> dict[str, object]:
    text = str(proposal.get("cover_letter", ""))
    lowered = text.lower()
    preferences = client["hidden_preferences"]
    if not isinstance(preferences, dict):
        raise ValueError("Simulator client preferences must be an object")
    must_have = [str(skill).lower() for skill in preferences.get("must_have_skills", [])]
    title_terms = [term for term in str(job.get("title", "")).lower().split() if len(term) > 4]
    security_signals = job.get("security_signals") or []
    score = 0.0
    if must_have and any(skill in lowered for skill in must_have):
        score += 0.25
    if title_terms and any(term in lowered for term in title_terms):
        score += 0.20
    if "[" in text and "]" in text:
        score += 0.20
    words = text.split()
    if 45 <= len(words) <= 350:
        score += 0.20
    generic = lowered.startswith(GENERIC_OPENINGS)
    if not generic:
        score += 0.15
    if security_signals:
        score = 0.0
    match = PRICE_PATTERN.search(text)
    proposed_price = float(match.group(1)) if match else None
    ceiling = float(preferences.get("budget_ceiling") or 0.0)
    within_budget = proposed_price is None or ceiling <= 0 or proposed_price <= ceiling
    reply_threshold = float(preferences.get("reply_threshold") or 0.55)
    hire_threshold = float(preferences.get("hire_threshold") or 0.75)
    viewed = score >= 0.25
    replied = score >= reply_threshold and within_budget
    interviewed = replied and score >= min(1.0, reply_threshold + 0.08)
    hired = interviewed and score >= hire_threshold
    return {
        "job_id": str(job["job_id"]),
        "category": str(job.get("category", "other")),
        "viewed": viewed,
        "replied": replied,
        "interviewed": interviewed,
        "hired": hired,
        "score": round(score, 3),
        "within_budget": within_budget,
        "data_origin": "synthetic_rule_based",
        "explanation": (
            "Deterministic simulator outcome from skill, specificity, evidence, length, "
            "price and safety signals."
        ),
    }
