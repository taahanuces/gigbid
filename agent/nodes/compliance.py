from __future__ import annotations

import re

from agent.handoffs import ComplianceVerdict, ProposalDraft
from agent.security import EMAIL_PATTERN, PHONE_PATTERN

GUARANTEE_PATTERN = re.compile(r"\b(?:guarantee|guaranteed|100% certain)\b", re.IGNORECASE)


def check_compliance(draft: ProposalDraft) -> ComplianceVerdict:
    text = draft.cover_letter
    blocked: list[str] = []
    comments: list[str] = []
    sanitized = text
    if EMAIL_PATTERN.search(text) or PHONE_PATTERN.search(text):
        blocked.append("no_off_platform_contact")
        comments.append("Contact details were removed.")
        sanitized = EMAIL_PATTERN.sub("[removed]", sanitized)
        sanitized = PHONE_PATTERN.sub("[removed]", sanitized)
    if GUARANTEE_PATTERN.search(text):
        blocked.append("no_guarantees")
        comments.append("Outcome guarantees were removed.")
        sanitized = GUARANTEE_PATTERN.sub("aim to", sanitized)
    return ComplianceVerdict(
        passed=not blocked,
        blocked_rule_ids=blocked,
        comments=comments,
        sanitized_text=sanitized,
    )
