"""Sanitization + spotlight delimiter tests (no API)."""

from __future__ import annotations

from safety import DELIMITER_CLOSE, DELIMITER_OPEN, sanitize, wrap_ticket


def test_sanitize_strips_null_bytes() -> None:
    assert sanitize("hello\x00 world") == "hello world"


def test_sanitize_preserves_unicode() -> None:
    # French accented chars must survive (test set has a French Visa ticket)
    assert (
        sanitize("Bonjour, ma carte Visa a été bloquée") == "Bonjour, ma carte Visa a été bloquée"
    )


def test_sanitize_preserves_newlines_and_tabs() -> None:
    assert sanitize("line1\nline2\tcol2") == "line1\nline2\tcol2"


def test_sanitize_handles_none_and_empty() -> None:
    assert sanitize(None) == ""
    assert sanitize("") == ""
    assert sanitize("   ") == ""


def test_wrap_ticket_includes_delimiters_and_company_subject_issue() -> None:
    out = wrap_ticket(issue="my problem", subject="urgent", company="Visa")
    assert out.startswith(DELIMITER_OPEN)
    assert out.endswith(DELIMITER_CLOSE)
    assert "company: Visa" in out
    assert "subject: urgent" in out
    assert "issue: my problem" in out


def test_wrap_ticket_uses_none_marker_for_empty_company() -> None:
    out = wrap_ticket(issue="issue", subject="", company="")
    assert "company: None" in out
    assert "subject: (none)" in out
