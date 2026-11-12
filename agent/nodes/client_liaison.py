from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from agent.security import find_injected_instructions


class MessageIntent(StrEnum):
    QUESTION = "question"
    NEGOTIATION = "negotiation"
    INTERVIEW = "interview"
    SCAM_SIGNAL = "scam_signal"
    OTHER = "other"


class LiaisonDraft(BaseModel):
    intent: MessageIntent
    reply: str
    proposed_slots: list[str] = Field(default_factory=list)
    requires_approval: bool = True
    risk_signals: list[str] = Field(default_factory=list)


def draft_client_reply(message: str, free_slots: list[str] | None = None) -> LiaisonDraft:
    lower = message.lower()
    injections = find_injected_instructions(message)
    if injections or any(term in lower for term in ("telegram", "pay outside", "crypto wallet")):
        return LiaisonDraft(
            intent=MessageIntent.SCAM_SIGNAL,
            reply="",
            risk_signals=[*injections, "possible off-platform request"],
        )
    if any(term in lower for term in ("interview", "call", "meet")):
        slots = (free_slots or [])[:3]
        return LiaisonDraft(
            intent=MessageIntent.INTERVIEW,
            reply="Thanks for the invitation. Here are several available times in my timezone.",
            proposed_slots=slots,
        )
    if any(term in lower for term in ("rate", "budget", "price", "discount")):
        return LiaisonDraft(
            intent=MessageIntent.NEGOTIATION,
            reply=(
                "Thanks for sharing the budget. I can confirm scope and milestones before "
                "revising the quote."
            ),
        )
    if "?" in message:
        return LiaisonDraft(
            intent=MessageIntent.QUESTION,
            reply=(
                "Thanks for the question. I will answer using the agreed project scope and "
                "verified experience."
            ),
        )
    return LiaisonDraft(intent=MessageIntent.OTHER, reply="Thanks for the update. I have noted it.")
