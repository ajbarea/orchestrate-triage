"""Corpus loader tests (no API).

Skipped when the upstream `data/` corpus is not present on disk. This repo
(orchestrate-triage) doesn't redistribute the corpus — it lives in
`interviewstreet/hackerrank-orchestrate-may26`. Local development with both
repos side-by-side runs these tests; CI on the portfolio repo skips them.
The non-corpus tests (normalize_company, etc.) still run.
"""

from __future__ import annotations

import pytest

from corpus import DATA_ROOT, HR_EXCLUDE_SUBDIRS, load_domain, normalize_company

_corpus_present = (DATA_ROOT / "visa").exists()
needs_corpus = pytest.mark.skipif(
    not _corpus_present,
    reason=f"data/ corpus not present at {DATA_ROOT}; clone the starter repo to enable",
)


@needs_corpus
@pytest.mark.parametrize("c", ["hackerrank", "claude", "visa"])
def test_load_domain_nonempty(c: str) -> None:
    blob = load_domain(c)
    assert blob, f"{c} corpus is empty — data/{c} missing?"
    assert '<doc path="' in blob, f"{c} corpus missing doc path tags"


@needs_corpus
def test_visa_corpus_is_smallest() -> None:
    """Visa's domain is order-of-magnitude smaller than the other two.

    After excluding HR's `integrations` + `library` subdirs, HR and Claude
    end up similar in size, so we don't assert ordering between them — just
    that Visa is by far the smallest.
    """
    visa = load_domain("visa")
    claude = load_domain("claude")
    hr = load_domain("hackerrank")
    assert len(visa) * 10 < len(claude)
    assert len(visa) * 10 < len(hr)


@needs_corpus
def test_hr_excludes_dev_facing_subdirs() -> None:
    """HR corpus must omit `integrations` and `library` to fit the context window."""
    hr = load_domain("hackerrank")
    for excluded in HR_EXCLUDE_SUBDIRS:
        assert f"data/hackerrank/{excluded}/" not in hr, f"unexpected {excluded} content"


def test_normalize_company_known() -> None:
    assert normalize_company("HackerRank") == "hackerrank"
    assert normalize_company("Claude") == "claude"
    assert normalize_company("Visa") == "visa"
    assert normalize_company("hackerrank") == "hackerrank"


def test_normalize_company_none_variants() -> None:
    for v in (None, "", "  ", "None", "none", "unknown_brand"):
        assert normalize_company(v) is None, f"expected None for {v!r}"


@needs_corpus
def test_corpus_strips_image_urls() -> None:
    hr = load_domain("hackerrank")
    # The aggressive stripper replaces signed image URLs with `[image]`.
    # If any signed URL ('Key-Pair-Id') leaks through, stripping is broken.
    assert "Key-Pair-Id" not in hr, "image URL stripping is not catching signed URLs"
