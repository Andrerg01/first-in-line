"""Application bootstrap — wires FastAPI app, routers, and startup only."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.exceptions import IngestError
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.events import router as events_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router

app = FastAPI(title="First In Line Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(events_router)
app.include_router(ingest_router)
app.include_router(admin_router)
app.include_router(auth_router)


@app.exception_handler(IngestError)
async def ingest_error_handler(request: Request, exc: IngestError) -> JSONResponse:
    """Convert domain ingest exceptions to structured HTTP error responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc)},
    )