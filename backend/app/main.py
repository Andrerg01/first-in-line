"""Application bootstrap — wires FastAPI app, routers, and startup only."""
from fastapi import FastAPI

from app.routers.events import router as events_router
from app.routers.health import router as health_router

app = FastAPI(title="Grand Opening Radar Backend", version="0.1.0")

app.include_router(health_router)
app.include_router(events_router)
