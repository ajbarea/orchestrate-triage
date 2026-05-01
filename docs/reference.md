# Reference

A short tour of every module. For the full source, see [github.com/ajbarea/orchestrate-triage](https://github.com/ajbarea/orchestrate-triage).

## `main.py` — CLI entry

```bash
python main.py [--tickets PATH] [--out PATH] [--model NAME]
               [--limit N] [--batch] [--resume] [--dry-run] [--verbose]
```

| flag | default | purpose |
|---|---|---|
| `--tickets` | `../support_tickets/support_tickets.csv` | input CSV |
| `--out` | `../support_tickets/output.csv` | predictions CSV |
| `--model` | `claude-sonnet-4-6` (or `MODEL` env var) | Claude model id |
| `--limit N` | `None` | process only first N tickets |
| `--batch` | off | submit as one async Message Batch (50% off) |
| `--resume` | off | skip tickets already in `--out` |
| `--dry-run` | off | print plan summary, make no API calls |
| `--verbose` | off | print each prediction as it lands |

Returns exit code 0 on success, 2 on credit-balance error, 1 otherwise.

## `agent.py` — sync triage

```python
def triage(
    client: Anthropic,
    ticket: TicketInput,
    corpus_blob: str,
    *,
    model: str = "claude-opus-4-7",
    max_tokens: int = 2048,
) -> tuple[TicketOutput, dict]:
    ...
```

Builds the cached system+corpus prompt, forces a `submit_triage` tool call, validates the result through pydantic, returns the `TicketOutput` plus a usage record (which `main.py` writes to `logs/usage.jsonl` per-ticket).

The system prompt is exposed as `agent.SYSTEM_PROMPT` for tests / inspection. The tool definition is `agent.SUBMIT_TOOL`.

## `batch.py` — Message Batches API

```python
def run_batch(
    client: Anthropic,
    by_company: dict[str | None, list[tuple[int, TicketInput]]],
    *,
    model: str = "claude-opus-4-7",
) -> dict[int, TicketOutput | None]:
    ...
```

Flattens the by-company dict to a single batch (preserving original CSV row indices via `custom_id="ticket-NNN"`), submits, polls every 60s until `processing_status == "ended"`, then re-threads results back into the original ticket order. Hard timeout at 24h (Anthropic's batch SLA).

`build_requests()` and `_build_params()` are the building blocks if you want to construct the payload manually for inspection.

## `corpus.py` — per-domain markdown

```python
def normalize_company(company: str | None) -> str | None: ...
def load_domain(company: str) -> str: ...
def list_subdirs(company: str) -> list[str]: ...
```

`load_domain("hackerrank")` returns the entire HR corpus as a single string with each file wrapped in `<doc path="data/hackerrank/...">...</doc>`. Frontmatter, image markup, and signed-URL params are stripped. The HR-specific subdir exclusions live in `HR_EXCLUDE_SUBDIRS = {"integrations", "library"}`.

`@functools.lru_cache(maxsize=8)` keeps the loaded blob in memory across calls within one Python invocation — particularly useful when `eval.py` runs multiple Sonnet domain groups back to back.

## `safety.py` — sanitization + spotlight wrap

```python
def sanitize(text: str | None) -> str: ...
def wrap_ticket(issue: str, subject: str, company: str) -> str: ...
```

`sanitize` drops ASCII control characters (except newline / tab) and NFC-normalizes unicode. `wrap_ticket` produces the `<user_ticket>` block sent to the model.

## `schema.py` — pydantic models

```python
class Status(StrEnum):       REPLIED, ESCALATED
class RequestType(StrEnum):  PRODUCT_ISSUE, FEATURE_REQUEST, BUG, INVALID

class TicketInput(BaseModel):  issue, subject, company
class TicketOutput(BaseModel): status, product_area, response, justification, request_type

CSV_COLUMNS  = [Issue, Subject, Company, Response, Product Area, Status, Request Type, Justification]
output_tool_schema() → JSON Schema dict for the submit_triage tool
```

`TicketOutput.model_json_schema()` is what we plug into the `submit_triage` tool's `input_schema`, so the schema definition lives in exactly one place.

## `eval.py` — accuracy harness

```bash
python eval.py [--limit N] [--model NAME]
```

Runs the agent against `../support_tickets/sample_support_tickets.csv` (10 labeled rows), compares predicted vs expected on the three structural columns (`status`, `request_type`, `product_area`), prints the per-column accuracy, and dumps every mismatch with predicted-vs-expected side-by-side for human review. Free-text `response` and `justification` are not graded automatically — they need human eyeballs.

## `tests/`

```bash
uv run --group dev pytest tests/ -q
```

Five test files, 31 tests total, **zero API calls** — all run in a few hundred milliseconds.

| file | what it covers |
|---|---|
| `test_safety.py` | sanitize + wrap_ticket: null bytes, unicode preservation, delimiter shape |
| `test_corpus.py` | load_domain non-empty, HR subdir exclusion, image stripping |
| `test_schema.py` | pydantic enum values, CSV column order, schema validation |
| `test_main.py` | resume helpers, cost estimate, output merge logic |
| `test_batch.py` | request construction, custom_id round-trip, no-corpus path |

## `scripts/build_submission.py`

```bash
python scripts/build_submission.py [output_path]
```

Builds a clean zip of `code/` (no `.venv`, `__pycache__`, `logs/`, `.env`, dotfiles, etc.) ready for HackerRank upload. Defaults to `/tmp/orchestrate-code.zip`. Stdlib-only (no system `zip` dependency).
