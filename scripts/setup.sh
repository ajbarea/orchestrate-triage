#!/usr/bin/env bash
# One-line workspace setup for orchestrate-triage.
#
# This repo ships only the agent code. The contest's `data/` corpus and
# `support_tickets/` CSVs live in the interviewstreet/hackerrank-orchestrate-may26
# starter — they're not redistributed here. This script clones the starter,
# layers our agent code + scripts on top, installs deps, and seeds .env.
#
# Usage:
#   bash <(curl -sL https://raw.githubusercontent.com/ajbarea/orchestrate-triage/main/scripts/setup.sh)
#   # or:
#   ./scripts/setup.sh [workspace_dir]
#
# Default workspace dir: ./orchestrate-workspace

set -euo pipefail

WORKSPACE="${1:-orchestrate-workspace}"
STARTER_REPO="https://github.com/interviewstreet/hackerrank-orchestrate-may26.git"
AGENT_REPO="https://github.com/ajbarea/orchestrate-triage.git"

if [[ -d "$WORKSPACE" ]]; then
  echo "fatal: '$WORKSPACE' already exists. Pass a different directory name as the first arg." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "fatal: \`uv\` is required (https://docs.astral.sh/uv/)." >&2
  exit 1
fi

echo "→ Cloning starter (data/ + support_tickets/) into $WORKSPACE/"
git clone --depth 1 "$STARTER_REPO" "$WORKSPACE"

echo "→ Layering agent code on top"
cd "$WORKSPACE"
git clone --depth 1 "$AGENT_REPO" .agent
cp -r .agent/code .agent/scripts .
rm -rf .agent

echo "→ Installing Python deps via uv"
cd code
uv sync

echo "→ Seeding .env from .env.example"
if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo
echo "✓ Workspace ready at: $(cd .. && pwd)"
echo
echo "Next steps:"
echo "  1. Edit $WORKSPACE/code/.env and set ANTHROPIC_API_KEY=sk-ant-..."
echo "  2. cd $WORKSPACE/code"
echo "  3. uv run --group dev pytest tests/ -q   # verify (zero API cost)"
echo "  4. uv run python main.py --dry-run       # plan summary (zero API cost)"
echo "  5. uv run python eval.py --limit 3       # smoke test against samples (~\$1)"
