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
1. Phase 0: repository and local skeleton
2. Phase 1: schema and backend CRUD
3. Phase 2: basic frontend
4. Phase 3: manual URL ingestion
5. Phase 4+: scheduled search, LangGraph, dedupe/review, map/calendar, cloud, CI/CD, notifications, polish

Do not overbuild future phases while Phase 0 is incomplete.

## Current Execution Focus (Phase 0)

Required Phase 0 deliverables:
- monorepo structure
- docker-compose.yml
- backend health endpoint
- frontend placeholder page
- Postgres container
- MCP server skeleton with health/tool-list
- worker no-op CLI command
- .env.example
- initial README

Phase 0 exit criteria:
- docker compose up succeeds
- frontend loads
- backend health returns status ok
- Postgres accepts connections
- MCP server starts
- worker no-op command runs

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
