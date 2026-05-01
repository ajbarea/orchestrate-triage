"""Tests for the batch path (no API). Verifies request construction is well-formed."""

from __future__ import annotations

from batch import _build_params, build_requests, custom_id_to_index
from schema import TicketInput


def test_custom_id_round_trip() -> None:
    for i in (0, 7, 28, 999):
        cid = f"ticket-{i:03d}"
        assert custom_id_to_index(cid) == i


def test_build_params_includes_cache_and_tool_choice() -> None:
    t = TicketInput(issue="hi", subject="", company="Visa")
    params = _build_params(t, "<doc path='x'>visa stuff</doc>")
    # MessageCreateParamsNonStreaming behaves like a TypedDict in the SDK
    assert params["model"] == "claude-opus-4-7"
    assert params["tool_choice"] == {"type": "tool", "name": "submit_triage"}
    sys_blocks = params["system"]
    assert len(sys_blocks) == 2
    assert sys_blocks[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert sys_blocks[1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    user = params["messages"][0]["content"]
    assert "<user_ticket>" in user
    assert "company: Visa" in user


def test_build_params_omits_corpus_block_when_empty() -> None:
    t = TicketInput(issue="hi", subject="", company="None")
    params = _build_params(t, "")
    assert len(params["system"]) == 1, "no corpus → only the system instruction block"


def test_build_requests_produces_one_per_ticket() -> None:
    numbered = [
        (0, TicketInput(issue="a", subject="", company="HackerRank")),
        (1, TicketInput(issue="b", subject="", company="Visa")),
        (2, TicketInput(issue="c", subject="", company="None")),
    ]
    reqs = build_requests(numbered)
    assert len(reqs) == 3
    assert {r["custom_id"] for r in reqs} == {"ticket-000", "ticket-001", "ticket-002"}
