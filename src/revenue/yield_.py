from datetime import datetime, timedelta, timezone
from supabase import Client


def compute_yield(db: Client, period_days: int = 30) -> dict:
    """Revenue quality: NRR, expansion MRR, beginning/ending MRR.

    NRR = (beginning_mrr + expansion_mrr) / beginning_mrr × 100
    Contraction and churn require CRM stage-down events; extend sync when available.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    # MRR base: new-business deals closed before period start
    beginning_deals = db.table("deals").select("amount").eq(
        "is_won", True
    ).eq("type", "newbusiness").lt("closed_at", since).execute()
    beginning_mrr = sum((d["amount"] or 0) / 12 for d in beginning_deals.data)

    # Expansion: existing-business deals won in period
    expansion_deals = db.table("deals").select("amount").eq(
        "is_won", True
    ).eq("type", "existingbusiness").gte("closed_at", since).execute()
    expansion_mrr = sum((d["amount"] or 0) / 12 for d in expansion_deals.data)

    # Total active MRR across all companies (HubSpot annualrevenue / 12)
    all_companies = db.table("companies").select("mrr").execute()
    total_active_mrr = sum(c["mrr"] or 0 for c in all_companies.data)

    ending_mrr = beginning_mrr + expansion_mrr
    nrr = round(ending_mrr / beginning_mrr * 100, 1) if beginning_mrr > 0 else None

    total_customers = db.table("contacts").select("id", count="exact").eq(
        "lifecycle_stage", "customer"
    ).execute()

    new_customers = db.table("contacts").select("id", count="exact").gte(
        "became_customer_at", since
    ).execute()

    return {
        "period_days": period_days,
        "beginning_mrr": round(beginning_mrr, 2),
        "expansion_mrr": round(expansion_mrr, 2),
        "ending_mrr": round(ending_mrr, 2),
        "total_active_mrr": round(total_active_mrr, 2),
        "nrr_percent": nrr,
        "total_customers": total_customers.count or 0,
        "new_customers_in_period": new_customers.count or 0,
    }
