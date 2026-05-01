<div align="center">

<img src="docs/assets/hero.png" width="800" alt="Orchestrate Triage hero — three luminous data streams routed through a futuristic triage center, each terminating at a distinct outcome (replied / escalated / invalid)">

# 🛂 Orchestrate Triage

### Multi-Domain Support-Triage AI Agent

*A terminal AI agent that triages support tickets across **HackerRank**, **Claude**, and **Visa** — corpus-grounded, prompt-injection-defended, async-batch-cheap.*

[![Tests](https://github.com/ajbarea/orchestrate-triage/actions/workflows/tests.yml/badge.svg)](https://github.com/ajbarea/orchestrate-triage/actions/workflows/tests.yml)
[![Documentation](https://github.com/ajbarea/orchestrate-triage/actions/workflows/docs.yml/badge.svg)](https://github.com/ajbarea/orchestrate-triage/actions/workflows/docs.yml)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package_manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude_Opus_4.7-D97757?style=flat-square)](https://www.anthropic.com/claude/opus)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/Docs-Zensical-blue?style=flat-square)](https://ajbarea.github.io/orchestrate-triage/)

---

**Built solo for [HackerRank Orchestrate](https://www.hackerrank.com/contests/hackerrank-orchestrate-may26) (May 1–2, 2026). 100/100/100 on the labeled sample eval. 29/29 on the production batch in 4 minutes.**

```
$ uv run python main.py --batch --model claude-opus-4-7

INFO main: loaded 29 tickets from ../support_tickets/support_tickets.csv
INFO main: --batch: submitting 29 tickets as a single async Anthropic batch (model=claude-opus-4-7)
INFO batch: submitted batch msgbatch_01PLNroVKazr1Zq4uhy2VHXJ with 29 requests
INFO batch: status=in_progress  counts=(processing=29, succeeded=0)  sleeping 60s
INFO batch: status=ended         counts=(succeeded=29)
INFO main: batch returned 29/29 successful triages
INFO main: wrote 29 predictions to ../support_tickets/output.csv
```

</div>

---

## What is this? 🧭

For each row in a CSV of support tickets, the agent decides:

- **status** — reply now, or escalate to a human?
- **request_type** — `product_issue` / `feature_request` / `bug` / `invalid`?
- **product_area** — which support category fits?
- **response** — corpus-grounded user-facing answer (no hallucinated policies)
- **justification** — concise reasoning, traceable to a specific corpus path

Three ecosystems are in scope, each with a local markdown corpus shipped by the contest's starter:

| Ecosystem | Tokens | Tickets in test set |
|---|---|---|
| 🟢 **HackerRank Support** | ~580K | 14 |
| 🟧 **Claude Help Center** | ~540K | 7 |
| 🟦 **Visa Support** | ~18K | 6 |
| ⚫ None / cross-domain | — | 2 |

The contest gave 24 hours. Build time was ~2.

---

## Quick Start 🚀

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.12+ | Required by `anthropic ≥ 0.97` and `pydantic 2` |
| **[uv](https://docs.astral.sh/uv/)** | ≥ 0.5 | Fast, lockfile-deterministic Python packaging |
| **Anthropic API key** | — | From [console.anthropic.com](https://console.anthropic.com/) — separate billing from any Claude.ai subscription |

### Get running

The contest's `data/` corpus and `support_tickets/` CSVs live in the **starter repo** (we don't redistribute them). Lay out the workspace as starter + this code on top:

```bash
# 1. Get the starter (corpus + tickets + problem statement)
git clone https://github.com/interviewstreet/hackerrank-orchestrate-may26.git workspace
cd workspace

# 2. Add this repo's agent code on top of the starter
git clone --depth 1 https://github.com/ajbarea/orchestrate-triage.git _agent
cp -r _agent/code _agent/scripts ./
rm -rf _agent

# 3. Install + configure
cd code
uv sync
cp .env.example .env       # then add ANTHROPIC_API_KEY=sk-ant-...

# 4. Verify (zero API cost)
uv run --group dev pytest tests/ -q       # 31 unit tests
uv run python main.py --dry-run           # corpus + dispatch plan, no API calls

# 5. Run
uv run python eval.py --limit 3                       # smoke test, ~$1
uv run python main.py --batch --model claude-opus-4-7 # full prod, ~$20
```

### Cost cheat sheet

| Command | Cost (Sonnet 4.6 default) | Cost (Opus 4.7) | Wall time |
|---|---|---|---|
| `pytest tests/ -q` | $0 | $0 | <1s |
| `main.py --dry-run` | $0 | $0 | <1s |
| `eval.py --limit 3` | ~$1 | ~$13 | ~1 min |
| `eval.py` (full sample, 10 rows) | ~$5 | ~$25 | ~2 min |
| `main.py` (sync, 29 rows) | ~$8 | ~$40 | ~5 min |
| `main.py --batch` (50% off) | ~$4 | ~$20 | ~5 min |

Default model is **Sonnet 4.6** for cheap dev iteration (1M context, fits all three corpora). Override with `--model claude-opus-4-7` for the final production run, or set `MODEL=…` in `.env`.

> [!TIP]
> **`--resume`** picks up where you left off if a run dies mid-way (credit halt, Ctrl-C, network blip). It re-reads the existing `output.csv` and skips tickets already processed by `Issue` text.

See the [Getting Started guide](https://ajbarea.github.io/orchestrate-triage/getting-started/) for the full command reference, model strategy, and troubleshooting.

---

## What's inside 🧱

| | |
|---|---|
| **Stateless batch CSV processor** | `argparse` + stdlib `csv` + pydantic schema |
| **Per-domain corpus stuffing** | Anthropic prompt caching with the **1-hour extended TTL beta** (`extended-cache-ttl-2025-04-11`) |
| **Forced single-tool-call** | `submit_triage` tool with strict pydantic `input_schema` — constrained decoding can't violate the shape |
| **Prompt-injection defense** | Spotlighting (XML `<user_ticket>` delimiters) + structural sanitization + explicit escalation criteria |
| **Async + 50%-off batch** | Anthropic Message Batches API via `--batch` (50% off all token types, ~30 min wall time) |
| **Recovery** | `--resume` re-reads `output.csv`, skips done tickets; `--dry-run` for plan validation without API |
| **Cost transparency** | Per-call JSONL usage logging at `code/logs/usage.jsonl` |
| **Quality** | 31 pytest unit tests (zero API calls), `ruff`-clean, ty-typed |

---

## Architecture 🏛️

```
support_tickets.csv ─▶ main.py (group tickets by company for cache locality)
                            │
                            ├── sync ──▶ agent.triage()      ─┐
                            │                                  ▼
                            └── --batch ▶ batch.run_batch() ─▶ Anthropic Messages API
                                                                │
   per-request:                                                 │
     system blocks (cache_control, ttl=1h):                     │
       [0] SYSTEM_PROMPT (rules + few-shot examples)            │
       [1] <corpus> per-domain markdown </corpus>               │
     user message:                                              │
       <user_ticket>                                            │
       company / subject / issue                                │
       </user_ticket>                                           │
     tools:        [submit_triage]                              │
     tool_choice:  {type: tool, name: submit_triage}  forced ◀──┘
                                                                │
                                                                ▼
                               TicketOutput (pydantic) → output.csv (8 columns)
```

Single-pass classification, not iterative agentic. One forced tool call per ticket. Cache locality maximized by grouping all tickets in a domain back-to-back.

**Stack:** Python 3.12 · [uv](https://docs.astral.sh/uv/) · [anthropic-python](https://github.com/anthropics/anthropic-sdk-python) ≥ 0.97 · Claude Opus 4.7 / Sonnet 4.6 · [pydantic](https://docs.pydantic.dev) · [pytest](https://pytest.org) · [ruff](https://docs.astral.sh/ruff/) · [Zensical](https://zensical.dev) docs

---

## Documentation 📚

Full docs at **[ajbarea.github.io/orchestrate-triage](https://ajbarea.github.io/orchestrate-triage/)**.

| Page | Content |
|---|---|
| [Overview](https://ajbarea.github.io/orchestrate-triage/overview/) | Problem framing, why corpus stuffing not RAG, what's deliberately cut |
| [Getting Started](https://ajbarea.github.io/orchestrate-triage/getting-started/) | Install, configure, run, troubleshoot |
| [Architecture](https://ajbarea.github.io/orchestrate-triage/architecture/) | System diagram, file map, design pillars |
| [Corpus & Caching](https://ajbarea.github.io/orchestrate-triage/architecture/corpus/) | Per-domain stuffing math, stripping, 1h TTL economics |
| [Prompt-Injection Defense](https://ajbarea.github.io/orchestrate-triage/architecture/safety/) | Spotlighting, structural sanitization, observed real-case behavior |
| [Cost & Determinism](https://ajbarea.github.io/orchestrate-triage/architecture/cost/) | Model-tier strategy, Batch API economics, determinism without temperature |
| [Reference](https://ajbarea.github.io/orchestrate-triage/reference/) | Module-by-module API |

---

## Repository layout 📁

```
.
├── code/                       # the agent — Python 3.12, uv-managed
│   ├── main.py                 #   CLI entry, argparse, CSV I/O, dispatch
│   ├── agent.py                #   sync triage call (forced submit_triage)
│   ├── batch.py                #   async Message Batches API path
│   ├── corpus.py               #   per-domain markdown loader + stripping
│   ├── safety.py               #   sanitize + spotlight delimiters
│   ├── schema.py               #   pydantic models, enums, CSV columns
│   ├── eval.py                 #   sample-eval harness (per-column accuracy)
│   ├── tests/                  #   31 unit tests, zero API calls
│   ├── README.md               #   in-depth design rationale + Apr-2026 SDK notes
│   └── pyproject.toml          #   uv project manifest
├── docs/                       # Zensical docs site (deployed to GitHub Pages)
├── scripts/
│   └── build_submission.py     # bundle code/ into a clean submission zip
├── .github/workflows/          # tests + docs CI
├── pyproject.toml              # docs-build deps (zensical)
├── zensical.toml               # docs site config
├── README.md                   # you are here
└── LICENSE                     # MIT
```

---

## License

MIT — see [LICENSE](./LICENSE).

---

<div align="center">
<sub>Built by <a href="https://github.com/ajbarea">AJ Barea</a> · HackerRank Orchestrate hackathon · May 2026</sub>
</div>
