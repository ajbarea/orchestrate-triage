"""Per-domain markdown corpus loader.

For Visa (~18K tokens) and Claude (~344K tokens) the entire domain fits
Opus 4.7's 1M context with room to spare, so we concatenate every markdown
file into a single cached blob and rely on the model + caching to do the
retrieval work.

HackerRank ships ~2M tokens raw — too large. Aggressive stripping (image
URLs, long signed-URL params, frontmatter, "Last updated" footers) cuts it
to ~1.1M, and excluding two dev-facing subdirs (`integrations`,
`library` — about API integrations and question-authoring, irrelevant to
the customer-support tickets in scope) brings it to ~620K, which fits.

Frontmatter blocks and image URLs are stripped to save tokens. Each chunk
is wrapped in a `<doc path="...">` tag so the model can cite source files
in `justification`.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

KNOWN_DOMAINS = {"hackerrank", "claude", "visa"}

# HackerRank subdirs that are dev-facing or content-authoring, not customer
# triage relevant. Removing them keeps the prompt under the 1M context limit.
HR_EXCLUDE_SUBDIRS = {"integrations", "library"}


def normalize_company(company: str | None) -> str | None:
    """Map free-form company strings to corpus dir names; None if not routable."""
    if not company:
        return None
    s = company.strip().lower()
    if s in KNOWN_DOMAINS:
        return s
    if s in {"none", ""}:
        return None
    return None


@lru_cache(maxsize=8)
def load_domain(company: str) -> str:
    """Return concatenated markdown for the given domain.

    For HackerRank, dev-facing subdirs in `HR_EXCLUDE_SUBDIRS` are skipped to
    keep the corpus under the 1M-token context limit.
    """
    if company not in KNOWN_DOMAINS:
        raise ValueError(f"unknown company: {company!r}")

    root = DATA_ROOT / company
    if not root.exists():
        return ""

    excluded = HR_EXCLUDE_SUBDIRS if company == "hackerrank" else set()

    chunks: list[str] = []
    for md_file in sorted(root.rglob("*.md")):
        # Skip files inside excluded top-level subdirs.
        rel_to_company = md_file.relative_to(root)
        if rel_to_company.parts and rel_to_company.parts[0] in excluded:
            continue

        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = _strip_frontmatter(text)
        text = _strip_aggressive(text).strip()
        if not text:
            continue
        rel = md_file.relative_to(DATA_ROOT).as_posix()
        chunks.append(f'<doc path="{rel}">\n{text}\n</doc>')

    return "\n\n".join(chunks)


def list_subdirs(company: str) -> list[str]:
    """Return the top-level subdir names under data/<company>/."""
    if company not in KNOWN_DOMAINS:
        raise ValueError(f"unknown company: {company!r}")
    root = DATA_ROOT / company
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def estimate_tokens(text: str) -> int:
    """Rough token estimate using 3 chars / token (Anthropic BPE on markdown)."""
    return len(text) // 3


def _strip_frontmatter(text: str) -> str:
    """Strip YAML frontmatter delimited by `---` on the first and a later line."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end < 0:
        return text
    return text[end + 5 :]


_RE_IMG_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_RE_IMG_HTML = re.compile(r"<img\b[^>]*/?>", re.IGNORECASE)
_RE_LAST_UPDATED = re.compile(r"^_Last updated:.*$", re.MULTILINE)
_RE_LONG_URL_PAREN = re.compile(r"\(https?://[^)]{120,}\)")
_RE_LONG_URL_QUOTED = re.compile(r'"https?://[^"]{120,}"')
_RE_TRIPLE_NEWLINE = re.compile(r"\n{3,}")


def _strip_aggressive(text: str) -> str:
    """Strip image references and other heavy fixed-width payloads.

    Replaces both markdown `![](url)` and HTML `<img ... />` forms with `[image]`.
    Strips "Last updated" footers, replaces extremely long bare URLs (whether in
    parens or quoted) with a placeholder, and collapses repeated blank lines.
    """
    text = _RE_IMG_MD.sub("[image]", text)
    text = _RE_IMG_HTML.sub("[image]", text)
    text = _RE_LAST_UPDATED.sub("", text)
    text = _RE_LONG_URL_PAREN.sub("(url)", text)
    text = _RE_LONG_URL_QUOTED.sub('"url"', text)
    text = _RE_TRIPLE_NEWLINE.sub("\n\n", text)
    return text
