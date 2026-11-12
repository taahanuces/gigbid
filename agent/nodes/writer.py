from __future__ import annotations

from agent.handoffs import (
    EvidenceItem,
    FitReport,
    JobSpec,
    PriceQuote,
    ProposalClaim,
    ProposalDraft,
)


def draft_proposal(
    job: JobSpec,
    fit: FitReport,
    evidence: list[EvidenceItem],
    price: PriceQuote,
) -> ProposalDraft:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    claims: list[ProposalClaim] = []
    paragraphs = [f"Your {job.title.lower()} project calls for a careful, reproducible delivery."]

    for index, mapping in enumerate(fit.requirement_matrix, start=1):
        valid_ids = [item for item in mapping.evidence_ids if item in evidence_by_id]
        if not valid_ids:
            continue
        source = evidence_by_id[valid_ids[0]]
        sentence = (
            f"For {mapping.requirement}, I can draw on {source.title}, where I "
            f"{source.text.rstrip('.').lower()} [{source.evidence_id}]."
        )
        claim_id = f"claim-{index}"
        claims.append(ProposalClaim(claim_id=claim_id, sentence=sentence, evidence_ids=valid_ids))
        paragraphs.append(sentence)

    paragraphs.append(
        f"I would confirm the milestones first, then deliver within the agreed scope at "
        f"{price.amount:.0f} {price.currency}."
    )
    questions = {
        question: "I would answer this after confirming the available data and success criteria."
        for question in job.screening_questions
    }
    return ProposalDraft(
        job_id=job.job_id,
        cover_letter="\n\n".join(paragraphs),
        screening_answers=questions,
        claims=claims,
    )
