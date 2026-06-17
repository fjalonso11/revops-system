from fastapi import APIRouter, Query
from src.core.database.client import get_supabase
from src.revenue.volume import compute_volume
from src.revenue.velocity import compute_velocity
from src.revenue.yield_ import compute_yield
from src.revenue.snapshots import get_prior_snapshot

router = APIRouter(prefix="/metrics", tags=["metrics"])

_PERIOD = Query(default=30, ge=1, le=365, description="Lookback window in days")

# Metric types that cannot have meaningful period-over-period comparison
_SKIP_COMPARISON = {"period_days", "nrr_is_complete"}


def _add_comparisons(db, metrics: dict, layer: str, period: int) -> dict:
    """
    Enriches a metrics dictionary with period-over-period comparison fields.

    For each numeric metric, adds:
      - {metric}_prior: the most recent prior snapshot value (None if no history)
      - {metric}_change_pct: percentage change from prior to current (None if no prior)

    Non-numeric fields (bool, str) and skip-listed keys are left untouched.
    """
    enriched = dict(metrics)

    for key, value in metrics.items():
        if key in _SKIP_COMPARISON:
            continue
        if not isinstance(value, (int, float)):
            continue

        prior = get_prior_snapshot(db, layer=layer, metric_name=key, period_days=period)
        enriched[f"{key}_prior"] = prior

        if prior is not None and prior != 0:
            change_pct = round((value - prior) / abs(prior) * 100, 1)
            enriched[f"{key}_change_pct"] = change_pct
        elif prior == 0 and value != 0:
            # Prior was zero — growth from zero, percentage is undefined
            enriched[f"{key}_change_pct"] = None
        elif prior is not None:
            enriched[f"{key}_change_pct"] = 0.0
        else:
            # No prior snapshot exists yet
            enriched[f"{key}_change_pct"] = None

    return enriched


@router.get("/volume")
def get_volume(period: int = _PERIOD):
    db = get_supabase()
    metrics = compute_volume(db, period_days=period)
    return _add_comparisons(db, metrics, layer="volume", period=period)


@router.get("/velocity")
def get_velocity(period: int = _PERIOD):
    db = get_supabase()
    metrics = compute_velocity(db, period_days=period)
    return _add_comparisons(db, metrics, layer="velocity", period=period)


@router.get("/yield")
def get_yield(period: int = _PERIOD):
    db = get_supabase()
    metrics = compute_yield(db, period_days=period)
    return _add_comparisons(db, metrics, layer="yield", period=period)


@router.get("/all")
def get_all(period: int = _PERIOD):
    db = get_supabase()
    volume = compute_volume(db, period_days=period)
    velocity = compute_velocity(db, period_days=period)
    yield_ = compute_yield(db, period_days=period)
    return {
        "period_days": period,
        "volume": _add_comparisons(db, volume, layer="volume", period=period),
        "velocity": _add_comparisons(db, velocity, layer="velocity", period=period),
        "yield": _add_comparisons(db, yield_, layer="yield", period=period),
    }
