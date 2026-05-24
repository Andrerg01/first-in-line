"""Application bootstrap — wires FastAPI app, routers, and startup only."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import IngestError
from app.routers.events import router as events_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router

app = FastAPI(title="Grand Opening Radar Backend", version="0.1.0")

app.include_router(health_router)
app.include_router(events_router)
app.include_router(ingest_router)


@app.exception_handler(IngestError)
async def ingest_error_handler(request: Request, exc: IngestError) -> JSONResponse:
    """Convert domain ingest exceptions to structured HTTP error responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc)},
    )
