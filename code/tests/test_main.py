"""Tests for resume / merge / cost-estimate helpers in main.py (no API)."""

from __future__ import annotations

import csv
from pathlib import Path

from main import (
    _estimate_cost,
    _load_output_rows,
    _merge_with_prior,
    read_already_processed,
    write_output,
)
from schema import CSV_COLUMNS, RequestType, Status, TicketInput, TicketOutput


def _write_sample_output(path: Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def test_read_already_processed_empty(tmp_path: Path) -> None:
    """Missing file or zero-byte file yields an empty set."""
    p = tmp_path / "nope.csv"
    assert read_already_processed(p) == set()
    p.touch()
    assert read_already_processed(p) == set()


def test_read_already_processed_skips_blank_issues(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    _write_sample_output(
        out,
        [
            {
                "issue": "real ticket",
                "subject": "",
                "company": "Visa",
                "response": "x",
                "product_area": "general_support",
                "status": "replied",
                "request_type": "product_issue",
            },
            {
                "issue": "",  # blank — must be skipped
                "subject": "",
                "company": "",
                "response": "",
                "product_area": "",
                "status": "replied",
                "request_type": "invalid",
            },
        ],
    )
    seen = read_already_processed(out)
    assert seen == {"real ticket"}


def test_estimate_cost_matches_published_rates() -> None:
    """Opus 4.7 standard pricing (Apr 2026): in $15/MT, out $75/MT, read $1.50/MT, create $18.75/MT.

    1M of each should cost: 15 + 75 + 1.50 + 18.75 = 110.25
    """
    usage = {
        "input": 1_000_000,
        "output": 1_000_000,
        "cache_read": 1_000_000,
        "cache_create": 1_000_000,
    }
    assert abs(_estimate_cost(usage) - 110.25) < 1e-6


def test_estimate_cost_zero_when_empty() -> None:
    assert _estimate_cost({"input": 0, "output": 0, "cache_read": 0, "cache_create": 0}) == 0.0


def test_load_output_rows_keys_by_issue(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    _write_sample_output(
        out,
        [
            {
                "issue": "issue-a",
                "subject": "subA",
                "company": "HackerRank",
                "response": "respA",
                "product_area": "screen",
                "status": "replied",
                "request_type": "product_issue",
            },
        ],
    )
    rows = _load_output_rows(out)
    assert "issue-a" in rows
    assert rows["issue-a"]["status"] == "replied"
    assert rows["issue-a"]["product_area"] == "screen"


def test_write_output_uses_lowercase_snake_case_schema(tmp_path: Path) -> None:
    """Output CSV header + status/request_type values are lowercase snake_case."""
    out = tmp_path / "out.csv"
    inputs = [
        TicketInput(issue="i1", subject="s1", company="HackerRank"),
        TicketInput(issue="i2", subject="s2", company="Visa"),
        TicketInput(issue="i3", subject="s3", company="None"),
    ]
    outputs: list[TicketOutput | None] = [
        TicketOutput(
            status=Status.REPLIED,
            product_area="screen",
            response="r1",
            justification="j1",
            request_type=RequestType.PRODUCT_ISSUE,
        ),
        TicketOutput(
            status=Status.ESCALATED,
            product_area="general_support",
            response="r2",
            justification="j2",
            request_type=RequestType.BUG,
        ),
        None,  # exercises the model-failed fallback row
    ]
    write_output(out, inputs, outputs)

    with open(out, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert list(reader.fieldnames or []) == [
            "issue",
            "subject",
            "company",
            "response",
            "product_area",
            "status",
            "request_type",
            "justification",
        ]
        rows = list(reader)
    assert rows[0]["status"] == "replied"
    assert rows[1]["status"] == "escalated"
    assert rows[2]["status"] == "escalated"
    assert rows[0]["request_type"] == "product_issue"
    assert rows[1]["request_type"] == "bug"
    assert rows[2]["request_type"] == "invalid"


def test_merge_with_prior_preserves_prior_when_new_is_none(tmp_path: Path) -> None:
    """If --resume is set and a ticket already has a prior row, we keep the prior."""
    inputs = [
        TicketInput(issue="issue-a", subject="", company="HackerRank"),
        TicketInput(issue="issue-b", subject="", company="Visa"),
    ]
    outputs: list = [None, None]
    prior = {
        "issue-a": {
            "issue": "issue-a",
            "subject": "",
            "company": "HackerRank",
            "response": "old respA",
            "product_area": "screen",
            "status": "replied",
            "request_type": "product_issue",
        }
    }
    merged_in, merged_out = _merge_with_prior(inputs, outputs, prior)
    assert len(merged_in) == 2
    assert len(merged_out) == 2
    # issue-a recovered from prior
    assert merged_out[0].response == "old respA"
    assert merged_out[0].status.value == "replied"
    # issue-b stays None (the new run didn't process it and there was no prior)
    assert merged_out[1] is None
