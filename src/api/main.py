from fastapi import FastAPI
from src.api.routes import health, sync, metrics, ai, webhooks

app = FastAPI(
    title="RevOps System",
    description="RevOps infrastructure for LatAm startups",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(sync.router)
app.include_router(metrics.router)
app.include_router(ai.router)
app.include_router(webhooks.router)
