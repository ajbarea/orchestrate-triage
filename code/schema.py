"""Pydantic schemas for the triage pipeline.

The output schema doubles as the JSON schema for the `submit_triage` tool,
so Anthropic strict mode constrains the model to emit exactly these fields.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Status(StrEnum):
    REPLIED = "replied"
    ESCALATED = "escalated"


class RequestType(StrEnum):
    PRODUCT_ISSUE = "product_issue"
    FEATURE_REQUEST = "feature_request"
    BUG = "bug"
    INVALID = "invalid"


class TicketInput(BaseModel):
    issue: str = Field(..., description="Main ticket body or question.")
    subject: str = Field("", description="May be blank, partial, noisy, or irrelevant.")
    company: str = Field(
        "",
        description="HackerRank, Claude, Visa, or None (or empty). Used for routing.",
    )


class TicketOutput(BaseModel):
    status: Status = Field(
        ...,
        description="`replied` if the agent answers directly; `escalated` for high-risk, sensitive, or unsupported cases.",
    )
    product_area: str = Field(
        ...,
        description="Most relevant support category / domain area drawn from the corpus paths (e.g. 'screen', 'privacy', 'travel_support').",
    )
    response: str = Field(
        ...,
        description="User-facing answer grounded in the provided corpus, or a short escalation/out-of-scope message.",
    )
    justification: str = Field(
        ...,
        description="Concise (1-3 sentences) explanation of the routing and answering decision, traceable to the corpus.",
    )
    request_type: RequestType = Field(..., description="Best-fit request classification.")


def output_tool_schema() -> dict:
    """Return a JSON schema dict for the `submit_triage` tool input."""
    return TicketOutput.model_json_schema()


CSV_COLUMNS = [
    "Issue",
    "Subject",
    "Company",
    "Response",
    "Product Area",
    "Status",
    "Request Type",
    "Justification",
]
"""Column order for the predictions CSV. Matches sample_support_tickets.csv exactly."""
