from fastapi import APIRouter
from pydantic import BaseModel
from src.core.database.client import get_supabase
from src.core.ai.client import analyze_metrics
from src.revenue.volume import compute_volume
from src.revenue.velocity import compute_velocity
from src.revenue.yield_ import compute_yield
from src.revenue.snapshots import save_all_period_snapshots, get_prior_snapshot
import logging

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

# Layers and their metric names for prior snapshot retrieval
_LAYERS = {
    "volume": ["new_customers", "new_won_deals", "new_mrr", "new_tpv",
               "open_pipeline_deals", "open_pipeline_value"],
    "velocity": ["avg_lead_to_mql_days", "avg_mql_to_sql_days",
                 "avg_sql_to_customer_days", "avg_lead_to_cash_days",
                 "avg_deal_cycle_days", "deals_won", "contacts_sampled"],
    "yield": ["beginning_mrr", "expansion_mrr", "churned_mrr", "contraction_mrr",
              "ending_mrr", "total_active_mrr", "nrr_percent",
              "total_customers", "new_customers_in_period"],
}


class AnalyzeRequest(BaseModel):
    question: str | None = None
    period_days: int = 30


def _build_prior_metrics(db, period_days: int) -> dict | None:
    """
    Builds a prior_metrics dictionary by fetching the most recent prior
    snapshot for each metric across all three layers.

    Returns None if no prior snapshots exist yet for any metric.
    """
    prior = {"volume": {}, "velocity": {}, "yield": {}}
    any_found = False

    for layer, metric_names in _LAYERS.items():
        for metric_name in metric_names:
            value = get_prior_snapshot(
                db, layer=layer, metric_name=metric_name, period_days=period_days
            )
            if value is not None:
                prior[layer][metric_name] = value
                any_found = True

    return prior if any_found else None


@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    db = get_supabase()

    # Compute current metrics for the requested period
    volume = compute_volume(db, period_days=req.period_days)
    velocity = compute_velocity(db, period_days=req.period_days)
    yield_ = compute_yield(db, period_days=req.period_days)

    # Build prior metrics for trend context — matches the requested period
    prior_metrics = _build_prior_metrics(db, period_days=req.period_days)

    # Save snapshots for all five period windows
    # Non-fatal: if this fails, analysis still completes and Slack still posts
    try:
        total_saved = save_all_period_snapshots(
            db, compute_volume, compute_velocity, compute_yield
        )
        log.info("Snapshots saved across all periods: %d rows.", total_saved)
    except Exception as e:
        log.warning("Snapshot save failed (non-fatal): %s", e)

    metrics = {"volume": volume, "velocity": velocity, "yield": yield_}

    if prior_metrics:
        log.info("Prior metrics found for period=%d days — trend context enabled.", req.period_days)
    else:
        log.info("No prior metrics found for period=%d days — snapshot only.", req.period_days)

    return {
        "metrics": metrics,
        "prior_metrics": prior_metrics,
        "analysis": analyze_metrics(metrics, question=req.question, prior_metrics=prior_metrics),
        "model": "claude-haiku-4-5-20251001",
        "period_days": req.period_days,
    }
