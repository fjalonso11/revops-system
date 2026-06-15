from datetime import datetime, timedelta, timezone
from supabase import Client


def compute_yield(db: Client, period_days: int = 30) -> dict:
    """Revenue quality: NRR, expansion MRR, beginning/ending MRR.

    NRR = (beginning_mrr + expansion_mrr - contraction_mrr - churned_mrr)
          / beginning_mrr × 100

    Churn and contraction are tracked via HubSpot deals of type 'churn' and
    'contraction'. These deal types must be configured in HubSpot and logged
    by the client team when a customer cancels or downgrades.

    nrr_is_complete is True when churn or contraction data is present in the
    period, signaling that the NRR reflects real retention dynamics. When both
    are zero, NRR is a ceiling — expansion only, no downside captured.
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

    # Churn: deals of type 'churn' closed in period (lost MRR)
    churn_deals = db.table("deals").select("amount").eq(
        "is_won", True
    ).eq("type", "churn").gte("closed_at", since).execute()
    churned_mrr = sum((d["amount"] or 0) / 12 for d in churn_deals.data)

    # Contraction: deals of type 'contraction' closed in period (reduced MRR)
    contraction_deals = db.table("deals").select("amount").eq(
        "is_won", True
    ).eq("type", "contraction").gte("closed_at", since).execute()
    contraction_mrr = sum((d["amount"] or 0) / 12 for d in contraction_deals.data)

    # Total active MRR across all companies (HubSpot mrr field / month)
    all_companies = db.table("companies").select("mrr").execute()
    total_active_mrr = sum(c["mrr"] or 0 for c in all_companies.data)

    # Complete NRR formula
    ending_mrr = beginning_mrr + expansion_mrr - contraction_mrr - churned_mrr
    nrr = round(ending_mrr / beginning_mrr * 100, 1) if beginning_mrr > 0 else None

    # NRR is only complete when churn or contraction data is present
    nrr_is_complete = churned_mrr > 0 or contraction_mrr > 0

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
        "churned_mrr": round(churned_mrr, 2),
        "contraction_mrr": round(contraction_mrr, 2),
        "ending_mrr": round(ending_mrr, 2),
        "total_active_mrr": round(total_active_mrr, 2),
        "nrr_percent": nrr,
        "nrr_is_complete": nrr_is_complete,
        "total_customers": total_customers.count or 0,
        "new_customers_in_period": new_customers.count or 0,
    }
