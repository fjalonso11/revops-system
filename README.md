# revops-system

AI-powered Revenue Operations infrastructure for high-growth startups.

Built by [Francisco Alonso](https://linkedin.com/in/falonso11) — MIT · ex-Oliver Wyman · ex-Clip

---

## Status

**What runs today:** A complete RevOps pipeline — HubSpot sync, validation, a structured Postgres warehouse, a metrics engine across three revenue layers, and AI analysis that reasons about *direction* (improving, deteriorating, flat) by comparing each period against its own history. It is wired to run on a schedule through n8n and deliver a directional revenue brief to Slack, with no manual step in between.

**What it runs on:** Synthetic data. The companies, contacts, and deals are hand-built test records in HubSpot, used to develop and validate the analytical logic across five rolling time windows (7 / 14 / 30 / 60 / 90 days).

**What is not done:** It is not connected to a real client's CRM. The single remaining step before a live commercial conversation is connecting a real HubSpot account — at which point the same pipeline produces directional revenue intelligence on real data without further engineering.

---

## What this is

`revops-system` connects CRM data, a metrics engine, and AI analysis into a single operational layer. It is designed for Series A LatAm startups that need enterprise-grade revenue infrastructure without enterprise-grade headcount or tooling cost.

The pipeline pulls deals, companies, and contacts from HubSpot, validates them, loads them into a structured warehouse, computes revenue metrics across **Volume, Velocity, and Yield**, and asks Claude to analyze the *change* in those metrics over time — not just their current values — before delivering a brief to Slack.

The thesis underneath it: CRM data is not revenue intelligence. A pipeline full of deals tells you what happened. It does not tell you whether retention is decaying, whether the funnel is slowing, or whether this month is better or worse than last. This system is built to answer the second question.

---

## The revenue framework — Volume · Velocity · Yield

| Layer | Question it answers | What it measures |
|---|---|---|
| **Volume** | Is the top of the engine growing? | New customers, MRR, deal flow |
| **Velocity** | Is the engine getting faster or slower? | Lead-to-cash timing, funnel conversion — reported *with sample sizes*, so a rate built on 3 deals is never mistaken for one built on 300 |
| **Yield** | Is revenue quality holding? | Net Revenue Retention — the complete formula: beginning MRR + expansion − contraction − churn |

### How NRR is computed

Net Revenue Retention is the metric most demos get wrong, because the easy version — expansion only — always produces a flattering number above 100%. This system computes the complete formula, treating `churn` and `contraction` as first-class deal types, and it carries an explicit `nrr_is_complete` flag:

```python
# NRR is only complete when churn or contraction data is present.
# When both are zero, NRR is a ceiling — expansion only, no downside captured.
nrr_is_complete = churned_mrr > 0 or contraction_mrr > 0
```

---

## Architecture

```
HubSpot (CRM — input source, treated as noisy, not source of truth)
    │
    ▼
Python sync connector  ──  validates companies / contacts / deals before write
    │                      idempotent upsert on hubspot_id (safe to re-run)
    ▼
Supabase (Postgres warehouse)  ──  5 tables; raw HubSpot payload retained per record
    │                              daily metric snapshots across 5 period windows
    ▼
Metrics engine  ──  Volume · Velocity (with sample sizes) · Yield (complete NRR)
    │
    ▼
Claude API  ──  receives current + prior-period metrics; reasons about direction first
    │
    ▼
n8n  ──  scheduled orchestration: sync → analyze → deliver
    │
    ▼
Slack  ──  directional revenue brief
```

### Engineering notes

- **Idempotent sync** — upserts on `hubspot_id`, so the job is safe to run repeatedly without duplicating records.
- **Validation before write** — companies, contacts, and deals are validated before they touch the warehouse; bad records are caught at the boundary.
- **Raw payload retention** — every synced row keeps its original HubSpot JSON in a `raw_data` column, so no upstream field is ever lost to the sync mapping.
- **Idempotent snapshots** — a unique constraint on `(snapshot_date, period_days, layer, metric_name)` means a re-run overwrites rather than duplicates.
- **Directional analysis** — Claude is given prior-period metrics alongside current ones and asked to reason about the trend before commenting on absolutes. The output is "yield is deteriorating," not "yield is 94%."
- **Sample-size reporting** — every velocity rate is reported with the n it was computed on.

---

## Tech stack

- **Python · FastAPI** — sync engine and REST API
- **Supabase (Postgres)** — commercial data warehouse
- **HubSpot** — CRM input source
- **Claude API (Anthropic)** — analysis engine
- **n8n** — workflow orchestration
- **Slack** — delivery channel
- **Railway** — deployment

---

## Project structure

```
revops-system/
├── src/
│   ├── api/              # FastAPI REST API — key-auth on protected endpoints
│   ├── core/             # Config, Supabase client, Claude AI client
│   ├── integrations/
│   │   ├── hubspot/      # HubSpot sync connector + validation layer
│   │   └── slack/        # Slack delivery
│   └── revenue/          # volume.py · velocity.py · yield_.py · snapshots.py
├── automations/          # n8n workflow definitions
├── db/migrations/        # Supabase schema
└── CLAUDE.md             # development rules
```

---

## How it was built

This system was built with [Claude Code](https://www.anthropic.com/claude-code) — architected, directed, and reviewed by me, implemented in collaboration with the model. The revenue framework, the data model, the metric definitions, and the engineering decisions documented above are mine. Using an AI coding tool to build an AI-powered product is the point, not a caveat.

---

## Contact

Reach out via [LinkedIn](https://linkedin.com/in/falonso11) or [GitHub](https://github.com/fjalonso11).