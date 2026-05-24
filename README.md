# Grand Opening Radar

Grand Opening Radar discovers nearby business grand openings and preserves source evidence, extracted claims, and canonical events — starting with Greenville, SC.

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Monorepo skeleton, Docker Compose, service stubs | ✅ Complete |
| 1 | Database schema, Alembic migrations, CRUD backend, seed data | ✅ Complete |
| 2 | Basic frontend — event list, event detail, admin verify/reject | ✅ Complete |
| 3 | Manual URL ingestion — AdminIngest page, OpenAI extraction pipeline | ✅ Complete |
| 4 | Scheduled worker — search → fetch → dedupe → telemetry pipeline | ✅ Complete |
| 5 | LangGraph extraction pipeline — classify, extract, multi-event, LLM call logging | ✅ Complete |
| 6 | Duplicate handling and review queue improvements | ✅ In Progress |
| 7+ | Map/calendar, CI/CD, notifications | Planned |

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

> **BRAVE_SEARCH_API_KEY** (optional) required when `SEARCH_PROVIDER` is `brave`
> or `duckduckgo+brave`.  Free tier provides 2,000 queries/month.

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
python -m pytest tests/unit/ tests/integration/ -v

# E2E smoke (requires docker compose up -d)
python -m pytest tests/e2e/ -v
```

## Running the Worker

The discovery worker is normally triggered by Docker Compose command or cron. To run manually:

```bash
# Inside the running worker container (one-shot run)
docker compose exec worker python -m worker.app.cli run

# Dry-run (no API/DB calls)
docker compose exec worker python -m worker.app.cli run --dry-run
```

To run locally (outside Docker), set required env vars explicitly — `.env` is only
loaded by Docker Compose:

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:BACKEND_API_URL="http://localhost:8000"
$env:MCP_SERVER_URL="http://localhost:9000"
$env:SCRAPER_MAX_RESULTS_PER_QUERY="15"
$env:OPENAI_API_KEY=(Get-Content .env | Select-String "OPENAI_API_KEY" | ForEach-Object { $_.ToString().Split("=",2)[1] })
python -m worker.app.cli run_once
```

**Worker environment variables** (all in `.env`, all have sensible defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPER_TARGET_LOCATION` | `Greenville, SC` | Location injected into search queries |
| `SCRAPER_MAX_RESULTS_PER_QUERY` | `10` | Max search results to request per query |
| `SCRAPER_DAILY_PAGE_LIMIT` | `50` | Max URLs to fetch per run |
| `SCRAPER_RATE_LIMIT_SECONDS` | `2.0` | Pause between consecutive queries (seconds) |
| `WORKER_REQUEST_TIMEOUT` | `30.0` | HTTP timeout for MCP/API calls (seconds) |
| `WORKER_BACKOFF_BASE` | `1.0` | Exponential backoff base for retries |
| `WORKER_MAX_RETRIES` | `3` | Max retries on transient failures |
| `OPENAI_API_KEY` | _(none)_ | OpenAI API key; if unset, extraction phase is skipped |
| `WORKER_CLASSIFY_MODEL` | `gpt-4o-mini` | Model used for relevance and count classification |
| `WORKER_EXTRACT_MODEL` | `gpt-4o-mini` | Model used for event extraction |
| `SCRAPER_LLM_PAGE_LIMIT` | `30` | Max pages to send through the LLM extraction pipeline per run |
| `SEARCH_PROVIDER` | `duckduckgo` | Search backend: `duckduckgo`, `brave`, `duckduckgo+brave`, or `stub` |
| `BRAVE_SEARCH_API_KEY` | _(none)_ | API key for Brave Search; required when `SEARCH_PROVIDER` includes `brave` |

## Pages

| Route | Description |
|-------|-------------|
| `/` | Event list with filters |
| `/events/:id` | Event detail with sources and claims |
| `/admin/ingest` | Paste a URL to trigger manual ingestion |
| `/admin/review` | Review queue with duplicate merge workflow |
| `/admin/events/:id` | Verify / reject a candidate event |

## Phase 6 Duplicate Handling

Phase 6 adds deterministic duplicate detection and manual merge tooling:

- Event-level duplicate fields on `events`:
  - `possible_duplicate` (bool)
  - `duplicate_of_id` (nullable UUID FK to `events.id`)
  - `normalized_business_name` (text)
- Worker ingestion now computes deterministic similarity (name + address + date)
  and auto-flags likely duplicates.
- Admin merge and conflict endpoints:
  - `GET /api/admin/events/{event_id}/conflicts?other_id={uuid}`
  - `POST /api/admin/events/{event_id}/flag-duplicate`
  - `POST /api/admin/events/{event_id}/merge`
- Retroactive duplicate scan endpoint:
  - `POST /api/admin/dedup/retroactive-run`

The duplicate logic is now split into smaller backend modules:

- `backend/app/services/dedup_scoring.py` — normalization + scoring primitives
- `backend/app/services/dedup_admin_service.py` — merge, conflict, flagging, retroactive scan
- `backend/app/services/dedup_service.py` — thin compatibility facade

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

