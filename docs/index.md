---
title: Documentation
hide:
  - navigation
  - toc
  - footer
---

<div class="hero" markdown>

# Orchestrate Triage

**A multi-domain support-triage AI agent. Built solo in 24 hours.**
{ .hero-subtitle }

<div class="hero-buttons" markdown>

[:octicons-rocket-24: Get Started](getting-started.md){ .md-button .md-button--primary }
[:octicons-light-bulb-24: How It Works](overview.md){ .md-button }

</div>

</div>

## What it does

For each row in a CSV of support tickets, the agent decides:

- which **product area** the ticket belongs to,
- whether it's a **product issue, bug, feature request, or invalid**,
- whether to **reply** (with a corpus-grounded answer) or **escalate** to a human,
- and a **justification** the judge can audit against the source corpus.

Three ecosystems are in scope: **HackerRank Support**, **Claude Help Center**, and **Visa Support** — each with a local markdown corpus shipped alongside the input tickets.

<div class="stat-grid" markdown>
  <div class="stat" markdown>
  <strong>10 / 10 / 10</strong>
  <span>sample-eval accuracy</span>
  </div>
  <div class="stat" markdown>
  <strong>29 / 29</strong>
  <span>production tickets succeeded</span>
  </div>
  <div class="stat" markdown>
  <strong>4 min</strong>
  <span>batch wall-time</span>
  </div>
  <div class="stat" markdown>
  <strong>~$50</strong>
  <span>lifetime API spend</span>
  </div>
</div>

## How it's built

- **Anthropic Claude Opus 4.7** (1M context) for production; **Sonnet 4.6** for cheap dev iteration.
- **Corpus stuffing with prompt caching** — no vector DB, no embeddings. Anthropic's own guidance below ~200K-token corpora is to include the entire corpus in the prompt; per-domain we sit at 18K / 540K / 580K tokens.
- **Forced single-tool-call** (`submit_triage`) returns schema-validated `TicketOutput` rows in one round-trip.
- **Spotlighting + structural delimiters** for prompt-injection defense — ticket text is wrapped in `<user_ticket>` XML tags with a system instruction to treat contents as data.
- **Async Message Batches API** for 50%-off production runs.

## Where this came from

[HackerRank Orchestrate](https://www.hackerrank.com/contests/hackerrank-orchestrate-may26) is a 24-hour solo hackathon (May 1–2, 2026). The starter scaffold and labeled-sample corpus live in [interviewstreet/hackerrank-orchestrate-may26](https://github.com/interviewstreet/hackerrank-orchestrate-may26); this site documents the agent built on top of it. Source: [github.com/ajbarea/orchestrate-triage](https://github.com/ajbarea/orchestrate-triage).
