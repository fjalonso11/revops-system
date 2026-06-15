from datetime import datetime, timedelta, timezone
from supabase import Client


def _days_between(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end.replace("Z", "+00:00"))
        diff = (e - s).total_seconds() / 86400
        return diff if diff >= 0 else None
    except (ValueError, AttributeError):
        return None


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def compute_velocity(db: Client, period_days: int = 30) -> dict:
    """Lead-to-cash funnel timing: lead→MQL→SQL→customer, deal cycle time.

    Sample sizes are reported alongside each average so Claude can distinguish
    statistically meaningful metrics from averages based on 1-2 contacts.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    contacts = db.table("contacts").select(
        "became_lead_at, became_mql_at, became_sql_at, became_customer_at"
    ).gte("updated_at", since).execute()

    lead_to_mql, mql_to_sql, sql_to_customer = [], [], []
    for c in contacts.data:
        d = _days_between(c.get("became_lead_at"), c.get("became_mql_at"))
        if d is not None:
            lead_to_mql.append(d)
        d = _days_between(c.get("became_mql_at"), c.get("became_sql_at"))
        if d is not None:
            mql_to_sql.append(d)
        d = _days_between(c.get("became_sql_at"), c.get("became_customer_at"))
        if d is not None:
            sql_to_customer.append(d)

    won_deals = db.table("deals").select(
        "created_at, closed_at"
    ).eq("is_won", True).gte("closed_at", since).execute()

    deal_cycles = []
    for d in won_deals.data:
        days = _days_between(d.get("created_at"), d.get("closed_at"))
        if days is not None:
            deal_cycles.append(days)

    avg_l2m = _avg(lead_to_mql)
    avg_m2s = _avg(mql_to_sql)
    avg_s2c = _avg(sql_to_customer)

    lead_to_cash = (
        round(avg_l2m + avg_m2s + avg_s2c, 1)
        if all(v is not None for v in [avg_l2m, avg_m2s, avg_s2c])
        else None
    )

    total_contacts = len(contacts.data)

    return {
        "period_days": period_days,
        "contacts_sampled": total_contacts,
        "avg_lead_to_mql_days": avg_l2m,
        "lead_to_mql_sample": f"{len(lead_to_mql)} of {total_contacts}",
        "avg_mql_to_sql_days": avg_m2s,
        "mql_to_sql_sample": f"{len(mql_to_sql)} of {total_contacts}",
        "avg_sql_to_customer_days": avg_s2c,
        "sql_to_customer_sample": f"{len(sql_to_customer)} of {total_contacts}",
        "avg_lead_to_cash_days": lead_to_cash,
        "avg_deal_cycle_days": _avg(deal_cycles),
        "deals_won": len(deal_cycles),
    }
