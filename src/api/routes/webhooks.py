import hmac
import hashlib
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from src.core.config import settings
from src.core.database.client import get_supabase
from src.integrations.hubspot.sync import run_full_sync
from src.integrations.slack.client import send_sync_notification

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_ACTIONS = {"sync_hubspot", "sync_hubspot_incremental"}


def _verify_signature(body: bytes, signature: str) -> bool:
    if not settings.n8n_webhook_secret:
        return True
    expected = hmac.new(
        settings.n8n_webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _do_hubspot_sync() -> None:
    db = get_supabase()
    result = run_full_sync(db)
    send_sync_notification("HubSpot (n8n)", result)


@router.post("/n8n")
async def n8n_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("x-n8n-signature", "")

    if not _verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    action = payload.get("action")

    if action in ("sync_hubspot", "sync_hubspot_incremental"):
        background_tasks.add_task(_do_hubspot_sync)
        return {"status": "accepted", "action": action}

    return {"status": "ignored", "action": action, "reason": "unknown action"}
