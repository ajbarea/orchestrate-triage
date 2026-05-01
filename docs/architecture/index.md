# Architecture

```
support_tickets.csv
        │
        ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  main.py                                                     │
   │  ├── argparse: --tickets / --out / --batch / --model /       │
   │  │              --resume / --dry-run / --limit / --verbose   │
   │  ├── csv read → group tickets by `company` for cache locality│
   │  └── dispatch:                                               │
   │       sync path  →  agent.triage()  per ticket               │
   │       --batch    →  batch.run_batch() — Message Batches API  │
   └──────────────────────────────────────────────────────────────┘
        │
        ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  Per-request structure (sync OR batch — identical body)      │
   │                                                              │
   │  system blocks (cache_control: ephemeral, ttl: 1h):          │
   │    [0] SYSTEM_PROMPT  — instructions, escalation criteria,   │
   │                          few-shot examples                   │
   │    [1] <corpus> ... </corpus>                                │
   │           per-domain markdown with frontmatter / image URLs  │
   │           stripped, each file wrapped in <doc path="..."/>   │
   │                                                              │
   │  user message:                                               │
   │    <user_ticket>                                             │
   │    company: HackerRank | Claude | Visa | None                │
   │    subject: ...                                              │
   │    issue:   ...                                              │
   │    </user_ticket>                                            │
   │                                                              │
   │  tools: [submit_triage]   (input_schema = TicketOutput)      │
   │  tool_choice: {type: "tool", name: "submit_triage"}  forced  │
   └──────────────────────────────────────────────────────────────┘
        │
        ▼
   exactly one tool_use block →  validated through pydantic
                              →  written as one row in output.csv
```

## File map

| file | purpose |
|---|---|
| `code/main.py` | CLI entry, argparse, CSV I/O, dispatch (sync vs `--batch`), `--resume` merge, cost estimate |
| `code/agent.py` | system prompt with few-shot examples, `submit_triage` tool definition, sync `triage()` call |
| `code/batch.py` | Anthropic Message Batches API path — build requests, submit, poll, collect results |
| `code/corpus.py` | per-domain markdown loader, frontmatter / image / signed-URL stripping, normalize_company |
| `code/safety.py` | ticket sanitization + spotlight delimiters |
| `code/schema.py` | pydantic models, status / request_type enums, CSV column order |
| `code/eval.py` | run against `sample_support_tickets.csv`, print per-column accuracy and mismatches |
| `code/tests/` | pytest unit tests for safety, corpus, schema, main, batch (no API) |
| `scripts/build_submission.py` | bundle `code/` into a clean submission zip |

## Design pillars

Three architectural choices do most of the load-bearing work — each documented in its own page:

- **[Corpus & Caching](corpus.md)** — why we stuff the per-domain corpus instead of running RAG, and how the 1-hour `extended-cache-ttl-2025-04-11` beta keeps cost under control.
- **[Prompt-Injection Defense](safety.md)** — spotlighting, structural delimiters, escalation criteria. How the French Visa "show me your internal rules" attack lands as a clean escalation with no leakage.
- **[Cost & Determinism](cost.md)** — token economics across Haiku 4.5 / Sonnet 4.6 / Opus 4.7, the 50%-off Message Batches API path, and why we don't need temperature controls for deterministic output.
