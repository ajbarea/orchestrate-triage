# Getting Started

This repo is the **agent layer only**. The contest's `data/` corpus and `support_tickets/` CSVs live in the starter at [`interviewstreet/hackerrank-orchestrate-may26`](https://github.com/interviewstreet/hackerrank-orchestrate-may26) — they're not redistributed here, since the contest owns that IP.

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.12+ | Required by `anthropic ≥ 0.97` and `pydantic 2` |
| **[uv](https://docs.astral.sh/uv/)** | ≥ 0.5 | Fast, lockfile-deterministic Python packaging |
| **Anthropic API key** | — | Console account from [console.anthropic.com](https://console.anthropic.com/) — separate billing bucket from any Claude.ai Pro/Max subscription |

## 1. Lay out the workspace

The agent expects `code/` to sit **next to** `data/` and `support_tickets/` (the path resolution in `corpus.py` and `main.py` walks `parent.parent` from the running script). The cleanest layout:

```bash
# starter — provides data/, support_tickets/, problem_statement.md
git clone https://github.com/interviewstreet/hackerrank-orchestrate-may26.git workspace
cd workspace

# this repo — agent code + scripts on top of the starter
git clone --depth 1 https://github.com/ajbarea/orchestrate-triage.git _agent
cp -r _agent/code _agent/scripts ./
rm -rf _agent
```

Result:

```
workspace/
├── code/                # this repo
├── scripts/             # this repo
├── data/                # starter (HR, Claude, Visa markdown corpora)
├── support_tickets/     # starter (sample + test CSVs, output.csv stub)
├── problem_statement.md # starter
├── AGENTS.md            # starter
└── ...
```

## 2. Install + configure

```bash
cd code
uv sync                    # install deps via uv.lock
cp .env.example .env       # then edit .env and add ANTHROPIC_API_KEY=sk-ant-...
```

`ANTHROPIC_API_KEY` is the only required variable. Optional:

| Variable | Default | What it does |
|---|---|---|
| `MODEL` | `claude-sonnet-4-6` | Default model. Override with `claude-opus-4-7` for production. |
| `EFFORT` | `xhigh` | Output-config effort hint. Used by some Anthropic SDK paths. |

## 3. Verify (zero API cost)

```bash
uv run --group dev pytest tests/ -q   # should report 31 passed
uv run python main.py --dry-run       # corpus + per-domain plan, no API
```

`--dry-run` prints the per-domain ticket counts and corpus sizes the agent **would** dispatch, without calling the Anthropic API. Useful before any priced run.

## 4. Smoke test against the labeled samples

```bash
# 3 tickets — quick sanity check (~$1 on Sonnet 4.6, ~$13 on Opus 4.7)
uv run python eval.py --limit 3

# Full 10-row sample eval (~$5 on Sonnet, ~$25 on Opus)
uv run python eval.py
```

`eval.py` compares predicted vs expected on the three structural columns (`status`, `request_type`, `product_area`) and dumps every mismatch with predicted-vs-expected side-by-side for human review.

## 5. Production run

The 29 unlabeled tickets in `support_tickets/support_tickets.csv` → `output.csv`:

=== "Async batch (recommended)"

    ```bash
    uv run python main.py --batch \
      --model claude-opus-4-7 \
      --tickets ../support_tickets/support_tickets.csv \
      --out     ../support_tickets/output.csv
    ```

    Submits all 29 tickets as one Anthropic Message Batch. **50% off** across all token types. ~5 min wall time in practice (24h hard cap).

=== "Sync (immediate, full price)"

    ```bash
    uv run python main.py \
      --model claude-opus-4-7 \
      --tickets ../support_tickets/support_tickets.csv \
      --out     ../support_tickets/output.csv
    ```

    Same code path, no batch discount, immediate results.

## 6. Build the submission zip

```bash
python ../scripts/build_submission.py /tmp/orchestrate-code.zip
```

Produces a clean zip preserving the `code/` prefix (so the grader's path resolution works), excluding `.venv`, `__pycache__`, `logs/`, `.env`, `*.csv`, `*.jsonl`, etc.

## Cost cheat sheet

| Command | Sonnet 4.6 (default) | Opus 4.7 | Wall time |
|---|---|---|---|
| `pytest tests/ -q` | $0 | $0 | <1s |
| `main.py --dry-run` | $0 | $0 | <1s |
| `eval.py --limit 3` | ~$1 | ~$13 | ~1 min |
| `eval.py` (full sample) | ~$5 | ~$25 | ~2 min |
| `main.py` (sync) | ~$8 | ~$40 | ~5 min |
| `main.py --batch` | ~$4 | ~$20 | ~5 min |

Per-domain corpus cache writes amortize across tickets in the same group. First call to a domain pays `cache_create` (~$10 on Opus for HR or Claude); subsequent calls in the same hour pay `cache_read` at 0.1× input cost.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `Your credit balance is too low` | Anthropic Console balance hit zero | Top up at [platform.claude.com/settings/billing](https://platform.claude.com/settings/billing); enable auto-reload to avoid mid-run halts. Then re-run with `--resume` to continue from where you stopped. |
| `prompt is too long: ... > 200000 maximum` | Using **Haiku 4.5** with the HR or Claude corpus | Switch to `claude-sonnet-4-6` (1M context) or `claude-opus-4-7` (1M context). Haiku's 200K cap doesn't fit either domain. |
| `temperature is deprecated for this model` | Old code path setting `temperature` on Opus 4.7 | Already removed in current `agent.py`; rebuild venv with `uv sync` |
| `Thinking may not be enabled when tool_choice forces tool use` | `thinking={"type":"adaptive"}` paired with forced `tool_choice` | Already removed in current `agent.py`; the forced tool_choice is the source of structural determinism — keep it, drop thinking |
| Agent reads empty corpus / escalates everything | Workspace layout: `code/` not next to `data/` | Re-check that `code/`, `data/`, `support_tickets/` are siblings under one parent directory (see step 1) |

## What's next

- **[Architecture](architecture/index.md)** — system diagram and file map
- **[Corpus & Caching](architecture/corpus.md)** — why we stuff instead of doing RAG, and the 1-hour TTL economics
- **[Prompt-Injection Defense](architecture/safety.md)** — how the French Visa injection lands as a clean escalation
- **[Cost & Determinism](architecture/cost.md)** — model-tier strategy, Batch API math, determinism without sampling
- **[Reference](reference.md)** — module-by-module API
