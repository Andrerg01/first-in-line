# MCP Plan

## Purpose

MCP provides a reusable tool layer for the backend API and ingestion worker.

MCP is not the main application brain.

LangGraph owns orchestration.  
Postgres owns persistent truth.  
MCP owns bounded actions.

## Initial MCP Tools

## `web.fetch_page`

Fetches a public web page and extracts basic metadata.

Input:

```json
{
  "url": "https://example.com/grand-opening"
}
````

Output:

```json
{
  "url": "https://example.com/grand-opening",
  "final_url": "https://example.com/grand-opening",
  "status_code": 200,
  "content_type": "text/html",
  "title": "Grand Opening",
  "html": "...",
  "visible_text": "...",
  "detected_published_at": "2026-06-01T12:00:00",
  "fetch_method": "httpx",
  "error": null
}
```

## `web.normalize_text`

Input:

```json
{
  "text": "raw visible text"
}
```

Output:

```json
{
  "normalized_text": "clean normalized text",
  "hash": "sha256..."
}
```

## `web.search`

Input:

```json
{
  "query": "\"grand opening\" \"Greenville SC\" restaurant",
  "max_results": 10
}
```

Output:

```json
{
  "results": [
    {
      "rank": 1,
      "title": "Example Grand Opening",
      "url": "https://example.com",
      "snippet": "..."
    }
  ]
}
```

Initial implementation can be stubbed/manual if no search API is configured yet.

## `geo.geocode_address`

Input:

```json
{
  "address": "123 Main St, Greenville, SC"
}
```

Output:

```json
{
  "lat": 34.8526,
  "lon": -82.394,
  "normalized_address": "123 Main St, Greenville, SC 29601",
  "confidence": 0.91
}
```

## `db.find_source_by_hash`

Input:

```json
{
  "visible_text_hash": "sha256..."
}
```

Output:

```json
{
  "exists": true,
  "source_document_id": "uuid"
}
```

## `db.find_similar_events`

Input:

```json
{
  "business_name": "Example Tacos",
  "city": "Greenville",
  "state": "SC",
  "event_date": "2026-06-14",
  "address": "123 Main St"
}
```

Output:

```json
{
  "matches": [
    {
      "event_id": "uuid",
      "business_name": "Example Tacos",
      "similarity_score": 0.87,
      "match_reasons": [
        "same city",
        "similar business name",
        "same event date"
      ]
    }
  ]
}
```

## `db.insert_candidate_event`

Input:

```json
{
  "business_name": "Example Tacos",
  "event_name": "Grand Opening",
  "event_type": "grand_opening",
  "category": "restaurant",
  "event_date": "2026-06-14T10:00:00",
  "address": "123 Main St, Greenville, SC",
  "promotion_text": "First 50 customers get free tacos",
  "confidence_score": 0.88,
  "source_document_id": "uuid"
}
```

Output:

```json
{
  "event_id": "uuid",
  "status": "candidate"
}
```

## Security Rules

Do not expose:

```text
run_sql
delete_all
arbitrary_file_read
arbitrary_http_post
```

Prefer typed, narrow tools.

## Local MCP Deployment

```text
mcp-server
  port: 9000
  internal URL: http://mcp-server:9000
```

Backend and worker call MCP over the internal Docker/Kubernetes network.

## Kubernetes MCP Deployment

```text
Deployment:
  mcp-server

Service:
  mcp-server

Internal DNS:
  http://mcp-server:9000
```

React should never call MCP directly.
