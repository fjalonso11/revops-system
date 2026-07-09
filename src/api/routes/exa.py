from fastapi import APIRouter, BackgroundTasks
from src.core.database.client import get_supabase
from src.integrations.exa.enrichment import enrich_all_companies, get_latest_enrichments
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
    Used to preview account intelligence without triggering a new enrichment.
    """
    db = get_supabase()
    enrichments = get_latest_enrichments(db, limit=limit)
    return {"enrichments": enrichments, "count": len(enrichments)}
