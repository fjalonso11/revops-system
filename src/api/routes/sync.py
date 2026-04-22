from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks
from src.core.database.client import get_supabase
from src.integrations.hubspot.sync import run_full_sync
from src.integrations.slack.client import send_sync_notification

router = APIRouter(prefix="/sync", tags=["sync"])


def _start_log(db, source: str, sync_type: str) -> str:
    row = db.table("sync_logs").insert({
        "source": source,
        "sync_type": sync_type,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    return row.data[0]["id"]


def _finish_log(db, log_id: str, result: dict) -> None:
    total = sum(v for k, v in result.items() if k != "errors" and isinstance(v, int))
    db.table("sync_logs").update({
        "status": "failed" if result.get("errors") else "success",
        "records_synced": total,
        "errors": result.get("errors") or None,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", log_id).execute()


def _hubspot_sync_task(sync_type: str) -> None:
    db = get_supabase()
    log_id = _start_log(db, "hubspot", sync_type)
    try:
        result = run_full_sync(db)
        _finish_log(db, log_id, result)
        send_sync_notification("HubSpot", result)
    except Exception as e:
        db.table("sync_logs").update({
            "status": "failed",
            "errors": [str(e)],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", log_id).execute()
        raise


@router.post("/hubspot")
def sync_hubspot(background_tasks: BackgroundTasks):
    background_tasks.add_task(_hubspot_sync_task, "full")
    return {"status": "started", "type": "full", "source": "hubspot"}


@router.post("/hubspot/incremental")
def sync_hubspot_incremental(background_tasks: BackgroundTasks):
    background_tasks.add_task(_hubspot_sync_task, "incremental")
    return {"status": "started", "type": "incremental", "source": "hubspot"}


@router.get("/hubspot/status")
def sync_status():
    db = get_supabase()
    logs = db.table("sync_logs").select("*").eq(
        "source", "hubspot"
    ).order("started_at", desc=True).limit(10).execute()
    return {"recent_syncs": logs.data}
