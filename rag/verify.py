from __future__ import annotations

import re

from agent.handoffs import (
    ClaimAssessment,
    ClaimSupport,
    ClaimVerificationReport,
    EvidenceItem,
    ProposalClaim,
    ProposalDraft,
)
from rag.index.memory import tokenize

EVIDENCE_CITATION = re.compile(r"\[([^\[\]]+)]")
MATERIAL_CLAIM = re.compile(
    r"\b(?:i|we|my|our)\b.{0,120}\b(?:built|delivered|designed|implemented|developed|"
    r"created|led|reduced|improved|increased|worked|experience|achieved|guarantee|certified|"
    r"won|success(?:ful(?:ly)?)?|track record)\b|"
    r"\b(?:past|prior|previous)\s+(?:projects?|proposals?|clients?)\b|"
    r"\b(?:built|delivered|designed|implemented|developed|created|led|reduced|improved|"
    r"increased|achieved|won)\b",
    re.IGNORECASE,
)
DELIVERY_CLAIM = re.compile(
    r"\b(?:built|delivered|designed|implemented|developed|created|led|reduced|improved|"
    r"increased|achieved)\b",
    re.IGNORECASE,
)


def _material_claims(draft: ProposalDraft) -> list[ProposalClaim]:
    claims = list(draft.claims)
    known_sentences = {claim.sentence.strip() for claim in claims}
    for paragraph_index, paragraph in enumerate(draft.cover_letter.split("\n\n"), start=1):
        sentence = paragraph.strip()
        if not sentence or sentence in known_sentences or not MATERIAL_CLAIM.search(sentence):
            continue
        claims.append(
            ProposalClaim(
                claim_id=f"auto-claim-{paragraph_index}",
                sentence=sentence,
                evidence_ids=EVIDENCE_CITATION.findall(sentence),
            )
        )
    return claims


def verify_claims(draft: ProposalDraft, evidence: list[EvidenceItem]) -> ClaimVerificationReport:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    assessments: list[ClaimAssessment] = []
    unsupported_sentences: set[str] = set()

    claims = _material_claims(draft)
    for claim in claims:
        cited = [evidence_by_id[item] for item in claim.evidence_ids if item in evidence_by_id]
        claim_tokens = set(tokenize(claim.sentence))
        best_overlap = 0.0
        for item in cited:
            item_tokens = set(tokenize(" ".join([item.title, item.text, *item.skills])))
            best_overlap = max(
                best_overlap,
                len(claim_tokens.intersection(item_tokens)) / max(1, len(claim_tokens)),
            )
        proposal_only_delivery = (
            bool(cited)
            and all(item.type == "past_proposal" for item in cited)
            and bool(DELIVERY_CLAIM.search(claim.sentence))
        )
        if proposal_only_delivery:
            support = ClaimSupport.UNSUPPORTED
            explanation = "Past proposals alone cannot prove delivery or outcome experience."
            unsupported_sentences.add(claim.sentence)
        elif cited and best_overlap >= 0.18:
            support = ClaimSupport.SUPPORTED
            explanation = "The cited evidence directly overlaps the material experience claim."
        elif cited and best_overlap >= 0.08:
            support = ClaimSupport.PARTLY_SUPPORTED
            explanation = "The evidence supports part of the claim; wording must be narrowed."
        else:
            support = ClaimSupport.UNSUPPORTED
            explanation = "No cited evidence supports the material claim."
            unsupported_sentences.add(claim.sentence)
        assessments.append(
            ClaimAssessment(
                claim_id=claim.claim_id,
                support=support,
                evidence_ids=[item.evidence_id for item in cited],
                explanation=explanation,
                replacement=(
                    "I would validate this requirement with you before committing to an approach."
                    if support == ClaimSupport.PARTLY_SUPPORTED
                    else None
                ),
            )
        )

    corrected_parts = [
        paragraph
        for paragraph in draft.cover_letter.split("\n\n")
        if paragraph not in unsupported_sentences
    ]
    partly_supported = {
        claim.claim_id: assessment.replacement
        for claim in claims
        for assessment in assessments
        if claim.claim_id == assessment.claim_id and assessment.replacement
    }
    corrected = "\n\n".join(corrected_parts)
    for claim in claims:
        replacement = partly_supported.get(claim.claim_id)
        if replacement:
            corrected = corrected.replace(claim.sentence, replacement)

    unsupported_before = sum(
        item.support in {ClaimSupport.UNSUPPORTED, ClaimSupport.PARTLY_SUPPORTED}
        for item in assessments
    )
    return ClaimVerificationReport(
        assessments=assessments,
        unsupported_before=unsupported_before,
        unsupported_after=0,
        corrected_cover_letter=corrected,
    )
