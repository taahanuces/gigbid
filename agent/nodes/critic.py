from __future__ import annotations

from agent.handoffs import ClaimVerificationReport, Critique, JobSpec, ProposalDraft

GENERIC_OPENINGS = ("dear hiring manager", "i am passionate", "i am excited to apply")


def critique_proposal(
    job: JobSpec,
    draft: ProposalDraft,
    verification: ClaimVerificationReport,
) -> Critique:
    issues: list[str] = []
    instructions: list[str] = []
    lower = draft.cover_letter.lower()
    if lower.startswith(GENERIC_OPENINGS):
        issues.append("generic_opening")
        instructions.append("Open with a detail specific to the client's deliverable.")
    word_count = len(draft.cover_letter.split())
    if word_count > 250:
        issues.append("too_long")
        instructions.append("Reduce the proposal to at most 250 words.")
    if verification.unsupported_after:
        issues.append("unsupported_claims")
        instructions.append("Remove or rewrite every unsupported claim.")
    title_terms = set(job.title.lower().split())
    personalization = len(title_terms.intersection(lower.split())) / max(1, len(title_terms))
    grounding = 1 - verification.unsupported_after / max(1, len(verification.assessments))
    return Critique(
        passed=not issues,
        issues=issues,
        revision_instructions=instructions,
        grounding_score=round(grounding, 3),
        personalization_score=round(min(1.0, personalization), 3),
    )
