from fastapi import APIRouter
from pydantic import BaseModel
from src.core.database.client import get_supabase
from src.core.ai.client import analyze_metrics
from src.revenue.volume import compute_volume
from src.revenue.velocity import compute_velocity
from src.revenue.yield_ import compute_yield
from src.revenue.snapshots import save_all_period_snapshots
import logging

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


class AnalyzeRequest(BaseModel):
    question: str | None = None
    period_days: int = 30


@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    db = get_supabase()

    # Compute 30-day metrics for Claude analysis
    volume = compute_volume(db, period_days=30)
    velocity = compute_velocity(db, period_days=30)
    yield_ = compute_yield(db, period_days=30)

    # Save snapshots for all five period windows in the background
    # Non-fatal: if this fails, analysis still completes and Slack still posts
    try:
        total_saved = save_all_period_snapshots(
            db, compute_volume, compute_velocity, compute_yield
        )
        log.info("Snapshots saved across all periods: %d rows.", total_saved)
    except Exception as e:
        log.warning("Snapshot save failed (non-fatal): %s", e)

    metrics = {"volume": volume, "velocity": velocity, "yield": yield_}

    return {
        "metrics": metrics,
        "analysis": analyze_metrics(metrics, question=req.question),
        "model": "claude-haiku-4-5-20251001",
        "period_days": req.period_days,
    }
