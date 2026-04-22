from datetime import datetime, timedelta, timezone
from supabase import Client


def compute_volume(db: Client, period_days: int = 30) -> dict:
    """New business growth: customers, MRR, TPV, open pipeline."""
    since = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    new_customers = db.table("contacts").select("id", count="exact").gte(
        "became_customer_at", since
    ).execute()

    new_won_deals = db.table("deals").select("id, amount").eq(
        "is_won", True
    ).gte("closed_at", since).execute()

    new_biz_deals = db.table("deals").select("amount").eq(
        "is_won", True
    ).eq("type", "newbusiness").gte("closed_at", since).execute()

    open_pipeline = db.table("deals").select("id, amount").eq(
        "is_closed", False
    ).execute()

    new_mrr = sum((d["amount"] or 0) / 12 for d in new_biz_deals.data)
    new_tpv = sum(d["amount"] or 0 for d in new_won_deals.data)
    pipeline_value = sum(d["amount"] or 0 for d in open_pipeline.data)

    return {
        "period_days": period_days,
        "new_customers": new_customers.count or 0,
        "new_won_deals": len(new_won_deals.data),
        "new_mrr": round(new_mrr, 2),
        "new_tpv": round(new_tpv, 2),
        "open_pipeline_deals": len(open_pipeline.data),
        "open_pipeline_value": round(pipeline_value, 2),
    }
