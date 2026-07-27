from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from src.core.database.client import get_supabase
from src.integrations.exa.enrichment import enrich_all_companies, get_latest_enrichments
from src.integrations.exa.client import company_brief
from src.core.ai.client import get_anthropic
from src.revenue.churn import resolve_at_risk_companies
import logging

log = logging.getLogger(__name__)

router = APIRouter(prefix="/exa", tags=["exa"])


def _run_enrichment() -> None:
    db = get_supabase()
    result = enrich_all_companies(db)
    log.info(
        "Exa enrichment complete — enriched=%d skipped=%d errors=%d",
        result["enriched"], result["skipped"], len(result["errors"])
    )


@router.post("/enrich")
def enrich_accounts(background_tasks: BackgroundTasks):
    """
    Triggers Exa account enrichment for all companies in Supabase.
    Runs in the background — returns immediately so n8n doesn't time out.
    """
    background_tasks.add_task(_run_enrichment)
    return {"status": "started", "action": "exa_enrich"}


@router.get("/enrichments")
def get_enrichments(limit: int = 3):
    """
    Returns the most recently enriched company briefs.
    """
    db = get_supabase()
    enrichments = get_latest_enrichments(db, limit=limit)
    return {"enrichments": enrichments, "count": len(enrichments)}


class ChurnCheckRequest(BaseModel):
    """All fields optional.

    - No fields: the endpoint resolves every at-risk company from its own
      deal data (churn/contraction deals in the last `period_days`) and checks
      each. This is the mode n8n uses on the daily run — it sends an empty body,
      so there is no domain to hardcode.
    - domain + company_name provided: the endpoint checks that one company on
      demand, skipping resolution. Used for testing or a one-off check.
    """
    domain: str | None = None
    company_name: str | None = None
    deal_type: str | None = None
    deal_amount: float | None = None
    period_days: int = 30


def _check_one_company(
    client,
    company_name: str,
    domain: str,
    deal_type: str | None = None,
    deal_amount: float | None = None,
) -> dict:
    """Run the Exa churn search + Claude synthesis for a single company.

    Valid output: a churn assessment dict for exactly the company passed in —
                  company, domain, exa_severity, narrative, sources.
    Provenance:   exa_signals <- company_brief(domain, churn_mode=True)
                  internal    <- deal_type + deal_amount (real numbers from the
                                 resolved deal; falls back to a generic line
                                 only when a caller supplies neither)
                  narrative   <- Claude synthesis of internal + exa_signals
    """
    log.info("Running churn check for %s (%s)", company_name, domain)

    exa_signals = company_brief(
        domain=domain,
        company_name=company_name,
        days=90,
        churn_mode=True,
    )

    if not exa_signals:
        log.warning("No Exa churn signals found for %s", domain)
        exa_signals = {
            "churn_risk_summary": "No external signals found.",
            "negative_signals": "None detected.",
            "severity": "low",
            "source_urls": "",
        }

    # Internal context from the real deal that flagged this company.
    if deal_type and deal_amount is not None:
        internal_context = (
            f"{company_name} has a {deal_type} deal for "
            f"${deal_amount:,.0f} lost/reduced ARR in the current window. "
            f"This is a real internal churn/contraction signal."
        )
    else:
        internal_context = (
            f"{company_name} is flagged as an at-risk account. "
            f"Yield is deteriorating."
        )

    synthesis_prompt = f"""You are a RevOps analyst. A client is showing internal churn risk signals.
Synthesize the internal revenue data and external web signals into a concise churn risk assessment.

Internal revenue context:
{internal_context}

External signals from Exa web search:
- Churn risk summary: {exa_signals.get('churn_risk_summary', 'N/A')}
- Negative signals: {exa_signals.get('negative_signals', 'None')}
- Severity: {exa_signals.get('severity', 'unknown')}
- Sources: {exa_signals.get('source_urls', '')}

Write a 3-5 sentence churn risk narrative that:
1. States the internal signal (revenue metrics)
2. Confirms or contradicts it with external evidence
3. Gives a recommended action

Be direct and specific. No headers. Plain text only."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": synthesis_prompt}],
    )

    narrative = response.content[0].text.strip()

    return {
        "company": company_name,
        "domain": domain,
        "deal_type": deal_type,
        "deal_amount": deal_amount,
        "exa_severity": exa_signals.get("severity", "unknown"),
        "narrative": narrative,
        "sources": exa_signals.get("source_urls", ""),
    }


@router.post("/churn-check")
def churn_check(req: ChurnCheckRequest = ChurnCheckRequest()):
    """
    Build B — Churn Signal Detection.

    Two modes:
    - On-demand (domain + company_name provided): checks that one company.
    - Auto (no domain): resolves every at-risk company from this platform's
      own deal data and checks each. This is the mode n8n uses — it sends an
      empty body, so there is no domain to hardcode.

    Returns a list of churn assessments. An empty list is valid and means no
    company is at risk in the window — it is NOT an error and must never be
    replaced by a fallback company.
    """
    db = get_supabase()
    client = get_anthropic()

    # Mode 1 — on-demand single company (caller supplied a domain).
    if req.domain and req.company_name:
        assessment = _check_one_company(
            client,
            company_name=req.company_name,
            domain=req.domain,
            deal_type=req.deal_type,
            deal_amount=req.deal_amount,
        )
        return {"at_risk_count": 1, "assessments": [assessment], "unresolved": []}

    # Mode 2 — auto-resolve every at-risk company from deal data.
    resolved = resolve_at_risk_companies(db, period_days=req.period_days)

    assessments = []
    unresolved = []
    for company in resolved:
        if not company.get("resolvable"):
            # Surface the data gap instead of dropping it silently.
            log.warning(
                "At-risk deal could not be resolved to a domain: %s (%s)",
                company.get("deal_name"), company.get("reason"),
            )
            unresolved.append(company)
            continue

        assessments.append(_check_one_company(
            client,
            company_name=company["company_name"],
            domain=company["domain"],
            deal_type=company.get("deal_type"),
            deal_amount=company.get("deal_amount"),
        ))

    log.info(
        "Churn check complete — at_risk=%d unresolved=%d",
        len(assessments), len(unresolved),
    )

    return {
        "at_risk_count": len(assessments),
        "assessments": assessments,
        "unresolved": unresolved,
    }
