from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from src.core.database.client import get_supabase
from src.integrations.exa.enrichment import enrich_all_companies, get_latest_enrichments
from src.integrations.exa.client import company_brief
from src.core.ai.client import get_anthropic
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
    domain: str
    company_name: str
    yield_status: str = "critical"
    internal_context: str = ""


@router.post("/churn-check")
def churn_check(req: ChurnCheckRequest):
    """
    Build B — Churn Signal Detection.

    Takes a company domain and internal revenue context, fetches external
    churn signals from Exa, then synthesizes both into a unified churn
    risk narrative via Claude.

    Called by n8n when risk_flags.churn_risk == true.
    """
    # Step 1 — Fetch external churn signals from Exa
    log.info("Running churn check for %s (%s)", req.company_name, req.domain)

    exa_signals = company_brief(
        domain=req.domain,
        company_name=req.company_name,
        days=90,
        churn_mode=True,
    )

    if not exa_signals:
        log.warning("No Exa churn signals found for %s", req.domain)
        exa_signals = {
            "churn_risk_summary": "No external signals found.",
            "negative_signals": "None detected.",
            "severity": "low",
            "source_urls": "",
        }

    # Step 2 — Synthesize internal + external signals via Claude
    client = get_anthropic()

    synthesis_prompt = f"""You are a RevOps analyst. A client is showing internal churn risk signals.
Synthesize the internal revenue data and external web signals into a concise churn risk assessment.

Internal revenue context:
{req.internal_context if req.internal_context else f"Yield status: {req.yield_status}. NRR is negative or deteriorating."}

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
        "company": req.company_name,
        "domain": req.domain,
        "yield_status": req.yield_status,
        "exa_severity": exa_signals.get("severity", "unknown"),
        "narrative": narrative,
        "sources": exa_signals.get("source_urls", ""),
    }
