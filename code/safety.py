"""Prompt-injection defense for ticket text.

Spotlighting + structural delimiters: wrap user ticket content in clear XML
tags so the system prompt can instruct the model to treat the contents as
*data* rather than instructions. Strip ASCII control chars (except newline /
tab) but preserve unicode so non-English tickets render correctly.
"""

from __future__ import annotations

import unicodedata

DELIMITER_OPEN = "<user_ticket>"
DELIMITER_CLOSE = "</user_ticket>"


def sanitize(text: str | None) -> str:
    """Strip ASCII control chars (except \\n, \\t) and normalize unicode."""
    if not text:
        return ""
    cleaned = "".join(c for c in text if c in "\n\t" or ord(c) >= 0x20)
    cleaned = unicodedata.normalize("NFC", cleaned)
    return cleaned.strip()


def wrap_ticket(issue: str, subject: str, company: str) -> str:
    """Wrap a ticket in spotlight delimiters with company / subject / issue rows."""
    issue = sanitize(issue)
    subject = sanitize(subject)
    company = sanitize(company) or "None"
    if not subject:
        subject = "(none)"
    return (
        f"{DELIMITER_OPEN}\n"
        f"company: {company}\n"
        f"subject: {subject}\n"
        f"issue: {issue}\n"
        f"{DELIMITER_CLOSE}"
    )
