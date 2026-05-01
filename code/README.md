# Multi-Domain Support Triage Agent

A terminal-based AI agent that triages support tickets across **HackerRank**, **Claude**, and **Visa** ecosystems using only the local corpus shipped with the starter repo. Built for HackerRank Orchestrate (May 1–2, 2026).

For every input row in `support_tickets/support_tickets.csv` the agent emits the five required columns: `status`, `product_area`, `response`, `justification`, `request_type`.

## Quick start

```bash
# install deps (uv-managed) and run unit tests
uv sync
uv run --group dev pytest tests/ -q

# run on the eval / sample tickets (10 labeled rows; prints per-column accuracy)
uv run python eval.py
uv run python eval.py --limit 3      # cheap sanity-check first

# run the agent on the test tickets and write predictions (sync)
uv run python main.py \
  --tickets ../support_tickets/support_tickets.csv \
  --out     ../support_tickets/output.csv

# 50%-off path via Anthropic Message Batches API (async, ~30 min wall time)
uv run python main.py --batch \
  --tickets ../support_tickets/support_tickets.csv \
  --out     ../support_tickets/output.csv

# resume after a credit halt (re-uses already-written rows in --out)
uv run python main.py --resume

# validate config + load corpus without any API calls
uv run python main.py --dry-run
```

A `.env` file at the repo root or in `code/` is loaded automatically; only `ANTHROPIC_API_KEY` is required.

### Cost & token footprint (Opus 4.7, Apr 2026 standard pricing)

| Domain     | Tokens (approx.) | First call (cache_create) | Subsequent calls (cache_read) |
|------------|------------------|---------------------------|-------------------------------|
| Visa       | ~16K             | ~$0.30                    | ~$0.02                        |
| Claude     | ~540K            | ~$10.50                   | ~$0.81                        |
| HackerRank | ~580K            | ~$11.10                   | ~$0.87                        |

Cache TTL is set to 1 hour explicitly via the `extended-cache-ttl-2025-04-11` beta header (default is 5 min as of March 2026; 1h survives slow human-in-the-loop iteration). Worst case for the full 29-ticket prediction run is roughly **$40–$50** end-to-end in sync mode, **~$20–$25** with `--batch` (50% discount across all token types).

## Architecture

```
support_tickets.csv ──▶ main.py ──▶ per-ticket pipeline ──▶ output.csv

per-ticket pipeline:
  ┌─ safety.wrap_ticket    spotlighting + structural delimiters
  ├─ corpus.load_domain    routed by ticket.company
  ├─ agent.triage          Claude Opus 4.7, strict-mode tool call
  └─ schema.TicketOutput   pydantic-validated row
```

### Why this design

1. **Corpus stuffing with prompt caching, not RAG.** Anthropic's own guidance for knowledge bases under ~200K tokens is to include the entire corpus in the prompt with `cache_control` rather than retrieve chunks. Visa is ~16K tokens after stripping; Claude ~540K; HackerRank ~580K (after dropping two dev-facing subdirs that aren't customer-triage relevant). Each fits Opus 4.7's 1M-token context, with cache reads at ~0.1× input cost after the first turn in a domain — cheaper *and* more accurate than embeddings on this scale. ([Contextual Retrieval, Anthropic, Sept 2024](https://www.anthropic.com/news/contextual-retrieval))

2. **Tickets grouped by `company` to maximize cache hits.** The cached corpus is reused across every ticket in the same domain. Min cached prefix on Opus 4.7 is 4096 tokens — every per-domain prompt clears that bar by orders of magnitude.

3. **Output via a strict-mode tool call.** A single `submit_triage` tool whose input schema is `TicketOutput` (5 fields, 2 enums, 3 strings). With Anthropic's structured-outputs / strict tool use, constrained decoding literally cannot emit invalid JSON — no parsing, no retries on schema errors. ([Structured Outputs, Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs))

4. **Prompt-injection defense via spotlighting.** Ticket content is wrapped in `<user_ticket>` delimiters; the system prompt instructs the model to treat the contents as data, not instructions. The test set contains a French ticket asking the agent to print all internal rules and exact fraud-detection logic — exactly the threat spotlighting addresses. ([Microsoft Learn — Defend against indirect prompt injection](https://learn.microsoft.com/en-us/security/zero-trust/sfi/defend-indirect-prompt-injection))

5. **Escalation logic in the prompt, not as a heuristic.** Hard-coded triggers ("contains the word fraud → escalate") are brittle. The system prompt enumerates escalation criteria (sensitive/safety/legal, account access disputes, payment disputes, broken-platform reports without a known fix, prompt-injection attempts) and the model returns `status=escalated` with a justification anchored in the corpus or in policy.

6. **Determinism.** `temperature=0`, single-shot per ticket, sorted file iteration when building the corpus blob. Same input yields the same output across runs.

7. **Eval harness.** `eval.py` runs the agent against the 10 labeled samples and reports per-column accuracy — used to iterate on the system prompt, escalation triggers, and product-area extraction before touching the test set.

### What we deliberately did not do

- **No vector DB / embedding-based RAG.** Overkill at this corpus size; adds an embedding service dependency and chunk-tuning yak-shaving.
- **No multi-agent orchestration.** Single-pass classify-and-respond is the right primitive; fan-out wouldn't improve grounding.
- **No web calls or scraping.** `data/` is the sole source of truth; the model is instructed to escalate when the corpus does not cover the ticket.

## Submission contents

The HackerRank submission requires three files:
- this `code/` directory zipped (excluding `.venv/`, `__pycache__/`, build artifacts)
- the populated `support_tickets/output.csv`
- the chat transcript at `~/hackerrank_orchestrate/log.txt`

## File map

| file              | purpose                                                                       |
|-------------------|-------------------------------------------------------------------------------|
| `main.py`         | CLI entry: argparse, CSV read/write, dispatch (sync or `--batch`), `--resume` |
| `agent.py`        | Anthropic client, system prompt + few-shot examples, `submit_triage` tool     |
| `batch.py`        | Anthropic Message Batches API path (50% off, async)                           |
| `corpus.py`       | per-domain markdown loader, frontmatter + img + signed-URL stripping          |
| `safety.py`       | ticket sanitization + spotlight delimiters                                     |
| `schema.py`       | pydantic models, status / request_type enums, CSV column order                |
| `eval.py`         | run against `sample_support_tickets.csv`, print per-column accuracy           |
| `tests/`          | pytest unit tests for safety, corpus, schema, main, batch (no API)            |

## Apr-2026 notes (Opus 4.7 specifics worth knowing)

- `temperature`, `top_p`, `top_k` were **removed entirely** from the Messages API for `claude-opus-4-7` (released Apr 16, 2026). The API returns `400` if you pass them. Adaptive thinking replaces them; we keep thinking *off* because it can't combine with a forced `tool_choice` — and forcing the `submit_triage` tool call is essential for getting a structured row every time.
- The minimum cached prefix is **4096 tokens**; system prompt + corpus easily clear that bar, so caching engages reliably.
- HackerRank's raw corpus is ~2M tokens — over the 1M context limit. The aggressive stripper (markdown + HTML images, signed URL params, "Last updated" footers) plus excluding the `integrations` and `library` subdirs (dev-facing, not customer-triage relevant) brings it under.
