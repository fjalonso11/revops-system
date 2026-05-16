from fastapi import FastAPI, Security, HTTPException
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from src.api.routes import health, sync, metrics, ai, webhooks
from src.core.config import settings

# API key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not settings.api_key:
        return  # No key configured — open access (local dev only)
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )


app = FastAPI(
    title="RevOps System",
    description="RevOps infrastructure for LatAm startups",
    version="0.1.0",
)

app.include_router(health.router)  # /health — no auth (monitoring needs this open)
app.include_router(sync.router, dependencies=[Security(verify_api_key)])
app.include_router(metrics.router, dependencies=[Security(verify_api_key)])
app.include_router(ai.router, dependencies=[Security(verify_api_key)])
app.include_router(webhooks.router)  # /webhooks — has its own signature verification