# Grand Opening Radar

Grand Opening Radar discovers nearby business grand openings and preserves source evidence, extracted claims, and canonical events — starting with Greenville, SC.

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Monorepo skeleton, Docker Compose, service stubs | ✅ Complete |
| 1 | Database schema, Alembic migrations, CRUD backend, seed data | ✅ Complete |
| 2 | Basic frontend — event list, event detail, admin verify/reject | ✅ Complete |
| 3 | Manual URL ingestion — AdminIngest page, OpenAI extraction pipeline | ✅ Complete |
| 4+ | Scheduled search, LangGraph pipeline, map/calendar, CI/CD, notifications | Planned |

Current version: see `VERSION` file.

## Local Setup

### Prerequisites

- Docker Desktop
- Python 3.12+ (for running tests and migrations locally)
- Node.js 20+ (for frontend dev server)

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD and OPENAI_API_KEY at minimum.
# DATABASE_URL must use the postgresql+psycopg:// scheme (psycopg v3).
```

> **Important:** The backend Docker image ships `psycopg` v3, not `psycopg2`.
> Always use `postgresql+psycopg://` in `DATABASE_URL` — never `postgresql://`.

### 2. Start the stack

```bash
docker compose up --build
```

Services:
| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| MCP server | http://localhost:9000 |
| Postgres | localhost:5432 |

> **OPENAI_API_KEY** must be set in `.env` for the manual URL ingestion pipeline
> (`/admin/ingest`) to call OpenAI for event extraction.

### 3. Apply migrations and seed data

Run once after the stack is first started (or after a schema change):

```bash
# From the repo root
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/grand_openings \
  python -m alembic upgrade head

DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/grand_openings \
  python seed_data.py
```

> Local migration/seed requires `psycopg[binary]` installed locally:
> `pip install "psycopg[binary]"`

Run from the `backend/` directory (alembic.ini lives there).

## Running Tests

```bash
# Unit + integration (no Docker required — uses SQLite in-memory)
# 73 tests as of Phase 3
python -m pytest tests/unit/ tests/integration/ -v

# E2E smoke (requires docker compose up -d)
python -m pytest tests/e2e/ -v
```

## Pages

| Route | Description |
|-------|-------------|
| `/` | Event list with filters |
| `/events/:id` | Event detail with sources and claims |
| `/admin/ingest` | Paste a URL to trigger manual ingestion |
| `/admin/events/:id` | Verify / reject a candidate event |

## Architecture

```
Browser → nginx (frontend:80) → /api/* → FastAPI (backend-api:8000) → Postgres
                                          ↓
                                    MCP server (bounded tools only)
```

- Frontend talks only to the backend API.
- Frontend never calls MCP directly.
- LangGraph (Phase 4+) orchestrates ingestion workflows.
- Postgres is the system of record.

## Data Layers

1. `source_documents` — raw fetched pages
2. `event_claims` — extracted atomic claims with confidence scores
3. `events` — canonical event records (locations, status, category)

## Project Standards

See `docs/standards/README.md` for coding conventions, architecture guardrails, and testing strategy.

