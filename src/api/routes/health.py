from fastapi import APIRouter
from src.core.database.client import get_supabase

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    try:
        get_supabase().table("sync_logs").select("id").limit(1).execute()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "ok", "database": db_status}
