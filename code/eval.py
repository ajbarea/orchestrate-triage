"""Eval harness: run the agent against sample_support_tickets.csv and report accuracy.

Sample CSV has expected outputs in `Response`, `Product Area`, `Status`,
`Request Type`. We compare predicted vs expected on the structural columns
(status, request_type, product_area) and surface the response text for
qualitative review on mismatches. Free-text response and justification are
not graded automatically — they need human eyeballs.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

from agent import TriageError, make_client, triage
from corpus import load_domain, normalize_company
from schema import TicketInput

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = REPO_ROOT / "support_tickets" / "sample_support_tickets.csv"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Run the agent on the labeled sample tickets.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default="claude-opus-4-7")
    args = parser.parse_args(argv)

    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(CODE_DIR / ".env")

    client = make_client()

    with open(SAMPLE_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[: args.limit]

    by_company: dict[str | None, list[tuple[int, dict]]] = defaultdict(list)
    for i, row in enumerate(rows):
        by_company[normalize_company(row.get("Company", ""))].append((i, row))

    results: list[dict | None] = [None] * len(rows)
    correct: dict[str, int] = {"status": 0, "request_type": 0, "product_area": 0}
    mismatches: list[tuple[int, dict, dict]] = []

    for company in sorted(by_company.keys(), key=lambda x: (x is None, x or "")):
        tickets = by_company[company]
        corpus = load_domain(company) if company else ""
        for i, row in tqdm(tickets, desc=f"{company or 'None':<11}", unit="tk"):
            t = TicketInput(
                issue=row.get("Issue", "") or "",
                subject=row.get("Subject", "") or "",
                company=(row.get("Company", "") or "").strip(),
            )
            try:
                out, _usage = triage(client, t, corpus, model=args.model)
            except TriageError as e:
                print(f"[{i}] FAILED: {e}")
                continue
            results[i] = {
                "predicted": {
                    "status": out.status.value,
                    "product_area": out.product_area,
                    "request_type": out.request_type.value,
                    "response": out.response,
                    "justification": out.justification,
                },
                "expected": {
                    "status": (row.get("Status", "") or "").strip().lower(),
                    "product_area": (row.get("Product Area", "") or "").strip(),
                    "request_type": (row.get("Request Type", "") or "").strip(),
                    "response": (row.get("Response", "") or "").strip(),
                },
                "ticket": {
                    "company": t.company,
                    "subject": t.subject,
                    "issue": t.issue,
                },
            }
            r = results[i]
            row_correct = {}
            for k in ("status", "request_type", "product_area"):
                if r["predicted"][k] == r["expected"][k]:
                    correct[k] += 1
                    row_correct[k] = True
                else:
                    row_correct[k] = False
            if not all(row_correct.values()):
                mismatches.append((i, r, row_correct))

    total = sum(1 for r in results if r is not None)
    print(f"\n{'=' * 60}\nACCURACY (n={total})\n{'=' * 60}")
    for k, n in correct.items():
        pct = (n / total * 100) if total else 0
        print(f"  {k:<14} {n}/{total}  ({pct:.0f}%)")

    if mismatches:
        print(f"\n{'=' * 60}\nMISMATCHES ({len(mismatches)})\n{'=' * 60}")
        for i, r, ok in mismatches:
            print(f"\n--- ticket #{i}  company={r['ticket']['company']!r}")
            print(f"  subject: {r['ticket']['subject'][:100]}")
            print(f"  issue:   {r['ticket']['issue'][:200]}")
            for k in ("status", "request_type", "product_area"):
                marker = "✓" if ok[k] else "✗"
                print(f"  {marker} {k:<14} pred={r['predicted'][k]!r:<25} exp={r['expected'][k]!r}")
            print(f"  predicted response: {r['predicted']['response'][:200]}")
            print(f"  expected response:  {r['expected']['response'][:200]}")
            print(f"  justification:      {r['predicted']['justification'][:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
