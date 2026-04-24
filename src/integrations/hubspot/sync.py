import sys
import json
import logging
from datetime import datetime, timezone
from supabase import Client
from src.integrations.hubspot import client as hs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_id_map(db: Client, table: str) -> dict[str, str]:
    """Returns {hubspot_id: internal_uuid} for the given table."""
    rows = db.table(table).select("id, hubspot_id").execute()
    return {r["hubspot_id"]: r["id"] for r in rows.data if r.get("hubspot_id")}


def _start_sync_log(db: Client) -> str | None:
    try:
        row = db.table("sync_logs").insert({
            "source": "hubspot",
            "sync_type": "full",
            "status": "running",
            "started_at": _now(),
        }).execute()
        return row.data[0]["id"] if row.data else None
    except Exception as e:
        log.warning("Could not create sync_log entry: %s", e)
        return None


def _finish_sync_log(
    db: Client,
    log_id: str | None,
    status: str,
    records_synced: int,
    errors: list[str],
) -> None:
    if not log_id:
        return
    try:
        db.table("sync_logs").update({
            "status": status,
            "records_synced": records_synced,
            "errors": errors or None,
            "completed_at": _now(),
        }).eq("id", log_id).execute()
    except Exception as e:
        log.warning("Could not update sync_log entry: %s", e)


def sync_companies(db: Client) -> int:
    log.info("Fetching companies from HubSpot...")
    companies = hs.fetch_all_companies()
    log.info("Upserting %d companies into Supabase...", len(companies))
    for company in companies:
        db.table("companies").upsert({
            "hubspot_id": company.hubspot_id,
            "name": company.name,
            "domain": company.domain,
            "industry": company.industry,
            "country": company.country,
            "city": company.city,
            "mrr": company.mrr,
            "arr": company.arr,
            "updated_at": _now(),
            "hubspot_synced_at": _now(),
            "raw_data": company.raw_data,
        }, on_conflict="hubspot_id").execute()
    return len(companies)


def sync_contacts(db: Client, company_id_map: dict[str, str]) -> int:
    log.info("Fetching contacts from HubSpot...")
    contacts = hs.fetch_all_contacts()
    log.info("Upserting %d contacts into Supabase...", len(contacts))
    for contact in contacts:
        db.table("contacts").upsert({
            "hubspot_id": contact.hubspot_id,
            "email": contact.email,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "lifecycle_stage": contact.lifecycle_stage,
            "lead_status": contact.lead_status,
            "became_lead_at": contact.became_lead_at.isoformat() if contact.became_lead_at else None,
            "became_mql_at": contact.became_mql_at.isoformat() if contact.became_mql_at else None,
            "became_sql_at": contact.became_sql_at.isoformat() if contact.became_sql_at else None,
            "became_customer_at": (
                contact.became_customer_at.isoformat() if contact.became_customer_at else None
            ),
            "updated_at": _now(),
            "hubspot_synced_at": _now(),
            "raw_data": contact.raw_data,
        }, on_conflict="hubspot_id").execute()
    return len(contacts)


def sync_deals(
    db: Client,
    company_id_map: dict[str, str],
    contact_id_map: dict[str, str],
) -> int:
    log.info("Fetching deals from HubSpot...")
    deals = hs.fetch_all_deals()
    log.info("Upserting %d deals into Supabase...", len(deals))
    for deal in deals:
        db.table("deals").upsert({
            "hubspot_id": deal.hubspot_id,
            "name": deal.name,
            "pipeline": deal.pipeline,
            "stage": deal.stage,
            "amount": deal.amount,
            "currency": deal.currency,
            "close_date": deal.close_date,
            "is_closed": deal.is_closed,
            "is_won": deal.is_won,
            "type": deal.type,
            "closed_at": deal.closed_at.isoformat() if deal.closed_at else None,
            "company_id": company_id_map.get(deal.hubspot_company_id) if deal.hubspot_company_id else None,
            "contact_id": contact_id_map.get(deal.hubspot_contact_id) if deal.hubspot_contact_id else None,
            "updated_at": _now(),
            "hubspot_synced_at": _now(),
            "raw_data": deal.raw_data,
        }, on_conflict="hubspot_id").execute()
    return len(deals)


def run_full_sync(db: Client) -> dict:
    """Syncs companies → contacts → deals. Order matters for FK resolution."""
    result: dict = {"companies": 0, "contacts": 0, "deals": 0, "errors": []}
    log_id = _start_sync_log(db)

    try:
        result["companies"] = sync_companies(db)
    except Exception as e:
        log.error("companies sync failed: %s", e)
        result["errors"].append(f"companies: {e}")

    company_id_map = _build_id_map(db, "companies")

    try:
        result["contacts"] = sync_contacts(db, company_id_map)
    except Exception as e:
        log.error("contacts sync failed: %s", e)
        result["errors"].append(f"contacts: {e}")

    contact_id_map = _build_id_map(db, "contacts")

    try:
        result["deals"] = sync_deals(db, company_id_map, contact_id_map)
    except Exception as e:
        log.error("deals sync failed: %s", e)
        result["errors"].append(f"deals: {e}")

    total = result["companies"] + result["contacts"] + result["deals"]
    status = "failed" if result["errors"] else "success"
    _finish_sync_log(db, log_id, status, total, result["errors"])

    return result


if __name__ == "__main__":
    from src.core.database.client import get_supabase

    log.info("Starting full HubSpot → Supabase sync")
    db = get_supabase()

    try:
        result = run_full_sync(db)
    except Exception as e:
        log.error("Sync aborted: %s", e)
        sys.exit(1)

    log.info(
        "Sync complete — companies=%d  contacts=%d  deals=%d  errors=%d",
        result["companies"],
        result["contacts"],
        result["deals"],
        len(result["errors"]),
    )

    if result["errors"]:
        for err in result["errors"]:
            log.error("  %s", err)
        sys.exit(1)
