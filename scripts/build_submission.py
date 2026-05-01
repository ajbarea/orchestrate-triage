#!/usr/bin/env python3
"""Build the HackerRank submission zip from code/.

Submission requires a zip of code/ excluding virtualenvs, build artifacts,
the data/ corpus, support_tickets/ CSVs, and any local usage logs.
This script bundles the right files using stdlib zipfile (no system `zip`
required) and prints a contents summary so you can sanity-check before upload.

Usage:
    python scripts/build_submission.py [output_path]
    default output: /tmp/orchestrate-code.zip
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = REPO_ROOT / "code"

EXCLUDED_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "logs",
    ".git",
}

EXCLUDED_NAMES = {
    ".env",
    ".env.local",
    ".DS_Store",
    "uv.lock",
}

EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".jsonl"}


def _included(path: Path) -> bool:
    """True if `path` (relative to CODE_DIR) should ship in the zip."""
    parts = path.parts
    if any(p in EXCLUDED_DIRS for p in parts):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return True


def build(out: Path) -> None:
    if not CODE_DIR.is_dir():
        print(f"fatal: {CODE_DIR} not found", file=sys.stderr)
        sys.exit(1)

    if out.exists():
        out.unlink()

    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in sorted(CODE_DIR.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(CODE_DIR)
            if not _included(rel):
                continue
            zf.write(src, arcname=str(rel))
            n += 1

    size = out.stat().st_size
    print(f"wrote {out} ({_human(size)}, {size:,} bytes, {n} files)")
    print("contents:")
    with zipfile.ZipFile(out) as zf:
        for info in zf.infolist():
            print(f"  {info.file_size:>10,}  {info.filename}")


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/orchestrate-code.zip")
    build(out)
