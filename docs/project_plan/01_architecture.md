# Architecture

## Components

## 1. Frontend

React application.

Responsibilities:

- Display events.
- Display event detail pages.
- Display source evidence.
- Provide map view.
- Provide calendar view.
- Provide admin review tools.
- Allow manual URL ingestion.
- Later: user alert preferences.

The frontend should not call MCP directly.

Frontend talks only to the backend API.

## 2. Backend API

Python FastAPI service.

Responsibilities:

- Serve frontend API endpoints.
- Read/write canonical app data.
- Provide admin review endpoints.
- Trigger manual URL ingestion.
- Expose event list, map, calendar, and source evidence endpoints.
- Handle auth later if needed.

Example endpoint groups:

```text
/api/events
/api/events/{event_id}
/api/events/{event_id}/claims
/api/events/{event_id}/sources
/api/ingest/manual-url
/api/admin/review
/api/admin/merge
````

## 3. MCP Server

Python MCP server.

Responsibilities:

* Expose bounded tools.
* Keep tooling reusable between backend and worker.
* Avoid arbitrary SQL tools.
* Avoid core orchestration logic.

MCP should be a toolbox, not the brain.

Initial MCP tool groups:

```text
web.search
web.fetch_page
web.extract_visible_text
web.normalize_text
web.hash_text

geo.geocode_address
geo.distance_between

db.find_source_by_hash
db.find_similar_events
db.insert_candidate_event
db.insert_event_claim
db.update_event_status
```

Do not expose a generic `run_sql` tool to the model.

## 4. Ingestion Worker

Python scheduled worker.

Responsibilities:

* Run scheduled discovery jobs.
* Generate search queries.
* Fetch and deduplicate source documents.
* Run LangGraph extraction workflow.
* Save candidate events and claims.
* Record processing decisions.

Can be run as:

```text
local CLI command
Docker Compose service
Kubernetes CronJob
Azure Container Apps Job
```

## 5. LangGraph

LangGraph orchestrates ingestion workflows.

Responsibilities:

* Manage workflow state.
* Handle conditional routing.
* Separate deterministic and intelligent steps.
* Preserve intermediate results.
* Support later retries and human-in-the-loop review.

Initial graph:

```text
start
  -> build_search_queries
  -> search_web
  -> fetch_sources
  -> dedupe_sources
  -> classify_relevance
  -> extract_event_claims
  -> find_similar_events
  -> decide_event_action
  -> save_candidate
  -> propose_followup_queries_if_needed
  -> end
```

## 6. Postgres

Postgres is the system of record.

Stores:

* Locations
* Search runs
* Search results
* Source documents
* Events
* Event claims
* Event-source relationships
* Processing decisions
* Later: users and alert preferences

## 7. OpenAI API

Used for intelligent tasks:

* Classifying whether a page is relevant.
* Extracting structured event information.
* Extracting evidence quotes.
* Resolving ambiguous/conflicting claims.
* Proposing follow-up search prompts.

Not used for:

* Fetching pages.
* Hashing.
* URL canonicalization.
* Simple duplicate detection.
* Basic database operations.
