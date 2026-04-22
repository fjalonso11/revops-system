from datetime import datetime, timezone
from supabase import Client
from src.integrations.hubspot import client as hs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_id_map(db: Client, table: str) -> dict[str, str]:
    """Returns {hubspot_id: internal_uuid} for the given table."""
    rows = db.table(table).select("id, hubspot_id").execute()
    return {r["hubspot_id"]: r["id"] for r in rows.data if r.get("hubspot_id")}


def sync_companies(db: Client) -> int:
    companies = hs.fetch_all_companies()
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
    contacts = hs.fetch_all_contacts()
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
    deals = hs.fetch_all_deals()
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

    try:
        result["companies"] = sync_companies(db)
    except Exception as e:
        result["errors"].append(f"companies: {e}")

    company_id_map = _build_id_map(db, "companies")

    try:
        result["contacts"] = sync_contacts(db, company_id_map)
    except Exception as e:
        result["errors"].append(f"contacts: {e}")

    contact_id_map = _build_id_map(db, "contacts")

    try:
        result["deals"] = sync_deals(db, company_id_map, contact_id_map)
    except Exception as e:
        result["errors"].append(f"deals: {e}")

    return result
