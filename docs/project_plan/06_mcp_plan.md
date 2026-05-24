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
  "provider": "brave",
  "query": "...",
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

Search provider is controlled by the `SEARCH_PROVIDER` environment variable:

| Value | Behaviour |
|-------|-----------|
| `duckduckgo` | DuckDuckGo only (free, no key, ~10 results/query) |
| `brave` | Brave Search API only (requires `BRAVE_SEARCH_API_KEY`, up to 20 results/query) |
| `duckduckgo+brave` | DuckDuckGo first; Brave fallback when DDG returns 0 results |
| `stub` | Deterministic stubs for testing (no network) |

**Brave rate limiting:** The free tier enforces 1 request/second.
The implementation reads `X-RateLimit-Reset` and `X-RateLimit-Remaining` from
every response, retries up to 3 times on HTTP 429, and proactively sleeps when
the per-second quota hits 0 to prevent the next sequential call from immediately
hitting a 429.

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

### SSRF protection

`web.fetch_page` validates the target URL with `_is_safe_url` before fetching:
- blocks non-http/https schemes
- resolves the hostname and rejects private/internal IP ranges
- blocks known internal service hostnames

**Known limitation (backlog):** the current guard resolves the hostname at validation
time and then re-resolves it at fetch time.  A DNS rebinding attack (public IP during
validation → private IP at request time) can bypass the guard.  Hardening approach:
pin the validated IP in the outbound request (pass resolved IP as target, set `Host`
header to the original hostname) so both resolution steps use the same address.
Track this as a security hardening task before any public deployment.

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
