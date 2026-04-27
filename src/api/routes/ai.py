from fastapi import APIRouter
from pydantic import BaseModel
from src.core.database.client import get_supabase
from src.core.ai.client import analyze_metrics
from src.revenue.volume import compute_volume
from src.revenue.velocity import compute_velocity
from src.revenue.yield_ import compute_yield

router = APIRouter(prefix="/ai", tags=["ai"])


class AnalyzeRequest(BaseModel):
    question: str | None = None
    period_days: int = 30


@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    db = get_supabase()
    metrics = {
        "volume": compute_volume(db, period_days=req.period_days),
        "velocity": compute_velocity(db, period_days=req.period_days),
        "yield": compute_yield(db, period_days=req.period_days),
    }
    return {
        "metrics": metrics,
        "analysis": analyze_metrics(metrics, question=req.question),
        "model": "claude-sonnet-4-5-20251022",
        "period_days": req.period_days,
    }
