# revops-system

AI-powered Revenue Operations infrastructure for high-growth startups.

Built by [Francisco Alonso](https://linkedin.com/in/falonso11) — MIT · ex-Oliver Wyman · ex-Clip

---

## Status

**What runs today:** A complete RevOps pipeline — HubSpot sync, validation, a structured Postgres warehouse, a metrics engine across three revenue layers, AI analysis that reasons about *direction* (improving, deteriorating, flat) by comparing each period against its own history, and an external web-intelligence layer that enriches every account and detects churn risk from live web signals. It runs on a schedule through n8n and delivers three briefs to Slack — directional revenue analysis, account intelligence, and per-company churn alerts — with no manual step in between.

**What the data is:** Two different things, deliberately.
- **CRM data is synthetic.** The companies, contacts, and deals are hand-built test records in HubSpot, used to develop and validate the analytical logic across five rolling time windows (7 / 14 / 30 / 60 / 90 days).
- **External intelligence is real.** The enrichment and churn-detection layer runs live web searches against real companies. When the pipeline flags an account as at-risk, it surfaces actual, sourced signals — funding rounds, leadership departures, regulatory exposure, security incidents — not test data.

**What is not done:** It is not connected to a real client's CRM. The single remaining step before a live commercial conversation is connecting a real HubSpot account — at which point the same pipeline produces directional revenue intelligence and churn detection on real data without further engineering.

---

## What this is

`revops-system` connects CRM data, a metrics engine, AI analysis, and external web intelligence into a single operational layer. It is designed for Series A LatAm startups that need enterprise-grade revenue infrastructure without enterprise-grade headcount or tooling cost.

The pipeline pulls deals, companies, and contacts from HubSpot, validates them, loads them into a structured warehouse, computes revenue metrics across **Volume, Velocity, and Yield**, asks Claude to analyze the *change* in those metrics over time — not just their current values — and then looks *outward*: for each account it pulls external web intelligence, and for at-risk accounts it correlates internal revenue signals with real-world negative signals into a churn-risk assessment. All of it is delivered to Slack.

The thesis underneath it: CRM data is not revenue intelligence. A pipeline full of deals tells you what happened. It does not tell you whether retention is decaying, whether the funnel is slowing, or whether this month is better or worse than last. And it tells you nothing about what is happening *around* your accounts in the outside world — a customer whose bank just cut them off is a churn risk your CRM cannot see. This system is built to answer the questions the CRM can't.

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

NRR is a *retention* metric: it measures what happens to the revenue you started a period with. That requires a beginning base — revenue that existed before the window — which the data model captures via deal close dates, not just deal amounts.

---

## External intelligence — enrichment and churn detection

The metrics engine looks inward at CRM data. This layer looks outward at the web, using the [Exa](https://exa.ai) API.

**Account enrichment.** For every company in the warehouse, the pipeline pulls a structured brief of recent developments — funding, product launches, leadership changes, expansion or contraction signals — and delivers it alongside the revenue analysis.

**Churn signal detection.** When the revenue analysis flags churn risk, the pipeline resolves *which* accounts are at risk directly from the deal data (every `churn` and `contraction` deal in the current window), runs a negative-signal web search on each, and asks Claude to synthesize the internal revenue signal with the external evidence into a single churn-risk narrative. One alert per at-risk account, delivered to Slack with sources.

The resolution is dynamic — the at-risk company is derived from the data on every run, never hardcoded. When no account is at risk, the result is an empty set, not a fabricated one.

---

## Architecture

```
HubSpot (CRM — input source, treated as noisy, not source of truth)
    │
    ▼
Python sync connector  ──  validates companies / contacts / deals before write
    │                      idempotent upsert on hubspot_id (safe to re-run)
    │                      resolves deal→company associations from the CRM
    ▼
Supabase (Postgres warehouse)  ──  6 tables; raw HubSpot payload retained per record
    │                              daily metric snapshots across 5 period windows
    ▼
Metrics engine  ──  Volume · Velocity (with sample sizes) · Yield (complete NRR)
    │
    ▼
Claude API  ──  receives current + prior-period metrics; reasons about direction first
    │
    ├─────────────► Exa web intelligence
    │                   • account enrichment (all companies)
    │                   • churn signals (at-risk accounts, resolved from deal data)
    │                   Claude synthesizes internal + external into a churn narrative
    ▼
n8n  ──  scheduled orchestration: sync → enrich → analyze → detect → deliver
    │
    ▼
Slack  ──  directional revenue brief · account intelligence · churn alerts
```

### Engineering notes

- **Idempotent sync** — upserts on `hubspot_id`, so the job is safe to run repeatedly without duplicating records.
- **Validation before write** — companies, contacts, and deals are validated before they touch the warehouse; bad records are caught at the boundary.
- **Association resolution** — deal→company links are read from the CRM's association data and mapped to internal keys, so revenue events resolve to the accounts that own them.
- **Raw payload retention** — every synced row keeps its original HubSpot JSON in a `raw_data` column, so no upstream field is ever lost to the sync mapping.
- **Idempotent snapshots** — a unique constraint on `(snapshot_date, period_days, layer, metric_name)` means a re-run overwrites rather than duplicates.
- **Directional analysis** — Claude is given prior-period metrics alongside current ones and asked to reason about the trend before commenting on absolutes. The output is "yield is deteriorating," not "yield is 94%."
- **Sample-size reporting** — every velocity rate is reported with the n it was computed on.
- **Dynamic churn resolution** — at-risk accounts are derived from deal data on every run, never hardcoded; an empty result is a valid, honest outcome.
- **Interface contracts** — functions that consume external systems (HubSpot, Exa, Claude) carry an explicit output contract in their docstring — what a valid result looks like and where each field derives from. A test asserts these contracts exist, so they can't be silently dropped.
- **Fault ledger** — `FAULTS.md` records every known issue with an explicit disposition (fixed / accepted / watch / blocks); nothing sits undisposed.

---

## Tech stack

- **Python · FastAPI** — sync engine and REST API
- **Supabase (Postgres)** — commercial data warehouse
- **HubSpot** — CRM input source
- **Claude API (Anthropic)** — analysis engine
- **Exa API** — external web intelligence
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
│   │   ├── exa/          # External web intelligence — enrichment + churn signals
│   │   └── slack/        # Slack delivery
│   └── revenue/          # volume.py · velocity.py · yield_.py · churn.py · snapshots.py
├── automations/          # n8n workflow definitions
├── db/migrations/        # Supabase schema
├── test_contracts.py     # asserts external-facing functions keep their output contracts
├── FAULTS.md             # fault disposition ledger
└── CLAUDE.md             # development rules
```

---

## How it was built

This system was built with [Claude Code](https://www.anthropic.com/claude-code) — architected, directed, and reviewed by me, implemented in collaboration with the model. The revenue framework, the data model, the metric definitions, and the engineering decisions documented above are mine. Using an AI coding tool to build an AI-powered product is the point, not a caveat.

---

## Contact

Reach out via [LinkedIn](https://linkedin.com/in/falonso11) or [GitHub](https://github.com/fjalonso11).
