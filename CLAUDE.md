# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this system does

RevOps infrastructure for LatAm startups. It syncs CRM data from HubSpot into Supabase (Postgres), computes three revenue metric layers (Volume / Velocity / Yield), and exposes them via a REST API with Claude AI analysis. n8n handles workflow orchestration by calling this API.

## Commands

```bash
make install       # pip install -e ".[dev]"
make dev           # uvicorn with hot reload on :8000
make test          # pytest
make test-unit     # pytest tests/unit/ -v
make lint          # ruff check
make format        # ruff format
make db-migrate    # apply 001_initial_schema.sql against $SUPABASE_DB_URL
make db-local      # docker compose up -d (local Postgres on :5432)
```

Run a single test: `pytest tests/unit/test_revenue_metrics.py::test_days_between_positive -v`

## Architecture

Four layers map directly to the folder structure:

| Layer | Folder | Role |
|---|---|---|
| Core infrastructure | `src/core/` | Supabase client, Claude API client, Pydantic settings |
| Orchestration | `automations/` + `src/api/routes/webhooks.py` | n8n workflow JSON definitions; inbound webhook receiver |
| CRM integration | `src/integrations/hubspot/` | Fetch + upsert contacts/companies/deals; `sync.py` drives FK-ordered full sync |
| Revenue outcomes | `src/revenue/` | `volume.py`, `velocity.py`, `yield_.py` compute metrics from the DB |

The API (`src/api/`) is a thin FastAPI layer over the above. Sync operations run as FastAPI `BackgroundTasks` and write to `sync_logs`.

## Key data flow

1. `POST /sync/hubspot` → `sync.py:run_full_sync()` → upserts companies → contacts → deals (order enforces FK integrity)
2. `GET /metrics/*` → `src/revenue/*.py` queries Supabase, returns computed dict
3. `POST /ai/analyze` → fetches all three metric dicts → sends to Claude with a cached system prompt → returns analysis
4. `POST /webhooks/n8n` → verifies HMAC signature → dispatches background sync task

## Database schema

Five tables in `db/migrations/001_initial_schema.sql`: `companies`, `contacts`, `deals`, `metrics_snapshots`, `sync_logs`.

The `deals` table is the backbone of all revenue metrics:
- **Volume**: count/sum of `is_won=true` deals in period
- **Velocity**: `created_at → closed_at` on won deals; `became_*_at` timestamps on contacts drive funnel stage timings
- **Yield**: NRR from `newbusiness` vs `existingbusiness` deal types; churn requires stage-down events (not yet in HubSpot sync)

## Configuration

All settings are in `src/core/config.py` (Pydantic `BaseSettings`). Copy `.env.example` → `.env`. Required vars: `SUPABASE_URL`, `SUPABASE_KEY`, `ANTHROPIC_API_KEY`, `HUBSPOT_ACCESS_TOKEN`. Slack and n8n vars are optional.

## Claude AI integration

`src/core/ai/client.py` uses prompt caching (`cache_control: ephemeral`) on the system prompt. The system prompt is ~800 tokens — caching it saves cost on every `/ai/analyze` call. Model is pinned to `claude-sonnet-4-6`.

## n8n workflow definitions

JSON files in `automations/` are imported directly into n8n (Settings → Import workflow). They reference `$env.REVOPS_API_URL` — set this in n8n's environment to point at the running API. Two workflows exist: `hubspot_daily_sync.json` (runs at 06:00 UTC daily) and `weekly_metrics_report.json` (runs Mondays at 08:00 UTC, calls `/ai/analyze` and posts to Slack).

## Deployment (Railway)

Set all env vars from `.env.example` in Railway. Start command: `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`. Supabase DB URL can be found in Supabase → Project Settings → Database.
