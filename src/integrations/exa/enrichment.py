"""
Build A — Account Enrichment Node
Fetches Exa company briefs for all companies in Supabase and stores results
in the company_enrichments table. Runs as part of the daily RevOps pipeline.
"""

import logging
from datetime import datetime, timezone
from supabase import Client
from src.integrations.exa.client import company_brief

log = logging.getLogger(__name__)


def enrich_all_companies(db: Client, period_days: int = 90) -> dict:
    """
    Fetches an Exa brief for every company in the companies table
    and upserts it into company_enrichments.

    Returns a summary dict: {enriched, skipped, errors}
    """
    result = {"enriched": 0, "skipped": 0, "errors": []}

    companies = db.table("companies").select(
        "id, name, domain"
    ).not_.is_("domain", "null").execute()

    if not companies.data:
        log.warning("No companies with domains found — skipping enrichment.")
        return result

    log.info("Enriching %d companies via Exa...", len(companies.data))

    for company in companies.data:
        company_id = company["id"]
        name = company["name"] or "Unknown"
        domain = company["domain"]

        try:
            brief = company_brief(
                domain=domain,
                company_name=name,
                days=period_days,
            )

            if not brief:
                log.warning("No Exa brief returned for %s (%s) — skipping.", name, domain)
                result["skipped"] += 1
                continue

            today = datetime.now(timezone.utc).date().isoformat()

            db.table("company_enrichments").upsert({
                "company_id": company_id,
                "company_name": name,
                "domain": domain,
                "summary": brief.get("summary"),
                "recent_signals": brief.get("recent_signals"),
                "risk_indicators": brief.get("risk_indicators"),
                "source_urls": brief.get("source_urls"),
                "enriched_date": today,
                "period_days": period_days,
            }, on_conflict="company_id,enriched_date").execute()

            log.info("Enriched: %s (%s)", name, domain)
            result["enriched"] += 1

        except Exception as e:
            msg = f"{name} ({domain}): {e}"
            log.error("Enrichment failed for %s: %s", name, e)
            result["errors"].append(msg)

    log.info(
        "Enrichment complete — enriched=%d skipped=%d errors=%d",
        result["enriched"], result["skipped"], len(result["errors"])
    )
    return result


def get_latest_enrichments(db: Client, limit: int = 3) -> list[dict]:
    """
    Returns the most recently enriched company briefs.
    Used by the daily Slack alert to surface top account intelligence.
    """
    rows = db.table("company_enrichments").select(
        "company_name, domain, summary, recent_signals, risk_indicators, enriched_at"
    ).order("enriched_at", desc=True).limit(limit).execute()

    return rows.data or []
