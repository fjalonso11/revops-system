import sys
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


# ---------------------------------------------------------------------------
# Validation layer — runs between HubSpot fetch and Supabase upsert
# Returns (is_valid: bool, reason: str | None)
# ---------------------------------------------------------------------------

def _validate_company(company) -> tuple[bool, str | None]:
    if not company.hubspot_id:
        return False, "missing hubspot_id"
    if not company.name or not str(company.name).strip():
        return False, "missing or empty name"
    if company.mrr is not None and company.mrr < 0:
        return False, f"negative mrr: {company.mrr}"
    if company.arr is not None and company.arr < 0:
        return False, f"negative arr: {company.arr}"
    return True, None


def _validate_contact(contact) -> tuple[bool, str | None]:
    if not contact.hubspot_id:
        return False, "missing hubspot_id"
    if contact.email and "@" not in str(contact.email):
        return False, f"invalid email format: {contact.email}"
    # Lifecycle timestamp ordering: lead → mql → sql → customer
    timestamps = [
        ("became_lead_at", contact.became_lead_at),
        ("became_mql_at", contact.became_mql_at),
        ("became_sql_at", contact.became_sql_at),
        ("became_customer_at", contact.became_customer_at),
    ]
    last_name, last_ts = None, None
    for name, ts in timestamps:
        if ts is not None:
            if last_ts is not None and ts < last_ts:
                return False, f"{name} ({ts}) is before {last_name} ({last_ts})"
            last_name, last_ts = name, ts
    return True, None


def _validate_deal(deal) -> tuple[bool, str | None]:
    if not deal.hubspot_id:
        return False, "missing hubspot_id"
    if deal.amount is not None and deal.amount < 0:
        return False, f"negative amount: {deal.amount}"
    if deal.is_won and not deal.is_closed:
        return False, "is_won=True but is_closed=False"
    valid_types = {"newbusiness", "existingbusiness", "churn", "contraction", None}
    if deal.type not in valid_types:
        return False, f"invalid type: {deal.type}"
    return True, None


# ---------------------------------------------------------------------------
# Sync functions
# ---------------------------------------------------------------------------

def sync_companies(db: Client) -> tuple[int, int, list[str]]:
    """Returns (synced, skipped, validation_errors)."""
    log.info("Fetching companies from HubSpot...")
    companies = hs.fetch_all_companies()
    log.info("Validating and upserting %d companies...", len(companies))

    synced, skipped = 0, 0
    validation_errors = []

    for company in companies:
        valid, reason = _validate_company(company)
        if not valid:
            msg = f"company {company.hubspot_id}: {reason}"
            log.warning("SKIPPED — %s", msg)
            validation_errors.append(msg)
            skipped += 1
            continue

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
        synced += 1

    return synced, skipped, validation_errors


def sync_contacts(
    db: Client, company_id_map: dict[str, str]
) -> tuple[int, int, list[str]]:
    """Returns (synced, skipped, validation_errors)."""
    log.info("Fetching contacts from HubSpot...")
    contacts = hs.fetch_all_contacts()
    log.info("Validating and upserting %d contacts...", len(contacts))

    synced, skipped = 0, 0
    validation_errors = []

    for contact in contacts:
        valid, reason = _validate_contact(contact)
        if not valid:
            msg = f"contact {contact.hubspot_id}: {reason}"
            log.warning("SKIPPED — %s", msg)
            validation_errors.append(msg)
            skipped += 1
            continue

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
        synced += 1

    return synced, skipped, validation_errors


def sync_deals(
    db: Client,
    company_id_map: dict[str, str],
    contact_id_map: dict[str, str],
) -> tuple[int, int, list[str]]:
    """Returns (synced, skipped, validation_errors)."""
    log.info("Fetching deals from HubSpot...")
    deals = hs.fetch_all_deals()
    log.info("Validating and upserting %d deals...", len(deals))

    synced, skipped = 0, 0
    validation_errors = []

    for deal in deals:
        valid, reason = _validate_deal(deal)
        if not valid:
            msg = f"deal {deal.hubspot_id}: {reason}"
            log.warning("SKIPPED — %s", msg)
            validation_errors.append(msg)
            skipped += 1
            continue

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
        synced += 1

    return synced, skipped, validation_errors


def run_full_sync(db: Client) -> dict:
    """Syncs companies → contacts → deals. Order matters for FK resolution."""
    result: dict = {
        "companies": 0,
        "contacts": 0,
        "deals": 0,
        "skipped": 0,
        "errors": [],
        "validation_errors": [],
    }
    log_id = _start_sync_log(db)

    try:
        synced, skipped, val_errors = sync_companies(db)
        result["companies"] = synced
        result["skipped"] += skipped
        result["validation_errors"].extend(val_errors)
    except Exception as e:
        log.error("companies sync failed: %s", e)
        result["errors"].append(f"companies: {e}")

    company_id_map = _build_id_map(db, "companies")

    try:
        synced, skipped, val_errors = sync_contacts(db, company_id_map)
        result["contacts"] = synced
        result["skipped"] += skipped
        result["validation_errors"].extend(val_errors)
    except Exception as e:
        log.error("contacts sync failed: %s", e)
        result["errors"].append(f"contacts: {e}")

    contact_id_map = _build_id_map(db, "contacts")

    try:
        synced, skipped, val_errors = sync_deals(db, company_id_map, contact_id_map)
        result["deals"] = synced
        result["skipped"] += skipped
        result["validation_errors"].extend(val_errors)
    except Exception as e:
        log.error("deals sync failed: %s", e)
        result["errors"].append(f"deals: {e}")

    total = result["companies"] + result["contacts"] + result["deals"]
    status = "failed" if result["errors"] else "success"
    _finish_sync_log(db, log_id, status, total, result["errors"])

    if result["validation_errors"]:
        log.warning(
            "%d records skipped due to validation errors", result["skipped"]
        )

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
        "Sync complete — companies=%d  contacts=%d  deals=%d  skipped=%d  errors=%d",
        result["companies"],
        result["contacts"],
        result["deals"],
        result["skipped"],
        len(result["errors"]),
    )

    if result["validation_errors"]:
        for err in result["validation_errors"]:
            log.warning("  VALIDATION: %s", err)

    if result["errors"]:
        for err in result["errors"]:
            log.error("  ERROR: %s", err)
        sys.exit(1)
