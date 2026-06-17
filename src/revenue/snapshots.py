from datetime import datetime, timezone
from supabase import Client
import logging

log = logging.getLogger(__name__)

# The five comparison windows the platform tracks simultaneously.
# Each daily run saves a complete set of metric rows for every window.
SNAPSHOT_PERIODS = [7, 14, 30, 60, 90]


def save_metrics_snapshot(
    db: Client,
    volume: dict,
    velocity: dict,
    yield_: dict,
    period_days: int = 30,
) -> int:
    """
    Saves Volume, Velocity, and Yield metric results to metrics_snapshots
    for a single period window.

    One row per metric per day per period. Uses upsert on
    (snapshot_date, period_days, layer, metric_name) so running twice
    on the same day updates rather than duplicates.

    Returns the number of rows saved.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    rows = []

    # Metrics to skip — these are metadata, not measurements
    skip_keys = {"period_days"}

    # Non-numeric types that cannot be stored as float
    skip_types = (bool, str)

    # Volume layer
    for key, value in volume.items():
        if key in skip_keys or value is None or isinstance(value, skip_types):
            continue
        rows.append({
            "snapshot_date": today,
            "period_days": period_days,
            "layer": "volume",
            "metric_name": key,
            "value": float(value),
        })

    # Velocity layer
    for key, value in velocity.items():
        if key in skip_keys or value is None or isinstance(value, skip_types):
            continue
        rows.append({
            "snapshot_date": today,
            "period_days": period_days,
            "layer": "velocity",
            "metric_name": key,
            "value": float(value),
        })

    # Yield layer
    for key, value in yield_.items():
        if key in skip_keys or value is None or isinstance(value, skip_types):
            continue
        rows.append({
            "snapshot_date": today,
            "period_days": period_days,
            "layer": "yield",
            "metric_name": key,
            "value": float(value),
        })

    if not rows:
        log.warning("No metric rows to save — all values were None or skipped.")
        return 0

    # Upsert — safe to run multiple times on the same day
    db.table("metrics_snapshots").upsert(
        rows,
        on_conflict="snapshot_date,period_days,layer,metric_name"
    ).execute()

    log.info(
        "Saved %d metric rows to metrics_snapshots for %s (period=%d days).",
        len(rows), today, period_days,
    )
    return len(rows)


def save_all_period_snapshots(
    db: Client,
    compute_volume,
    compute_velocity,
    compute_yield,
) -> int:
    """
    Saves snapshots for all five period windows in a single call.

    Calls the three compute functions once per period window and saves
    the results. Total rows per daily run: ~15 metrics x 5 periods = 75 rows.

    Returns the total number of rows saved across all periods.
    """
    total_saved = 0

    for period in SNAPSHOT_PERIODS:
        try:
            volume = compute_volume(db, period_days=period)
            velocity = compute_velocity(db, period_days=period)
            yield_ = compute_yield(db, period_days=period)
            saved = save_metrics_snapshot(db, volume, velocity, yield_, period_days=period)
            total_saved += saved
        except Exception as e:
            log.warning("Snapshot save failed for period=%d (non-fatal): %s", period, e)

    log.info("Total snapshot rows saved across all periods: %d", total_saved)
    return total_saved


def get_prior_snapshot(
    db: Client,
    layer: str,
    metric_name: str,
    period_days: int = 30,
) -> float | None:
    """
    Returns the most recent prior snapshot value for a given metric,
    layer, and period window — from any date before today.

    Returns None if no prior snapshot exists (e.g. first day of tracking).
    This is honest: the caller should treat None as 'no comparison available'
    rather than 'zero change'.
    """
    today = datetime.now(timezone.utc).date().isoformat()

    result = db.table("metrics_snapshots").select("value, snapshot_date").eq(
        "layer", layer
    ).eq(
        "metric_name", metric_name
    ).eq(
        "period_days", period_days
    ).lt(
        "snapshot_date", today
    ).order(
        "snapshot_date", desc=True
    ).limit(1).execute()

    if result.data:
        return float(result.data[0]["value"])
    return None
