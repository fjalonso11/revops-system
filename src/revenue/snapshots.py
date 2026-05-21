from datetime import datetime, timezone
from supabase import Client
import logging

log = logging.getLogger(__name__)


def save_metrics_snapshot(
    db: Client,
    volume: dict,
    velocity: dict,
    yield_: dict,
    period_days: int = 30,
) -> int:
    """
    Saves Volume, Velocity, and Yield metric results to metrics_snapshots.
    One row per metric per day. Uses upsert on (snapshot_date, period_days,
    layer, metric_name) so running twice on the same day updates rather than
    duplicates.

    Returns the number of rows saved.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    rows = []

    # Metrics to skip — these are metadata, not measurements
    skip_keys = {"period_days"}

    # Volume layer
    for key, value in volume.items():
        if key in skip_keys or value is None:
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
        if key in skip_keys or value is None:
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
        if key in skip_keys or value is None:
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

    log.info("Saved %d metric rows to metrics_snapshots for %s.", len(rows), today)
    return len(rows)
