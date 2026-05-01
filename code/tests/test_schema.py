"""Pydantic schema tests (no API)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schema import CSV_COLUMNS, RequestType, Status, TicketInput, TicketOutput, output_tool_schema


def test_status_values() -> None:
    assert Status.REPLIED.value == "replied"
    assert Status.ESCALATED.value == "escalated"


def test_request_type_values() -> None:
    assert {r.value for r in RequestType} == {
        "product_issue",
        "feature_request",
        "bug",
        "invalid",
    }


def test_csv_columns_match_sample() -> None:
    """Output column order must match the sample CSV exactly."""
    assert CSV_COLUMNS == [
        "Issue",
        "Subject",
        "Company",
        "Response",
        "Product Area",
        "Status",
        "Request Type",
    ]


def test_ticket_output_validates_full() -> None:
    out = TicketOutput(
        status="replied",
        product_area="screen",
        response="hello",
        justification="why",
        request_type="product_issue",
    )
    assert out.status == Status.REPLIED
    assert out.request_type == RequestType.PRODUCT_ISSUE


def test_ticket_output_rejects_invalid_enum() -> None:
    with pytest.raises(ValidationError):
        TicketOutput(
            status="banana",
            product_area="screen",
            response="hello",
            justification="why",
            request_type="product_issue",
        )


def test_ticket_input_defaults() -> None:
    t = TicketInput(issue="hi")
    assert t.subject == ""
    assert t.company == ""


def test_output_tool_schema_has_required_fields() -> None:
    s = output_tool_schema()
    required = set(s["required"])
    assert {"status", "product_area", "response", "justification", "request_type"} <= required
