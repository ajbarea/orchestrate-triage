"""Anthropic Message Batches API path: 50% cost vs sync, async (~30 min typical, 24h hard cap).

Why this exists: the production prediction run is 29 tickets, each with a
~580K-token cached corpus prefix. Run synchronously the cost is ~$40; run as
a batch and Anthropic charges 50% across the board — input, output, cache
read, and cache write. Same model, same quality, just deferred.

We submit all 29 tickets in one batch with `cache_control` set on the system
and corpus blocks. Within the batch, the first request per domain hits
`cache_create`; the remaining requests on the same prefix hit `cache_read`.

Polling cadence: 60s (matches the docs example). Hard timeout: 24h.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from anthropic import Anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from agent import SUBMIT_TOOL, SYSTEM_PROMPT
from corpus import load_domain, normalize_company
from safety import wrap_ticket
from schema import TicketInput, TicketOutput

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 60
POLL_TIMEOUT_SEC = 24 * 60 * 60
EXTENDED_CACHE_BETA = "extended-cache-ttl-2025-04-11"


def _build_params(ticket: TicketInput, corpus_blob: str) -> MessageCreateParamsNonStreaming:
    """Build the per-request params object — same shape as the sync triage call."""
    user_msg = wrap_ticket(ticket.issue, ticket.subject, ticket.company)
    system_blocks: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }
    ]
    if corpus_blob:
        system_blocks.append(
            {
                "type": "text",
                "text": f"<corpus>\n{corpus_blob}\n</corpus>",
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        )
    return MessageCreateParamsNonStreaming(
        model="claude-opus-4-7",
        max_tokens=2048,
        system=system_blocks,
        messages=[{"role": "user", "content": user_msg}],
        tools=[SUBMIT_TOOL],
        tool_choice={"type": "tool", "name": "submit_triage"},
    )


def build_requests(numbered: list[tuple[int, TicketInput]]) -> list[Request]:
    """Construct one batch Request per (index, ticket).

    Each request's `custom_id` is `ticket-NNN` so we can re-thread results
    back to the original CSV row order after the async batch completes.
    """
    requests: list[Request] = []
    for i, t in numbered:
        company = normalize_company(t.company)
        corpus = load_domain(company) if company else ""
        params = _build_params(t, corpus)
        requests.append(Request(custom_id=f"ticket-{i:03d}", params=params))
    return requests


def custom_id_to_index(custom_id: str) -> int:
    """Inverse of the `ticket-NNN` scheme used in build_requests."""
    return int(custom_id.removeprefix("ticket-"))


def submit_and_wait(
    client: Anthropic,
    requests: list[Request],
    *,
    poll_interval_sec: float = POLL_INTERVAL_SEC,
    timeout_sec: float = POLL_TIMEOUT_SEC,
) -> dict[int, TicketOutput | None]:
    """Submit a batch, poll until ended, return {ticket_index: TicketOutput | None}."""
    if not requests:
        return {}

    batch = client.messages.batches.create(
        requests=requests,
        extra_headers={"anthropic-beta": EXTENDED_CACHE_BETA},
    )
    logger.info("submitted batch %s with %d requests", batch.id, len(requests))

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        b = client.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            logger.info("batch %s ended; counts=%s", batch.id, b.request_counts)
            break
        logger.info(
            "batch %s status=%s counts=%s; sleeping %.0fs",
            batch.id,
            b.processing_status,
            b.request_counts,
            poll_interval_sec,
        )
        time.sleep(poll_interval_sec)
    else:
        raise TimeoutError(f"batch {batch.id} did not finish within {timeout_sec}s")

    results: dict[int, TicketOutput | None] = {}
    for r in client.messages.batches.results(batch.id):
        idx = custom_id_to_index(r.custom_id)
        if r.result.type != "succeeded":
            logger.warning(
                "ticket %d batch result type=%s — falling back to None", idx, r.result.type
            )
            results[idx] = None
            continue
        message = r.result.message
        out: TicketOutput | None = None
        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_triage":
                try:
                    out = TicketOutput.model_validate(block.input)
                except Exception as e:
                    logger.warning("ticket %d schema validation failed: %s", idx, e)
                    out = None
                break
        results[idx] = out
    return results


def run_batch(
    client: Anthropic,
    by_company: dict[str | None, list[tuple[int, TicketInput]]],
) -> dict[int, TicketOutput | None]:
    """High-level wrapper: flatten by-company dict to a single batch and submit."""
    flat: list[tuple[int, TicketInput]] = []
    for tickets in by_company.values():
        flat.extend(tickets)
    flat.sort(key=lambda x: x[0])

    requests = build_requests(flat)
    return submit_and_wait(client, requests)
