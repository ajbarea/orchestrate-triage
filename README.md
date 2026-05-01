# Orchestrate Triage

A terminal-based, multi-domain support-triage AI agent. Submitted to **HackerRank Orchestrate** (May 1–2, 2026) — a 24-hour solo hackathon to design, build, and ship an AI agent against an open-ended problem statement.

The agent reads a CSV of support tickets and emits structured triage decisions (status, product area, response, justification, request type) grounded in a local markdown corpus across **HackerRank**, **Claude (Anthropic)**, and **Visa** support ecosystems.

## What's in this repo

| path                          | what                                                                  |
|-------------------------------|-----------------------------------------------------------------------|
| [`code/`](./code)             | the agent — Python 3.12, `uv`-managed, runs on Claude Opus 4.7        |
| [`code/README.md`](./code/README.md) | full design rationale + run instructions + April-2026 SDK notes |
| [`scripts/build_submission.py`](./scripts/build_submission.py) | zip the `code/` directory for HackerRank upload |

The HackerRank starter scaffold (problem statement, evaluation criteria, the per-domain markdown corpus under `data/`, and the input CSVs under `support_tickets/`) lives in the contest's repo:

> https://github.com/interviewstreet/hackerrank-orchestrate-may26

To run this agent end-to-end you need that corpus on disk next to `code/`. The repo above is the canonical source.

## Quick start

```bash
git clone https://github.com/interviewstreet/hackerrank-orchestrate-may26.git starter
git clone https://github.com/ajbarea/orchestrate-triage.git           starter/orchestrate
# (or sit `code/` and `scripts/` next to the starter's data/ + support_tickets/)

cd starter/code      # if you laid out as above
uv sync
cp .env.example .env # fill in ANTHROPIC_API_KEY
uv run python eval.py             # run against labeled samples
uv run python main.py --batch     # production run, 50%-off batch path
```

See [`code/README.md`](./code/README.md) for full architecture, cost analysis, and the Apr-2026 Opus 4.7 specifics.

## Design highlights

- **Per-domain corpus stuffing** with `cache_control` + 1-hour extended TTL (`extended-cache-ttl-2025-04-11` beta) — Anthropic's own guidance for knowledge bases under ~200K tokens
- **Forced single-tool-call** (`submit_triage`) for guaranteed schema-valid structured output
- **Spotlighting** (XML `<user_ticket>` delimiters + system instruction) for prompt-injection defense
- **Few-shot examples** in the system prompt to calibrate edge cases (greetings, out-of-scope, escalation)
- **Both sync and async paths**: sync for fast eval iteration, `--batch` (Anthropic Message Batches API) for the 29-ticket production run at 50% off
- **`--resume`** so a mid-run credit halt doesn't lose progress
- **31 pytest unit tests**, ruff-clean, zero API-cost test suite

## License

MIT — see [`LICENSE`](./LICENSE).
