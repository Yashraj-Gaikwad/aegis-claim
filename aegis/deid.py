import re

_REDACTION_PATTERNS = (
    (
        "SSN",
        re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
        "[REDACTED_SSN]",
    ),
    (
        "DATE",
        re.compile(
            r"\b(?:(?:DOB|date\s+of\s+birth)\s*[:\-]?\s*)?"
            r"(?:(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}"
            r"|(?:19|20)\d{2}[/-](?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01]))\b",
            re.IGNORECASE,
        ),
        "[REDACTED_DATE]",
    ),
    (
        "PHONE",
        re.compile(
            r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?!\d)"
        ),
        "[REDACTED_PHONE]",
    ),
    (
        "EMAIL",
        re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        "[REDACTED_EMAIL]",
    ),
)


def scrub_phi(text: str) -> tuple[str, list[str]]:
    scrubbed = text
    detected_types: list[str] = []
    for redaction_type, pattern, replacement in _REDACTION_PATTERNS:
        scrubbed, count = pattern.subn(replacement, scrubbed)
        if count:
            detected_types.append(redaction_type)
    return scrubbed, detected_types
