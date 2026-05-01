"""Entry point: read tickets, dispatch to the agent grouped by company, write output.csv.

Tickets are processed serially within each company group so the cached
per-domain corpus is reused across every ticket in that group (cache reads
at ~0.1× input cost). Determinism: input order is preserved in the output
even though we group by domain internally.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

from agent import TriageError, make_client, triage
from corpus import load_domain, normalize_company
from schema import CSV_COLUMNS, TicketInput, TicketOutput

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = Path(__file__).resolve().parent

logger = logging.getLogger("orchestrate.main")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-domain support-triage agent. Reads tickets, writes predictions.",
    )
    parser.add_argument(
        "--tickets",
        default=str(REPO_ROOT / "support_tickets" / "support_tickets.csv"),
        help="Path to the input tickets CSV (Issue/Subject/Company columns).",
    )
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "support_tickets" / "output.csv"),
        help="Path to write the predictions CSV.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("MODEL", "claude-sonnet-4-6"),
        help=(
            "Claude model id. Defaults to Sonnet 4.6 — has the 1M-token context "
            "the HR + Claude corpora need, ~5x cheaper than Opus, plenty for dev "
            "iteration. Override with --model claude-opus-4-7 for the final "
            "production run, or set MODEL in .env. (Haiku 4.5 only has 200K "
            "context which doesn't fit the HR/Claude corpora.)"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N tickets (for smoke tests).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print each prediction as it lands.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Read existing --out CSV and skip tickets already processed (matched by issue text).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config + load corpus per domain, but make no API calls. Prints a plan summary.",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help=(
            "Submit as one Anthropic Message Batch (50%% off, async). Polls every 60s; "
            "typical wall time ~30 min, hard 24h cap. Use for the production prediction run "
            "where wait time is acceptable; sync mode is better for sample eval iteration."
        ),
    )
    return parser.parse_args(argv)


def read_already_processed(out_path: str | Path) -> set[str]:
    """Return the set of `Issue` strings already present in `out_path`, for --resume."""
    p = Path(out_path)
    if not p.exists() or p.stat().st_size == 0:
        return set()
    seen: set[str] = set()
    try:
        with open(p, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                issue = (row.get("Issue") or "").strip()
                if issue:
                    seen.add(issue)
    except (OSError, csv.Error):
        return set()
    return seen


def read_tickets(path: str | Path) -> list[TicketInput]:
    rows: list[TicketInput] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                TicketInput(
                    issue=row.get("Issue", "") or "",
                    subject=row.get("Subject", "") or "",
                    company=(row.get("Company", "") or "").strip(),
                )
            )
    return rows


def write_output(
    path: str | Path,
    inputs: list[TicketInput],
    outputs: list[TicketOutput | None],
) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for ti, to in zip(inputs, outputs, strict=True):
            if to is None:
                writer.writerow(
                    {
                        "Issue": ti.issue,
                        "Subject": ti.subject,
                        "Company": ti.company,
                        "Response": "",
                        "Product Area": "",
                        "Status": "escalated",
                        "Request Type": "invalid",
                        "Justification": "Model failed to return a valid triage decision.",
                    }
                )
                continue
            writer.writerow(
                {
                    "Issue": ti.issue,
                    "Subject": ti.subject,
                    "Company": ti.company,
                    "Response": to.response,
                    "Product Area": to.product_area,
                    "Status": to.status.value,
                    "Request Type": to.request_type.value,
                    "Justification": to.justification,
                }
            )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)

    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(CODE_DIR / ".env")

    rows = read_tickets(args.tickets)
    if args.limit is not None:
        rows = rows[: args.limit]
    logger.info("loaded %d tickets from %s", len(rows), args.tickets)

    already: set[str] = read_already_processed(args.out) if args.resume else set()
    if already:
        logger.info("--resume: %d tickets already in %s, will skip", len(already), args.out)

    by_company: dict[str | None, list[tuple[int, TicketInput]]] = defaultdict(list)
    for i, t in enumerate(rows):
        if t.issue.strip() in already:
            continue
        by_company[normalize_company(t.company)].append((i, t))

    if args.dry_run:
        print(f"--dry-run: would process {sum(len(v) for v in by_company.values())} tickets:")
        for company in sorted(by_company.keys(), key=lambda x: (x is None, x or "")):
            tickets = by_company[company]
            corpus = load_domain(company) if company else ""
            print(
                f"  {company or 'None':<11}  {len(tickets):>3} tickets  corpus={len(corpus):>9,} chars"
            )
        if already:
            print(f"  (skipping {len(already)} already-processed tickets)")
        return 0

    client = make_client()

    results: list[TicketOutput | None] = [None] * len(rows)
    cumulative = {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0}

    if args.batch:
        from batch import run_batch

        n = sum(len(v) for v in by_company.values())
        logger.info(
            "--batch: submitting %d tickets as a single async Anthropic batch (model=%s)",
            n,
            args.model,
        )
        batch_results = run_batch(client, by_company, model=args.model)
        ok = 0
        for i, out in batch_results.items():
            results[i] = out
            if out is not None:
                ok += 1
        logger.info("batch returned %d/%d successful triages", ok, n)
        write_output(args.out, rows, results)
        return 0

    for company in sorted(by_company.keys(), key=lambda x: (x is None, x or "")):
        tickets = by_company[company]
        corpus = load_domain(company) if company else ""
        logger.info(
            "processing %d %s tickets (corpus chars=%d)",
            len(tickets),
            company or "None",
            len(corpus),
        )

        for i, t in tqdm(tickets, desc=f"{company or 'None':<11}", unit="tk"):
            try:
                out, usage = triage(client, t, corpus, model=args.model)
            except TriageError as e:
                logger.warning("ticket %d failed (%s); falling back to escalation", i, e)
                out = None
                usage = None
            results[i] = out
            if usage:
                cumulative["input"] += usage["input_tokens"]
                cumulative["output"] += usage["output_tokens"]
                cumulative["cache_read"] += usage["cache_read_input_tokens"]
                cumulative["cache_create"] += usage["cache_creation_input_tokens"]
            if args.verbose and out is not None:
                print(
                    f"  [{i:02d}] {t.company or 'None':<11} "
                    f"status={out.status.value:<10} "
                    f"rt={out.request_type.value:<16} "
                    f"pa={out.product_area}"
                )

    # When --resume, merge with previously-written rows so we don't drop them.
    if already:
        prior = _load_output_rows(args.out)
        merged_inputs, merged_outputs = _merge_with_prior(rows, results, prior)
        write_output(args.out, merged_inputs, merged_outputs)
    else:
        write_output(args.out, rows, results)

    cost = _estimate_cost(cumulative)
    logger.info(
        "wrote %d predictions to %s | usage in=%d out=%d cache_read=%d cache_create=%d | est cost ≈ $%.2f",
        len(rows),
        args.out,
        cumulative["input"],
        cumulative["output"],
        cumulative["cache_read"],
        cumulative["cache_create"],
        cost,
    )
    return 0


def _load_output_rows(path: str | Path) -> dict[str, dict[str, str]]:
    """Read existing output.csv into {Issue: row} for resume merging."""
    out: dict[str, dict[str, str]] = {}
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return out
    with open(p, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            issue = (row.get("Issue") or "").strip()
            if issue:
                out[issue] = row
    return out


def _merge_with_prior(
    inputs: list[TicketInput],
    outputs: list[TicketOutput | None],
    prior: dict[str, dict[str, str]],
) -> tuple[list[TicketInput], list]:
    """Yield input/output pairs preserving prior rows where new ones are None."""
    merged_in: list[TicketInput] = []
    merged_out: list = []
    for ti, to in zip(inputs, outputs, strict=True):
        if to is None and ti.issue.strip() in prior:
            row = prior[ti.issue.strip()]
            merged_in.append(ti)
            merged_out.append(_PriorRow(row))
        else:
            merged_in.append(ti)
            merged_out.append(to)
    return merged_in, merged_out


class _PriorRow:
    """Adapter so write_output can serialize an already-written CSV row."""

    def __init__(self, row: dict[str, str]) -> None:
        self._row = row

    @property
    def status(self):
        class _S:
            value = (self._row.get("Status", "") or "").strip()

        return _S()

    @property
    def request_type(self):
        class _R:
            value = (self._row.get("Request Type", "") or "").strip()

        return _R()

    @property
    def product_area(self) -> str:
        return self._row.get("Product Area", "") or ""

    @property
    def response(self) -> str:
        return self._row.get("Response", "") or ""

    @property
    def justification(self) -> str:
        return self._row.get("Justification", "") or ""


def _estimate_cost(usage: dict[str, int]) -> float:
    """Rough USD cost for Opus 4.7 standard pricing (Apr 2026):
    input $15/MT, output $75/MT, cache_read $1.50/MT, cache_create $18.75/MT.
    """
    return (
        usage["input"] * 15.0
        + usage["output"] * 75.0
        + usage["cache_read"] * 1.50
        + usage["cache_create"] * 18.75
    ) / 1_000_000


if __name__ == "__main__":
    sys.exit(main())
