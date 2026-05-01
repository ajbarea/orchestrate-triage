# Getting Started

The code in this repository is the agent layer only. To run end-to-end you also need the starter's `data/` corpus and `support_tickets/` CSVs.

## 1. Clone both repos

```bash
# starter — provides data/, support_tickets/, problem_statement.md
git clone https://github.com/interviewstreet/hackerrank-orchestrate-may26.git starter
cd starter

# this repo — agent code + scripts, sits next to data/ and support_tickets/
git clone https://github.com/ajbarea/orchestrate-triage.git ./_triage
cp -r ./_triage/code .             # so code/ sits next to data/ and support_tickets/
cp -r ./_triage/scripts .          # for build_submission.py
rm -rf ./_triage
```

## 2. Install + configure

```bash
cd code
uv sync
cp .env.example .env               # then fill in ANTHROPIC_API_KEY
```

Only `ANTHROPIC_API_KEY` is required. Optional: `MODEL=claude-sonnet-4-6` (default; switch to `claude-opus-4-7` for production runs).

## 3. Run unit tests (no API)

```bash
uv run --group dev pytest tests/ -q
```

Should be `31 passed`.

## 4. Validate against the labeled samples

```bash
uv run python eval.py --limit 3    # ~$1 — smoke test the pipeline
uv run python eval.py              # full 10-sample run, ~$5 on Sonnet 4.6
```

Per-column accuracy (status / request_type / product_area) prints at the bottom.

## 5. Run the production prediction

Sync mode (immediate, full price):

```bash
uv run python main.py \
  --model claude-opus-4-7 \
  --tickets ../support_tickets/support_tickets.csv \
  --out     ../support_tickets/output.csv
```

Async batch mode (50% off, ~30 min):

```bash
uv run python main.py --batch \
  --model claude-opus-4-7 \
  --tickets ../support_tickets/support_tickets.csv \
  --out     ../support_tickets/output.csv
```

If you bonk on credits mid-run, top up at <https://platform.claude.com/settings/billing> and re-run with `--resume`. Already-processed rows are read from `output.csv` and skipped; the remaining tickets continue from where you stopped.

## 6. Build the submission zip

```bash
python ../scripts/build_submission.py /tmp/orchestrate-code.zip
```

Produces a clean zip of `code/` (no `.venv`, `__pycache__`, `logs/`, `.env`, etc.) ready for upload to HackerRank.

## Troubleshooting

| Error message | Likely cause | Fix |
|---|---|---|
| `Your credit balance is too low` | Anthropic Console balance hit zero | Top up at the billing URL above |
| `prompt is too long: ... > 200000 maximum` | Using Haiku 4.5 with HR or Claude corpus | Switch model to `claude-sonnet-4-6` (1M context) or `claude-opus-4-7` |
| `temperature is deprecated for this model` | Old code path setting temperature on Opus 4.7 | Already removed in `agent.py`; rebuild venv |
| `Thinking may not be enabled when tool_choice forces tool use` | Old code path passing `thinking={"type":"adaptive"}` with forced tool_choice | Already removed in `agent.py`; rebuild venv |
