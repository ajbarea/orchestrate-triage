# Cost & Determinism

## Two-stage model strategy

| stage | model | why |
|---|---|---|
| **Sample eval iteration** | Sonnet 4.6 | 1M context fits all corpora, ~5× cheaper than Opus, plenty of capability for the labeled-sample scoring shape |
| **Production prediction** | Opus 4.7 | Highest-quality calls on nuanced edge cases (multilingual injection, subtle escalation), only run once via `--batch` |
| ~~Anywhere~~ | ~~Haiku 4.5~~ | 200K context can't fit HR (388K Haiku tokens) or Claude (399K Haiku tokens). Only fits Visa. |

Switching is one CLI flag:

```bash
# default: Sonnet 4.6, cheap iteration
uv run python eval.py

# explicit Opus 4.7 for production
uv run python main.py --model claude-opus-4-7 --batch
```

## The Message Batches API path — 50% off

For the production prediction, `--batch` submits all 29 tickets as a single async job:

```python
batch = client.messages.batches.create(requests=[...])
# poll every 60s
while True:
    b = client.messages.batches.retrieve(batch.id)
    if b.processing_status == "ended":
        break
    time.sleep(60)
# stream results
for r in client.messages.batches.results(batch.id):
    ...
```

[Anthropic's pricing page](https://www.anthropic.com/news/message-batches-api) confirms 50% off across all token types — input, output, cache_create, cache_read — with no quality difference vs sync. Most batches finish in under an hour; the 24h hard cap is never close in practice. Our 29-ticket Opus batch closed in **4 minutes** wall-time.

## Token economics

The Opus 4.7 standard rate card (April 2026):

| token type | $/MT | what it covers |
|---|---|---|
| input | $15.00 | uncached prompt content |
| output | $75.00 | completion + tool-call payload |
| cache_create | $18.75 | first time a `cache_control`-tagged block is sent (1.25× input on default 5min TTL; 2× input on 1h extended TTL) |
| cache_read | $1.50 | every subsequent send of the same block within TTL (0.1× input) |

The 1-hour extended TTL via `anthropic-beta: extended-cache-ttl-2025-04-11` costs more on first write but pays back after the second read on the same prefix — trivially true within a per-domain batch.

## Total spend (lifetime, this hackathon)

| phase | what ran | model | cost |
|---|---|---|---|
| pre-credit-bonk dev | 1 smoke + 3 HR + 1 Claude + 3 None on Opus 4.7 | Opus 4.7 | $27 |
| sample eval (Sonnet) | 3-ticket smoke + 10-ticket full + 10-ticket re-eval after prompt fix | Sonnet 4.6 | ~$5–6 |
| **production batch** | 29 unlabeled tickets, Message Batches API | Opus 4.7 + `--batch` | **~$20** |
| **total lifetime** | | | **~$50** |

## How we get determinism without sampling controls

Opus 4.7 (released April 16, 2026) **deprecated `temperature`, `top_p`, and `top_k` entirely** — calls including any of those parameters return HTTP 400. Three things stand in for them:

1. **Forced `tool_choice`.** The model must call `submit_triage` exactly once. There's no path to plain text output.
2. **Strict input schema.** The tool's `input_schema` is the pydantic `TicketOutput` model. Constrained decoding under tool-use guarantees the output cannot violate the schema.
3. **Adaptive thinking off.** `tool_choice` forced is incompatible with `thinking={"type":"adaptive"}`, so we keep thinking disabled. The model still reasons internally, just without an explicit budget.

Same prompt + same model + same corpus → same output. Verified across two re-runs of the sample eval (10/10/10 each time).

## Resilience

Three failure paths, all handled:

- **Rate-limit (429).** Anthropic SDK auto-retries with exponential backoff (default `max_retries=2`). Saw one 47-second wait during the sample eval; recovered cleanly.
- **Credit balance exhausted (400).** `agent.py` catches `BadRequestError` with "credit balance" in the message, prints a clear top-up URL, exits with code 2 — no stack trace mid-run. Saw this happen for real during dev; restart was painless.
- **Partial completion.** `--resume` re-reads the existing `output.csv` and skips tickets already processed (matched by `Issue` text). Lets you survive a credit halt or a Ctrl-C without losing progress.
