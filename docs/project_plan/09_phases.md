# Project Phases

## Phase 0 — Repository and Local Skeleton

## Goal

Create the basic project structure and get all services running locally.

## Deliverables

- Monorepo structure.
- Docker Compose.
- FastAPI backend with health endpoint.
- React frontend with placeholder page.
- Postgres container.
- MCP server skeleton.
- Worker skeleton.
- Basic `.env.example`.
- Initial README.

## Suggested Tasks

```text
Create repo
Create /frontend
Create /backend
Create /worker
Create /mcp_server
Create /shared
Create /infra
Create /docs
Add docker-compose.yml
Add backend health endpoint
Add frontend placeholder
Add Postgres service
Add MCP health/tool-list endpoint
Add worker CLI placeholder
````

## Exit Criteria

```text
docker compose up works
frontend loads
backend /health returns ok
Postgres accepts connections
MCP server starts
worker can run a no-op command
```

---

## Phase 1 — Database and CRUD Backend

## Goal

Create the core schema and backend endpoints.

## Deliverables

* Alembic migrations.
* SQLAlchemy/SQLModel models.
* CRUD repositories.
* Event list endpoint.
* Event detail endpoint.
* Source and claims endpoints.
* Seed data.

## Suggested Tasks

```text
Create locations table
Create search_runs table
Create search_results table
Create source_documents table
Create events table
Create event_sources table
Create event_claims table
Create processing_decisions table
Create seed script
Create GET /api/events
Create GET /api/events/{id}
Create GET /api/events/{id}/claims
Create GET /api/events/{id}/sources
```

## Exit Criteria

```text
Seed event appears through API
Claims appear through API
Sources appear through API
```

---

## Phase 2 — Basic Frontend

## Goal

Make the app usable with manually seeded data.

## Deliverables

* Event list page.
* Event detail page.
* Basic filters.
* Admin status buttons.
* Simple styling.

## Suggested Tasks

```text
Create React routing
Create API client
Create EventList page
Create EventDetail page
Show claims and sources
Add verify/reject buttons
Add basic filter by status/date/category
```

## Exit Criteria

```text
User can view seeded events
User can inspect source evidence
User can verify/reject event
```

---

## Phase 3 — Manual URL Ingestion

## Goal

Paste a URL and create a candidate event.

## Deliverables

* MCP `fetch_page` tool.
* Text normalization and hashing.
* Source document storage.
* OpenAI extraction call.
* Pydantic validation.
* Manual ingestion backend endpoint.
* Manual ingestion frontend page.

## Suggested Tasks

```text
Implement MCP web.fetch_page
Implement MCP web.normalize_text
Implement source hash check
Create extraction prompt
Create extraction Pydantic schema
Create POST /api/ingest/manual-url
Create frontend manual URL form
Show extracted candidate
Save event claims
Save processing decisions
```

## Exit Criteria

```text
User pastes URL
System fetches page
System extracts candidate event
System stores source document
System stores event claims
System creates candidate event
Frontend displays candidate and evidence
```

---

## Phase 4 — Deterministic Search and Scheduled Worker

## Goal

Run a daily discovery job without relying on LLMs for search/fetch/deduplication.

## Deliverables

* Search query generator.
* Search provider integration or stub.
* Search result storage.
* Worker `run_once`.
* Source deduplication.
* Local scheduled execution.
* Kubernetes CronJob manifest later.

## Suggested Tasks

```text
Create query templates
Create location config
Implement web.search tool
Store search_results
Fetch top N URLs
Canonicalize URLs
Normalize/hash text
Skip duplicate source_documents
Create processing run logs
Create worker run_once command
```

## Exit Criteria

```text
Worker can search Greenville, SC
Worker stores search results
Worker fetches pages
Worker skips duplicate pages
No LLM required for this phase
```

---

## Phase 5 — LangGraph Extraction Workflow ✅ COMPLETE

## Status

**Completed.** 218 tests passing. VERSION `0.6.1`.

Includes post-completion improvements shipped in the same branch:
- `SEARCH_PROVIDER` env var: `duckduckgo`, `brave`, `duckduckgo+brave`, `stub` modes.
- Brave Search rate-limit handling: header-driven retry on 429, proactive sleep
  when per-second quota exhausted.

## Goal

Convert new source documents into candidate events through a structured graph.

## Deliverables

* LangGraph state definition.
* Relevance classification node.
* **Page event-count classification node** — determines if a page contains
  one or multiple event announcements before extraction.
* Event extraction node (single event path).
* **Multi-event extraction node** — uses `MultiEventExtractionResult` schema
  when the page contains multiple announcements; each extracted event goes
  through the same save path, all linked to the same `source_document_id`.
* Similar event lookup node.
* Save candidate node.
* Processing decision records.
* **LLM call logging** — `llm_calls` table (id, call_type, model,
  prompt_tokens, completion_tokens, total_tokens, cost_usd, latency_ms,
  status, created_at); every OpenAI call persists a row; `processing_decisions`
  gains `llm_call_id` FK.

## Suggested Tasks

```text
Define graph state
Create classify_relevance node
Create classify_page_event_count node (heuristic + LLM)
Create extract_event_claims node (single-event path)
Create extract_multi_event_claims node (multi-event path)
Create find_similar_events node
Create decide_event_action node
Create save_candidate node (handles list of events)
Add model config
Add retry/error handling
Log decisions
Add llm_calls table migration
Add llm_call_id FK to processing_decisions
Implement token-to-cost conversion helper
```

## Exit Criteria

```text
Daily worker can process newly fetched pages
Irrelevant pages are rejected
Relevant pages create candidate events
Multi-event pages produce one event record per announced business
Claims and evidence are stored
Potential duplicates are flagged
Every LLM call has a llm_calls row with token counts and estimated cost
```

---

## Phase 6 — Duplicate Handling and Review Queue

## Goal

Prevent duplicate event records and support manual review.

## Deliverables

* Similarity function.
* Possible duplicate flagging.
* Review queue UI.
* Merge action.
* Conflict display.
* Retroactive duplicate scan action.

## Suggested Tasks

```text
Implement business name normalization
Implement address/date matching
Implement candidate similarity score
Flag possible duplicates
Create review queue endpoint
Create review queue frontend page
Create merge endpoint
Display conflicting claims
Allow admin to choose canonical value
Create retroactive dedup run endpoint
```

## Exit Criteria

```text
Candidate duplicate is flagged
Admin can merge or create new event
Conflicting event dates are visible
Canonical event can be edited/verified
```

---

## Phase 7 — Map and Calendar Views

## Goal

Make the app feel like a useful local discovery tool.

## Deliverables

* Geocoding.
* Map view.
* Calendar view.
* Date/radius filters.

## Suggested Tasks

```text
Implement geo.geocode_address MCP tool
Store lat/lon on events
Create /api/events/map endpoint if useful
Add map page
Add calendar page
Add date filters
Add category filters
```

## Exit Criteria

```text
Verified/candidate events appear on map
Events appear on calendar
User can filter upcoming events
```

---

## Phase 8 — Cloud Deployment

## Goal

Deploy the app to Azure with Kubernetes-style environments.

## Deliverables

* Container images.
* ACR integration.
* AKS namespace manifests or Helm chart.
* Dev namespace deployment.
* Indus namespace deployment.
* Prod namespace deployment.
* Managed Postgres connection.
* Key Vault secret management.
* Ingress.

## Suggested Tasks

```text
Create Dockerfile for frontend
Create Dockerfile for backend
Create Dockerfile for MCP server
Create Dockerfile for worker
Create Kubernetes manifests or Helm chart
Create dev values
Create indus values
Create prod values
Create ingress routing
Set /api route to backend
Set root route to frontend
Configure secrets
Connect to Azure Database for PostgreSQL
```

## Exit Criteria

```text
Frontend reachable through domain
Backend reachable through /api
Worker CronJob runs daily
MCP server reachable internally
Postgres is external managed service
```

---

## Phase 9 — CI/CD

## Goal

Automate build and deployment.

## Deliverables

* CI pipeline.
* Lint/test stage.
* Docker build stage.
* Push to registry.
* Deploy dev from develop branch.
* Deploy prod from main/tag.

## Suggested Branch Model

```text
feature/*
  -> pull request into develop

develop
  -> deploy dev

main
  -> deploy prod

tag
  -> release
```

## Suggested Pipeline Stages

```text
lint
test
build
push
deploy-dev
deploy-prod
```

## Exit Criteria

```text
Merge to develop deploys dev
Merge/tag to main deploys prod
Images are versioned
Secrets are not committed
```

---

## Phase 10 — Notifications

## Goal

Notify users of new relevant openings.

## Deliverables

* User table.
* Alert preferences.
* Email alerts.
* Notification deduplication.
* Later SMS alerts.

## Suggested Tasks

```text
Create users table
Create alert_preferences table
Create sent_alerts table
Create email provider integration
Create daily digest job
Create alert preference UI
Prevent duplicate notifications
```

## Exit Criteria

```text
User can subscribe to alerts
User receives email digest
System does not send duplicate alerts
```

---

## Phase 11 — Admin Authentication

## Goal

Secure the admin-only surfaces (review queue, status changes) behind a real
identity so the app can be exposed publicly without open write access.

## Design Decisions

* **Login with Google (OAuth 2.0 / OIDC)** — no password management; users
  authenticate via their Google account and the system verifies the returned
  identity token.
* **Admin allowlist** — a small, env-var or DB-backed list of Google email
  addresses that are granted admin access. No self-registration; the operator
  controls membership directly.
* **No general user registration** — keep it minimal. Admins log in; everyone
  else is read-only.

## Deliverables

* Google OAuth 2.0 integration on the backend (authorization code flow).
* JWT session tokens issued by the backend after successful Google callback.
* Admin allowlist (start with `ADMIN_EMAILS` env var; migrate to DB table
  later if the list grows).
* Route guards on the frontend for `/admin/*` pages.
* Protected backend endpoints: verify, reject, review-queue write actions.
* Logout endpoint and frontend logout button.

## Suggested Tasks

```text
Register OAuth app in Google Cloud Console
Create GET /auth/google/login (redirect to Google)
Create GET /auth/google/callback (exchange code, issue JWT)
Create POST /auth/logout
Add JWT middleware to admin-only endpoints
Add ADMIN_EMAILS env var to backend config
Add LoginPage frontend page
Add useAuth() context / hook
Protect /admin/* routes with auth redirect
Add logout button to admin nav
```

## Exit Criteria

```text
Unauthenticated users cannot call verify/reject/review-queue write endpoints
Admin navigates to /admin/review and is redirected to Google if not logged in
After Google sign-in, admin lands back on the review queue
Non-allowlisted Google accounts receive 403
Admin can log out and session is invalidated
```

---

## Phase 12 — Polish and Portfolio Packaging

## Goal

Make the project presentable.

## Deliverables

* Clean README.
* Architecture diagram.
* Screenshots.
* Demo data.
* Cost estimate.
* Design tradeoff documentation.
* Responsible scraping note.
* Deployment guide.

## Suggested Tasks

```text
Write README
Add screenshots
Add architecture diagram
Add local setup guide
Add cloud deployment guide
Add database ERD
Add LangGraph workflow diagram
Add MCP tool list
Add cost estimate
Add known limitations
```

## Exit Criteria

```text
A recruiter/engineer can understand the project quickly
The repo runs locally
The deployed app has demo data
The architecture story is clear
```
