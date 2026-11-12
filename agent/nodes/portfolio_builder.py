from __future__ import annotations

import re

from pydantic import BaseModel, Field

from agent.handoffs import DataOrigin, EvidenceItem


class CaseStudyCandidate(BaseModel):
    repository: str
    title: str
    summary: str
    verified_technologies: list[str] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    status: str = "pending_human_approval"


TECHNOLOGY_PATTERNS = {
    "Python": re.compile(r"\bpython\b|\.py\b", re.IGNORECASE),
    "TypeScript": re.compile(r"\btypescript\b|\.tsx?\b", re.IGNORECASE),
    "FastAPI": re.compile(r"\bfastapi\b", re.IGNORECASE),
    "React": re.compile(r"\breact\b", re.IGNORECASE),
    "Postgres": re.compile(r"\bpostgres(?:ql)?\b", re.IGNORECASE),
    "Next.js": re.compile(r"\bnext(?:\.js|js)\b", re.IGNORECASE),
    "Node.js": re.compile(r"\bnode(?:\.js|js)\b", re.IGNORECASE),
    "Docker": re.compile(r"\bdocker(?:file)?\b", re.IGNORECASE),
    "Redis": re.compile(r"\bredis\b", re.IGNORECASE),
    "Celery": re.compile(r"\bcelery\b", re.IGNORECASE),
    "Pandas": re.compile(r"\bpandas\b", re.IGNORECASE),
    "scikit-learn": re.compile(r"\bscikit[- ]learn\b|\bsklearn\b", re.IGNORECASE),
}
OUTCOME_CLAIM = re.compile(
    r"(?:\b\d+(?:\.\d+)?%|\b\d[\d,]*\s+(?:users|customers|clients)|"
    r"\$\s?\d|\b(?:guarantee|fastest|best-in-class|revenue)\b)",
    re.IGNORECASE,
)


def build_case_study_candidate(
    *, repository: str, readme: str, code_manifest: dict[str, str]
) -> CaseStudyCandidate:
    combined = "\n".join([readme, *code_manifest.keys(), *code_manifest.values()])
    technologies = [
        name for name, pattern in TECHNOLOGY_PATTERNS.items() if pattern.search(combined)
    ]
    title = readme.splitlines()[0].lstrip("# ").strip() if readme.strip() else repository
    summary = (
        f"Repository evidence shows an implementation using {', '.join(technologies)}."
        if technologies
        else "Repository imported; technologies require human verification."
    )
    unsupported_claims = [
        line.strip().lstrip("-* ")
        for line in readme.splitlines()
        if OUTCOME_CLAIM.search(line) and not line.lstrip().startswith("#")
    ]
    return CaseStudyCandidate(
        repository=repository,
        title=title,
        summary=summary,
        verified_technologies=technologies,
        evidence_paths=["README.md", *sorted(code_manifest)],
        unsupported_claims=list(dict.fromkeys(unsupported_claims)),
    )


def approve_case_study_candidate(
    candidate: CaseStudyCandidate,
    *,
    evidence_id: str,
    tenant_id: str,
    persona: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        tenant_id=tenant_id,
        persona=persona,
        type="github_case_study",
        title=candidate.title,
        text=candidate.summary,
        source=f"github://{candidate.repository}",
        project=candidate.repository,
        skills=candidate.verified_technologies,
        outcome="repository_verified_human_approved",
        data_origin=DataOrigin.PRIVATE_USER_DATA,
        generator_version="portfolio-builder-v1",
    )
