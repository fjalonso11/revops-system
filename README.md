# revops-system

AI-powered Revenue Operations infrastructure for high-growth startups.

Built by [Francisco Alonso](https://linkedin.com/in/falonso11) · MIT · Ex-Oliver Wyman · Ex-Clip

---

## What this is

revops-system is a productized RevOps platform that connects CRM data, AI analysis, and automated alerting into a single operational layer. It is designed for Series A LatAm startups that need enterprise-grade revenue infrastructure without enterprise-grade headcount.

The system pulls data from HubSpot, loads it into a structured data warehouse, runs AI-powered analysis across volume, velocity, and yield metrics, and delivers actionable alerts to Slack — fully automated via n8n.

---

## Architecture

```
HubSpot (CRM)
    ↓
Python Sync Connector
    ↓
Supabase (Data Warehouse)
    ↓
Claude AI (Analysis)
    ↓
n8n (Orchestration)
    ↓
Slack (Alerts)
```

### Four-layer RevOps model

| Layer | Purpose | Tools |
|---|---|---|
| Core Infrastructure | Data warehouse + AI brain | Supabase · Claude API |
| Orchestration | Workflow automation | n8n |
| Functional Alignment | CRM sync | HubSpot |
| Revenue Outcomes | Volume · Velocity · Yield | Custom metrics engine |

---

## Tech stack

- **Python** · FastAPI — sync engine and REST API
- **Supabase** (Postgres) — commercial data warehouse
- **HubSpot** — CRM source of truth
- **Claude API** (Anthropic) — AI analysis engine
- **n8n** — workflow orchestration
- **Slack** — alert delivery

---

## Key features

- HubSpot → Supabase full and incremental sync
- Audit trail via sync_logs table
- Revenue metrics across Volume (MRR, new customers), Velocity (lead-to-cash), and Yield (NRR, expansion, churn)
- AI-generated pipeline analysis via Claude
- Automated Slack alerts triggered by n8n workflows

---

## Project structure

```
revops-system/
├── src/
│   ├── api/              # FastAPI REST API
│   ├── core/             # Config, Supabase client, Claude AI client
│   ├── integrations/
│   │   ├── hubspot/      # HubSpot sync connector
│   │   └── slack/        # Slack notifications
│   └── revenue/          # Volume, Velocity, Yield metrics
├── automations/          # n8n workflow JSON files
├── db/migrations/        # Supabase schema
└── CLAUDE.md             # AI development rules
```

---

## Status

Active development. First working slice (HubSpot → Supabase sync) complete.

---

## Contact

This repo is private and available upon request.  
Reach out via [LinkedIn](https://linkedin.com/in/falonso11) or [GitHub](https://github.com/fjalonso11).
