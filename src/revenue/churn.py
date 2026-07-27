from datetime import datetime, timedelta, timezone
from supabase import Client


def resolve_at_risk_companies(db: Client, period_days: int = 30) -> list[dict]:
    """Resolve every at-risk company from this platform's own deal data.

    Valid output: a list of at-risk companies, one per churn/contraction deal
                  closed in the last `period_days` days, each carrying the
                  fields a churn check needs. Empty list is valid and means
                  nothing is at risk in the window — not an error.
    Provenance:   at_risk_deal   <- deals where type IN ('churn','contraction')
                                     AND is_won = true
                                     AND closed_at >= now - period_days
                  company/domain <- companies joined on deals.company_id
                  amount/type    <- that deal's own columns

    A deal with no company_id, or a company row with no domain, is skipped
    with the reason recorded in the returned dict's `skipped` companion — a
    churn check cannot run without a domain, and silently dropping it would
    hide a data gap. The 30-day default matches the metric window that
    triggers the churn signal (yield_.py period_days=30): the feature is early
    warning, so the resolution window tracks the alarm window.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    deals = (
        db.table("deals")
        .select("name, amount, type, company_id, closed_at")
        .eq("is_won", True)
        .in_("type", ["churn", "contraction"])
        .gte("closed_at", since)
        .execute()
    )

    at_risk: list[dict] = []
    for deal in deals.data:
        company_id = deal.get("company_id")
        if not company_id:
            # No company link: cannot resolve a domain to check. Record and skip.
            at_risk.append({
                "resolvable": False,
                "reason": "deal has no company_id",
                "deal_name": deal.get("name"),
                "deal_type": deal.get("type"),
            })
            continue

        company = (
            db.table("companies")
            .select("name, domain")
            .eq("id", company_id)
            .limit(1)
            .execute()
        )

        row = company.data[0] if company.data else None
        domain = row.get("domain") if row else None

        if not domain:
            at_risk.append({
                "resolvable": False,
                "reason": "company has no domain",
                "deal_name": deal.get("name"),
                "deal_type": deal.get("type"),
                "company_name": row.get("name") if row else None,
            })
            continue

        at_risk.append({
            "resolvable": True,
            "company_name": row.get("name"),
            "domain": domain,
            "deal_type": deal.get("type"),
            "deal_amount": deal.get("amount"),
            "deal_name": deal.get("name"),
        })

    return at_risk
