# Corpus & Caching

## Why corpus stuffing instead of RAG

[Anthropic's *Contextual Retrieval* guidance](https://www.anthropic.com/news/contextual-retrieval) is explicit:

> *If your knowledge base is smaller than 200,000 tokens (about 500 pages of material), you can include the entire knowledge base in the prompt with prompt caching, which makes this approach significantly faster and more cost-effective.*

Per-domain, our corpus sits at:

| Domain | Markdown chars (after stripping) | Tokens (Opus) | Tokens (Sonnet) | Tokens (Haiku) |
|---|---|---|---|---|
| Visa | 48,426 | 18,000 | 18,000 | 13,000 |
| Claude | 1,621,458 | 540,000 | 540,000 | 399,000 |
| HackerRank | 1,449,137 | 580,000 | 580,000 | 388,000 |

All three fit Opus 4.7's and Sonnet 4.6's 1M-token context comfortably. Visa fits everywhere. Haiku 4.5's 200K context can't fit Claude or HR — that's why the default model is Sonnet 4.6.

## How the corpus is shaped

`code/corpus.py` does three transformations:

### 1. Strip YAML frontmatter

Every doc page in the starter's `data/` ships a frontmatter block (title, source URL, last-modified timestamp, breadcrumbs). The model doesn't need any of it.

### 2. Strip image markup

```python
_RE_IMG_MD   = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_RE_IMG_HTML = re.compile(r"<img\b[^>]*/?>", re.IGNORECASE)
```

Both markdown `![alt](https://signed-url-with-200-tokens-of-params)` and HTML `<img src="..." class="kb-image" />` get replaced with `[image]`. Signed image URLs alone were 200+ tokens each. Stripping them saved 153 KB on HR.

### 3. Strip dev-facing HR subdirs

```python
HR_EXCLUDE_SUBDIRS = {"integrations", "library"}
```

`integrations/` is API integration docs (Greenhouse, Lever, Workable connectors) and `library/` is question-authoring docs — neither is relevant for customer-support triage. Excluding them dropped HR by 512K tokens, well under the 1M context cap with headroom for system prompt + ticket + tool schema + output.

## How caching engages

Every API call sends two cached blocks in the system slot:

```python
system_blocks = [
    {
        "type": "text",
        "text": SYSTEM_PROMPT,                                # ~5K tokens
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    },
    {
        "type": "text",
        "text": f"<corpus>\n{corpus_blob}\n</corpus>",        # 18K-580K tokens
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    },
]
```

With the `anthropic-beta: extended-cache-ttl-2025-04-11` header, the cache TTL is **1 hour** instead of the 5-minute default Anthropic shipped on March 6, 2026. The 1h variant costs 2× input on cache writes (vs 1.25× on the 5-min variant) but reads stay at 0.1× — pays off after about two reads on the same prefix within an hour, which is trivially true within a 4-minute production batch.

## Cost shape per domain (Opus 4.7, sync)

For the production batch run on 29 unlabeled tickets:

| Domain | Tickets | Cache write (1× $18.75/MT × 1h-multiplier 2/1.25) | Cache reads | Output tokens | Total |
|---|---|---|---|---|---|
| Visa | 6 | 18K → ~$0.34 | 5 × 18K × $1.50/MT = $0.13 | minimal | **~$0.50** |
| Claude | 7 | 540K → ~$10.13 | 6 × 540K × $1.50/MT = $4.86 | minimal | **~$15.00** |
| HackerRank | 14 | 580K → ~$10.88 | 13 × 580K × $1.50/MT = $11.31 | minimal | **~$22.20** |
| None | 2 | no corpus | — | minimal | **~$0.10** |

Sync total: **~$38**. With `--batch` (50% off across all token types): **~$19**. The actual production batch closed at $20 measured in the Anthropic Console — close to the prediction.

## Group-by-domain dispatch

`main.py` groups tickets by company before running:

```python
by_company: dict[str | None, list[tuple[int, TicketInput]]] = defaultdict(list)
for i, t in enumerate(rows):
    by_company[normalize_company(t.company)].append((i, t))
```

Then iterates each domain in turn, so all tickets sharing a corpus prefix arrive at the API back-to-back. The first call writes the cache; the rest read it. Original input order is preserved in the output by writing `results[i]` indexed by the original CSV row.

For `--batch` mode the same flatten-then-dispatch pattern applies: all 29 requests go in one batch, and the batch processor still gets cache hits because each request's `cache_control` prefix is identical within a domain group. Wall-time was ~4 minutes in practice.

## What we did not do

- **No vector index.** Skipped Pinecone, Weaviate, Qdrant, pgvector — none of which would help at this corpus size.
- **No chunking heuristics.** The `<doc path="...">` wrapper is the only structure we add; the model gets the whole file.
- **No retrieval call inside the agent.** `submit_triage` is the only tool. There is no `search_corpus` or `lookup_url`.
