
# Initial Ticket Backlog

## Epic 0 — Repo Setup

### Ticket 0.1 — Create Monorepo Structure

Create:

```text
frontend/
backend/
worker/
mcp_server/
shared/
infra/
docs/
````

### Ticket 0.2 — Add Docker Compose

Services:

```text
postgres
backend-api
frontend
mcp-server
```

Worker can be run manually first.

### Ticket 0.3 — Add Environment Template

Create:

```text
.env.example
```

With:

```text
APP_ENV=local
DATABASE_URL=
OPENAI_API_KEY=
MCP_SERVER_URL=
LOG_LEVEL=INFO
```

---

## Epic 1 — Backend Skeleton

### Ticket 1.1 — Create FastAPI App

Add:

```text
GET /health
```

### Ticket 1.2 — Add Config Loader

Load environment variables.

### Ticket 1.3 — Add Database Connection

Connect to Postgres.

### Ticket 1.4 — Add Alembic

Set up migrations.

---

## Epic 2 — Database Schema

### Ticket 2.1 — Create Core Tables

Create migrations for:

```text
locations
search_runs
search_results
source_documents
events
event_sources
event_claims
processing_decisions
```

### Ticket 2.2 — Add Seed Data

Create one fake Greenville event.

### Ticket 2.3 — Add Event Repository

Implement basic CRUD.

---

## Epic 3 — Event API

### Ticket 3.1 — Event List Endpoint

```text
GET /api/events
```

### Ticket 3.2 — Event Detail Endpoint

```text
GET /api/events/{event_id}
```

### Ticket 3.3 — Event Claims Endpoint

```text
GET /api/events/{event_id}/claims
```

### Ticket 3.4 — Event Sources Endpoint

```text
GET /api/events/{event_id}/sources
```

---

## Epic 4 — Frontend Skeleton

### Ticket 4.1 — Create React App

Use Vite.

### Ticket 4.2 — Add Routing

Routes:

```text
/
/events/:eventId
/admin/ingest
/admin/review
```

### Ticket 4.3 — Add Event List Page

Read from backend.

### Ticket 4.4 — Add Event Detail Page

Show event, claims, sources.

---

## Epic 5 — MCP Skeleton

### Ticket 5.1 — Create MCP Server

Add server skeleton.

### Ticket 5.2 — Add Fetch Page Tool

Tool:

```text
web.fetch_page
```

### Ticket 5.3 — Add Normalize Text Tool

Tool:

```text
web.normalize_text
```

### Ticket 5.4 — Add Source Hash Lookup Tool

Tool:

```text
db.find_source_by_hash
```

---

## Epic 6 — Manual URL Ingestion

### Ticket 6.1 — Create Extraction Schema

Pydantic schema for LLM output.

### Ticket 6.2 — Create Extraction Prompt

Prompt should extract:

```text
business name
event type
event date
address
promotion
notes
evidence quotes
confidence
```

### Ticket 6.3 — Add Manual Ingestion Endpoint

```text
POST /api/ingest/manual-url
```

### Ticket 6.4 — Save Source Document

Store:

```text
url
canonical_url
title
visible_text
visible_text_hash
fetched_at
```

### Ticket 6.5 — Save Event Claims

Store extracted atomic claims.

### Ticket 6.6 — Create Candidate Event

Create event with status:

```text
candidate
```

### Ticket 6.7 — Build Manual Ingestion UI

Paste URL, run extraction, show result.

---

## Epic 7 — Worker

### Ticket 7.1 — Create Worker CLI

Commands:

```text
run-once
run-manual-url
```

### Ticket 7.2 — Add Search Query Generator

Generate Greenville search prompts.

### Ticket 7.3 — Add Search Tool Stub

Initial implementation can return manually configured URLs.

### Ticket 7.4 — Store Search Runs and Results

Write search metadata to Postgres.

---

## Epic 8 — LangGraph

### Ticket 8.1 — Define Graph State

Create state object.

### Ticket 8.2 — Add Relevance Classification Node

LLM classifies source document.

### Ticket 8.3 — Add Event Extraction Node

LLM extracts structured event claims.

### Ticket 8.4 — Add Save Candidate Node

Persist candidate event, claims, and decisions.

### Ticket 8.5 — Add Similar Event Node

Start with deterministic similarity.

---

## Epic 9 — Admin Review

### Ticket 9.1 — Verify Event Endpoint

```text
POST /api/admin/events/{event_id}/verify
```

### Ticket 9.2 — Reject Event Endpoint

```text
POST /api/admin/events/{event_id}/reject
```

### Ticket 9.3 — Review Queue Endpoint

```text
GET /api/admin/review
```

### Ticket 9.4 — Review Queue UI

Show candidates and possible duplicates.

---

## Epic 10 — Cloud

### Ticket 10.1 — Dockerize Backend

### Ticket 10.2 — Dockerize Frontend

### Ticket 10.3 — Dockerize MCP Server

### Ticket 10.4 — Dockerize Worker

### Ticket 10.5 — Create Kubernetes Manifests or Helm Chart

### Ticket 10.6 — Create Dev Namespace Deployment

### Ticket 10.7 — Add Ingress Routing

Routes:

```text
/      -> frontend
/api/* -> backend
```

### Ticket 10.8 — Add Worker CronJob

Run daily.

````

---

## Immediate next move in VSCode

Start with these three files first:

```text
README.md
docs/00_project_overview.md
docs/09_phases.md
````

Then create the repo skeleton:

```text
frontend/
backend/
worker/
mcp_server/
shared/
infra/
docs/
```

The first actual implementation target should be:

```text
Docker Compose + FastAPI /health + React placeholder + Postgres connection
```
