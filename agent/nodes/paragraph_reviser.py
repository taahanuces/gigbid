from __future__ import annotations

from agent.handoffs import EvidenceItem, JobSpec, PriceQuote, ProposalDraft


def regenerate_paragraph(
    *,
    draft: ProposalDraft,
    paragraph_index: int,
    job: JobSpec,
    evidence: list[EvidenceItem],
    price: PriceQuote,
) -> tuple[str, list[str]]:
    paragraphs = draft.cover_letter.split("\n\n")
    if paragraph_index < 0 or paragraph_index >= len(paragraphs):
        raise IndexError("Paragraph index is outside the proposal")

    if paragraph_index == 0:
        return (
            f"I would approach your {job.title.lower()} as a measurable, reproducible delivery, "
            "with the success criteria agreed before implementation.",
            ["personalized_opening", "scope_first"],
        )
    if paragraph_index == len(paragraphs) - 1:
        return (
            "I would confirm milestones and acceptance checks first, then deliver within the "
            f"agreed scope at {price.amount:.0f} {price.currency}.",
            ["explicit_milestones", "price_preserved"],
        )

    source = evidence[(paragraph_index - 1) % len(evidence)] if evidence else None
    if source is None:
        return (
            f"For {job.required_skills[0] if job.required_skills else 'the core deliverable'}, "
            "I would validate the inputs and acceptance criteria before making an "
            "implementation claim.",
            ["unsupported_claim_avoided"],
        )
    skill = source.skills[0] if source.skills else "the required work"
    return (
        f"For {skill}, the closest verified example is {source.title}: "
        f"{source.text.rstrip('.')} [{source.evidence_id}].",
        ["verified_evidence_only", f"cites:{source.evidence_id}"],
    )
