from fastapi import APIRouter
from pydantic import BaseModel
from src.core.database.client import get_supabase
from src.core.ai.client import analyze_metrics
from src.revenue.volume import compute_volume
from src.revenue.velocity import compute_velocity
from src.revenue.yield_ import compute_yield
from src.revenue.snapshots import save_metrics_snapshot
import logging

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


class AnalyzeRequest(BaseModel):
    question: str | None = None
    period_days: int = 30


@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    db = get_supabase()

    volume = compute_volume(db, period_days=req.period_days)
    velocity = compute_velocity(db, period_days=req.period_days)
    yield_ = compute_yield(db, period_days=req.period_days)

    # Save snapshot before analysis — data is already computed
    try:
        rows_saved = save_metrics_snapshot(
            db, volume, velocity, yield_, period_days=req.period_days
        )
        log.info("Snapshot saved: %d rows.", rows_saved)
    except Exception as e:
        log.warning("Snapshot save failed (non-fatal): %s", e)

    metrics = {"volume": volume, "velocity": velocity, "yield": yield_}

    return {
        "metrics": metrics,
        "analysis": analyze_metrics(metrics, question=req.question),
        "model": "claude-haiku-4-5-20251001",
        "period_days": req.period_days,
    }
