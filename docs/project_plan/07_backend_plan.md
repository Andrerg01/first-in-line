# Backend Plan

## Framework

Use FastAPI.

## Responsibilities

The backend API serves the frontend and handles application-level operations.

It should:

- expose event data
- expose source evidence
- trigger manual URL ingestion
- handle admin review actions
- later handle users and alert subscriptions

## Initial API Endpoints

## Health

```text
GET /health
````

Returns:

```json
{
  "status": "ok"
}
```

## Events

```text
GET /api/events
```

Query params:

```text
city
state
status
category
start_date
end_date
lat
lon
radius_miles
```

Returns event list.

```text
GET /api/events/{event_id}
```

Returns event detail.

```text
GET /api/events/{event_id}/claims
```

Returns extracted claims.

```text
GET /api/events/{event_id}/sources
```

Returns source documents and source URLs.

## Manual Ingestion

```text
POST /api/ingest/manual-url
```

Input:

```json
{
  "url": "https://example.com/grand-opening"
}
```

Output:

```json
{
  "source_document_id": "uuid",
  "event_id": "uuid",
  "status": "candidate",
  "message": "Candidate event created"
}
```

## Admin Review

```text
POST /api/admin/events/{event_id}/verify
POST /api/admin/events/{event_id}/reject
POST /api/admin/events/{event_id}/mark-needs-review
POST /api/admin/events/{event_id}/merge
GET /api/admin/events/{event_id}/conflicts?other_id={event_id}
POST /api/admin/events/{event_id}/flag-duplicate
POST /api/admin/dedup/retroactive-run
```

## Suggested Backend Modules

```text
backend/
  app/
    main.py
    config.py
    db.py
    models/
    schemas/
    routers/
      health.py
      events.py
      ingest.py
      admin.py
    services/
      event_service.py
      ingestion_service.py
      source_service.py
      mcp_client.py
      openai_client.py
    repositories/
      event_repository.py
      source_repository.py
      claims_repository.py
```

## Database Access

Use SQLAlchemy or SQLModel.

Use Alembic for migrations.

## Important Rules

1. Backend is the only thing the frontend talks to.
2. Backend should not trust raw LLM output.
3. All LLM outputs should be validated with Pydantic.
4. Backend should expose evidence and claims, not only final event data.
5. Admin review should be built early.