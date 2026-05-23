# Grand Opening Radar - Agent Instructions

## Project Mission

Build Grand Opening Radar as a portfolio-grade system that discovers local grand opening events (starting with Greenville, SC), preserves source evidence, extracts structured claims, and maintains canonical event records with human-review capability.

## Product Scope

Primary categories:
- restaurant
- cafe
- food truck
- brewery
- retail opening

Primary user value:
- discover upcoming openings by map, calendar, and list
- inspect source evidence and extracted claims
- allow admin verification, rejection, and merging

## Core Architecture Rules

System components:
- Frontend: React
- Backend API: FastAPI
- Database: Postgres
- Ingestion orchestration: LangGraph
- Tool layer: MCP server
- LLM provider: OpenAI

Hard boundaries:
1. Frontend talks only to backend API.
2. Frontend never calls MCP directly.
3. MCP is a bounded toolbox, not orchestration logic.
4. LangGraph orchestrates ingestion workflows.
5. Postgres is the system of record.

## Data Truth Model

Always preserve three layers:
1. Raw source documents
2. Extracted atomic claims
3. Canonical event records

Never treat one LLM response as final truth.

## Deterministic vs Intelligent Work

Deterministic first for:
- URL canonicalization
- fetch/retry/backoff/rate limits
- visible text extraction and normalization
- content hashing and duplicate detection
- database CRUD and status transitions

LLM usage only where deterministic code is weak:
- relevance classification
- structured event extraction
- evidence quote extraction
- conflict reasoning
- follow-up query generation

## Security and Tooling Constraints

Do not expose generic dangerous tools in MCP:
- run_sql
- delete_all
- arbitrary_file_read
- arbitrary_http_post

Expose only typed, narrow tools such as:
- web.fetch_page
- web.normalize_text
- web.search
- geo.geocode_address
- db.find_source_by_hash
- db.find_similar_events
- db.insert_candidate_event

## Responsible Scraping Rules

Must include:
- timeouts, retries, backoff
- domain-level rate limits
- robots.txt awareness where practical
- content-type checks
- failure reason logging

Must avoid:
- paywall bypassing
- auth bypassing
- private-content scraping
- aggressive request patterns

## Validation and Reliability

- Validate all LLM outputs with Pydantic before persistence.
- Store evidence quotes and claim-level confidence.
- Mark material conflicts as needs_review.
- Prefer deterministic matching before LLM conflict resolution.

## Environment and Deployment Expectations

Local development baseline:
- Docker Compose services: postgres, backend-api, frontend, mcp-server
- worker initially runnable manually

Cloud target baseline:
- single AKS cluster
- namespaces: dev, indus, prod
- one managed Postgres server with env-specific db/schema separation
- ingress routes root to frontend and /api/* to backend

## Cost Discipline

Follow low-cost defaults:
- one daily scraper run
- dedupe via visible text hash before LLM
- process only capped daily page volumes through LLM
- use cheaper models for simple classification/extraction
- reserve stronger models for ambiguity/conflict cases

## Phase-Driven Delivery

Implement in order:
1. Phase 0: repository and local skeleton ✅ COMPLETE
2. Phase 1: schema and backend CRUD ✅ COMPLETE
3. Phase 2: basic frontend ✅ COMPLETE
4. Phase 3: manual URL ingestion ✅ COMPLETE
5. Phase 4+: scheduled search, LangGraph, dedupe/review, map/calendar, cloud, CI/CD, notifications, polish

Do not overbuild future phases while the current phase is incomplete.

## Current Execution Focus (Phase 4)

Phase 3 is complete. The next phase covers scheduled automated search ingestion,
LangGraph orchestration, deduplication/review workflows, map/calendar views,
cloud deployment, CI/CD, and notifications.

Required Phase 4 entry criteria:
- Scheduled scraper job (cron or worker)
- LangGraph pipeline nodes for search → fetch → extract → dedupe
- Admin review queue for candidate events
- Map view (Phase 5 stretch)

## Git Workflow

Branch strategy:
- `main` — protected; only receives PRs from `develop` (releases)
- `develop` — protected; integration branch; receives all feature/fix/refactor PRs
- Feature/fix/refactor branches: always created from `develop`

Branch naming:
- `feat/short-description` — new feature
- `fix/short-description` — bug fix
- `refactor/short-description` — structural improvement
- `docs/short-description` — documentation only
- `test/short-description` — tests only

Rules:
- NEVER push directly to `main` or `develop`.
- NEVER open a PR to `main` from a feature branch; PRs go to `develop`.
- Every PR must pass tests and reviewer approval before merging.
- Squash or rebase to keep `develop` history clean.

## Versioning

The single source of truth for version is the `VERSION` file at the repository root.

Format: `MAJOR.MINOR.PATCH` (SemVer)

Bump rules:
- PATCH — bug fixes, documentation, style, test-only changes
- MINOR — new feature, new endpoint, new service, new model
- MAJOR — phase completion milestone, breaking API change, or explicitly requested

Every PR that changes code must include a `VERSION` bump as part of the same commit.
The reviewer must verify the bump is present and the correct level.

## Coding Conventions

Repository standards source:
- docs/standards/README.md
- AGENTS.md

General:
- Keep modules small and explicit.
- Prefer typed interfaces and clear schemas.
- Log decisions and failure reasons.
- Use UTC timestamps in persisted records.

Backend:
- FastAPI routers by domain (health, events, ingest, admin).
- service/repository separation.
- migrations via Alembic.
- keep main.py as composition/bootstrap only.
- include docstrings and type hints for non-trivial functions.
- split large files before they become monoliths.

Frontend:
- Vite + React Router.
- pages for list, detail, admin ingest, admin review.
- avoid hardcoded pod/service URLs in browser code.

Worker/LangGraph:
- isolate graph nodes for testability.
- persist processing decisions for auditability.

## Definition of Done (Any Task)

A task is done only when:
1. implementation exists
2. local run path is documented
3. expected outputs are verifiable
4. obvious edge-case failures are handled or explicitly documented
5. changes stay inside current phase scope unless explicitly requested
6. relevant tests exist or testing gaps are explicitly called out
7. docs are updated when behavior/contracts changed

## When in Doubt

Prioritize:
1. evidence preservation
2. deterministic correctness
3. safe bounded tooling
4. low-cost operation
5. incremental deliverables that meet current phase exit criteria
