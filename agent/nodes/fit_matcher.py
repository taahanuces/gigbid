from __future__ import annotations

import re

from agent.handoffs import EvidenceItem, FitReport, JobSpec, RequirementEvidence

TOKEN_PATTERN = re.compile(r"[a-z0-9+#.-]+")


def _tokens(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.lower()))


def match_fit(job: JobSpec, evidence: list[EvidenceItem]) -> FitReport:
    requirements = list(dict.fromkeys([*job.required_skills, *job.deliverables]))
    matrix: list[RequirementEvidence] = []
    matched_skills: list[str] = []
    missing_skills: list[str] = []

    for requirement in requirements:
        requirement_tokens = _tokens(requirement)
        scored: list[tuple[float, EvidenceItem]] = []
        for item in evidence:
            item_tokens = _tokens(" ".join([item.title, item.text, *item.skills]))
            overlap = len(requirement_tokens.intersection(item_tokens))
            score = overlap / max(1, len(requirement_tokens))
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        ids = [item.evidence_id for score, item in scored[:3] if score >= 0.3]
        supported = bool(ids)
        matrix.append(
            RequirementEvidence(
                requirement=requirement,
                evidence_ids=ids,
                supported=supported,
                explanation=(
                    f"Supported by {', '.join(ids)}."
                    if supported
                    else "No sufficiently relevant verified evidence was found."
                ),
            )
        )
        if requirement in job.required_skills:
            (matched_skills if supported else missing_skills).append(requirement)

    supported_count = sum(item.supported for item in matrix)
    score = supported_count / max(1, len(matrix))
    evidence_ids = list(
        dict.fromkeys(evidence_id for item in matrix for evidence_id in item.evidence_ids)
    )
    return FitReport(
        score=round(score, 3),
        requirement_matrix=matrix,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        evidence_ids=evidence_ids,
        explanation=f"{supported_count} of {len(matrix)} requirements have evidence.",
    )
