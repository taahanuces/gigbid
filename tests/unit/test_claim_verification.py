from agent.handoffs import EvidenceItem, ProposalClaim, ProposalDraft
from rag.verify import verify_claims


def test_unsupported_claim_is_removed() -> None:
    supported = "I built a Python forecasting pipeline."
    invented = "I delivered this exact system to ten banks."
    draft = ProposalDraft(
        job_id="job-1",
        cover_letter=f"Opening.\n\n{supported}\n\n{invented}",
        claims=[
            ProposalClaim(claim_id="c1", sentence=supported, evidence_ids=["e1"]),
            ProposalClaim(claim_id="c2", sentence=invented, evidence_ids=[]),
        ],
    )
    evidence = [
        EvidenceItem(
            evidence_id="e1",
            tenant_id="demo",
            persona="data",
            type="case_study",
            title="Forecasting",
            text="built a Python forecasting pipeline",
            source="test",
            skills=["Python", "forecasting"],
        )
    ]
    report = verify_claims(draft, evidence)
    assert report.unsupported_before == 1
    assert invented not in report.corrected_cover_letter
    assert report.unsupported_after == 0


def test_uncited_material_claim_is_discovered_even_when_writer_omits_claim_metadata() -> None:
    invented = "I guarantee I increased revenue by 300% for this exact client."
    draft = ProposalDraft(
        job_id="job-2",
        cover_letter=f"A scoped opening.\n\n{invented}\n\nI would confirm milestones first.",
        claims=[],
    )

    report = verify_claims(draft, [])

    assert report.unsupported_before == 1
    assert report.assessments[0].claim_id == "auto-claim-2"
    assert invented not in report.corrected_cover_letter


def test_uncited_track_record_and_past_proposal_claims_are_removed() -> None:
    invented = "My past proposals consistently won, demonstrating a successful track record."
    draft = ProposalDraft(
        job_id="job-3",
        cover_letter=f"A scoped opening.\n\n{invented}\n\nI would confirm milestones first.",
        claims=[],
    )

    report = verify_claims(draft, [])

    assert report.unsupported_before == 1
    assert invented not in report.corrected_cover_letter


def test_past_proposal_alone_cannot_support_delivery_claim() -> None:
    claim = "Delivered a marketing attribution workbook using Tableau."
    draft = ProposalDraft(
        job_id="job-4",
        cover_letter=f"A scoped opening.\n\n{claim} [proposal-1]",
        claims=[],
    )
    evidence = [
        EvidenceItem(
            evidence_id="proposal-1",
            tenant_id="demo",
            persona="data",
            type="past_proposal",
            title="Marketing attribution proposal",
            text="Proposed a marketing attribution workbook using Tableau.",
            source="test",
            skills=["Tableau"],
            outcome="won",
        )
    ]

    report = verify_claims(draft, evidence)

    assert report.unsupported_before == 1
    assert claim not in report.corrected_cover_letter
