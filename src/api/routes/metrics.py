from fastapi import APIRouter, Query
from src.core.database.client import get_supabase
from src.revenue.volume import compute_volume
from src.revenue.velocity import compute_velocity
from src.revenue.yield_ import compute_yield

router = APIRouter(prefix="/metrics", tags=["metrics"])

_PERIOD = Query(default=30, ge=1, le=365, description="Lookback window in days")


@router.get("/volume")
def get_volume(period: int = _PERIOD):
    return compute_volume(get_supabase(), period_days=period)


@router.get("/velocity")
def get_velocity(period: int = _PERIOD):
    return compute_velocity(get_supabase(), period_days=period)


@router.get("/yield")
def get_yield(period: int = _PERIOD):
    return compute_yield(get_supabase(), period_days=period)


@router.get("/all")
def get_all(period: int = _PERIOD):
    db = get_supabase()
    return {
        "period_days": period,
        "volume": compute_volume(db, period_days=period),
        "velocity": compute_velocity(db, period_days=period),
        "yield": compute_yield(db, period_days=period),
    }
