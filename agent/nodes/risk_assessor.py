from __future__ import annotations

from agent.handoffs import JobSpec, RiskFlag, RiskReport
from agent.security import find_injected_instructions


def assess_risk(job: JobSpec, client_history: dict[str, object] | None = None) -> RiskReport:
    text = f"{job.title}\n{job.description}".lower()
    flags: list[RiskFlag] = []
    explanation: list[str] = []
    ignored = find_injected_instructions(text)

    keyword_rules = {
        RiskFlag.OFF_PLATFORM_CONTACT: (
            "telegram",
            "whatsapp",
            "contact me outside",
            "email me directly",
        ),
        RiskFlag.OFF_PLATFORM_PAYMENT: ("pay outside", "crypto payment", "direct payment"),
        RiskFlag.UNPAID_WORK: ("free trial", "unpaid trial", "work for free", "free sample"),
        RiskFlag.GUARANTEE_REQUEST: ("guarantee results", "guaranteed outcome"),
    }
    for flag, phrases in keyword_rules.items():
        if any(phrase in text for phrase in phrases):
            flags.append(flag)
            explanation.append(flag.value.replace("_", " "))

    if ignored:
        flags.append(RiskFlag.PROMPT_INJECTION)
        explanation.append("embedded instructions were isolated and ignored")

    history = client_history or {}
    payment_verified = bool(history.get("payment_verified", True))
    rating = _as_float(history.get("average_rating", 4.0), default=0)
    completed = _as_int(history.get("completed_projects", 0), default=0)
    if not payment_verified:
        flags.append(RiskFlag.UNVERIFIED_PAYMENT)
    if rating < 3 or (completed == 0 and not payment_verified):
        flags.append(RiskFlag.POOR_CLIENT_HISTORY)

    client_quality = min(1.0, max(0.0, rating / 5 * 0.7 + min(completed, 10) / 10 * 0.3))
    weights = {
        RiskFlag.OFF_PLATFORM_CONTACT: 0.35,
        RiskFlag.OFF_PLATFORM_PAYMENT: 0.45,
        RiskFlag.UNPAID_WORK: 0.45,
        RiskFlag.PROMPT_INJECTION: 0.25,
        RiskFlag.UNVERIFIED_PAYMENT: 0.15,
        RiskFlag.POOR_CLIENT_HISTORY: 0.2,
        RiskFlag.GUARANTEE_REQUEST: 0.2,
    }
    score = min(1.0, sum(weights[flag] for flag in set(flags)))
    blocking = {
        RiskFlag.OFF_PLATFORM_PAYMENT,
        RiskFlag.UNPAID_WORK,
    }
    blocked = bool(blocking.intersection(flags)) or score >= 0.7
    return RiskReport(
        score=round(score, 3),
        flags=list(dict.fromkeys(flags)),
        client_quality_score=round(client_quality, 3),
        explanation=("; ".join(explanation) if explanation else "No material risk signal found."),
        blocked=blocked,
        ignored_instructions=ignored,
    )


def _as_float(value: object, *, default: float) -> float:
    if isinstance(value, (str, int, float)):
        return float(value)
    return default


def _as_int(value: object, *, default: int) -> int:
    if isinstance(value, (str, int, float)):
        return int(value)
    return default
