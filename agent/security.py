from __future__ import annotations

import re

INJECTION_PATTERNS = (
    re.compile(r"ignore (?:all|any|the|previous).*instructions", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"developer message", re.IGNORECASE),
    re.compile(r"reveal .*?(?:secret|token|credential|prompt)", re.IGNORECASE),
    re.compile(r"execute .*?(?:command|tool|code)", re.IGNORECASE),
)

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
PAYMENT_PATTERN = re.compile(
    r"\b(?:iban|swift|routing|account|card)\s*(?:number|no\.?|#)?\s*[:=]?\s*[A-Z0-9 -]{6,}",
    re.IGNORECASE,
)


def find_injected_instructions(text: str) -> list[str]:
    return [match.group(0) for pattern in INJECTION_PATTERNS for match in pattern.finditer(text)]


def quote_untrusted(text: str) -> str:
    cleaned = text.replace("```", "''' ")
    return f"<untrusted_marketplace_content>\n{cleaned}\n</untrusted_marketplace_content>"


def redact_pii(text: str) -> str:
    text = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    text = PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    return PAYMENT_PATTERN.sub("[REDACTED_PAYMENT]", text)
