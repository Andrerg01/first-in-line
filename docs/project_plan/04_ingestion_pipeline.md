# Ingestion Pipeline

## Pipeline Philosophy

Most data acquisition should be deterministic.

LLMs should be used only where deterministic code is weak:

- messy text interpretation
- event extraction
- ambiguity handling
- conflict reasoning
- follow-up query generation

## Deterministic Tasks

1. Generate search queries.
2. Search the web.
3. Collect top N URLs.
4. Canonicalize URLs.
5. Fetch pages.
6. Extract visible text.
7. Normalize visible text.
8. Hash normalized text.
9. Skip already-seen documents.
10. Store source documents.
11. Run simple duplicate checks.

## Intelligent Tasks

1. Classify whether a page is relevant.
2. Extract structured candidate event information.
3. Extract source evidence snippets.
4. Compare candidate to similar known events.
5. Decide whether the candidate is:
   - new event
   - possible duplicate
   - conflicting source
   - irrelevant
6. Propose follow-up search queries if confidence is low or claims conflict.
7. Pick best canonical value when multiple sources disagree.

## Initial Manual URL Pipeline

```text
User pastes URL
  -> backend receives URL
  -> MCP fetch_page
  -> extract visible text
  -> normalize text
  -> hash text
  -> check source_documents by hash
  -> if duplicate, return existing source/event links
  -> LLM classify relevance
  -> if relevant, LLM extract claims
  -> find similar events
  -> create candidate event or needs_review record
  -> frontend displays candidate + evidence
````

## Scheduled Daily Pipeline

```text
CronJob starts
  -> create search_run
  -> load target locations
  -> generate search queries
  -> for each query (with SCRAPER_RATE_LIMIT_SECONDS delay between):
       -> web.search (telemetry recorded)
       -> store search_results
       -> canonicalize URLs
       -> dedupe across queries (seen-URL set)
  -> for each unique URL (up to max_urls_per_run):
       -> web.fetch_page (telemetry recorded)
       -> web.normalize_text (telemetry recorded)
       -> hash normalized text
       -> db.store_source_document (telemetry recorded, skip if duplicate hash)
  -> flush all tool-call telemetry to pipeline_tool_calls
  -> finish_search_run with aggregate stats
  -> (future) classify relevance
  -> (future) extract claims
  -> (future) find similar events
  -> (future) save candidate events
```

## Search Query Strategy

Initial query templates:

```text
"grand opening" "{city} {state}" restaurant
"soft opening" "{city} {state}" restaurant
"ribbon cutting" "{city} {state}" restaurant
"now open" "{city} {state}" restaurant
"grand opening" "{city} {state}" cafe
"grand opening" "{city} {state}" brewery
"grand opening" "{city} {state}" food truck
"new restaurant opening" "{city} {state}"
```

Targeted source templates:

```text
site:localchamber.org "ribbon cutting" "{city}"
site:localnews.com "grand opening" "{city}"
site:cityeventcalendar.gov "grand opening" "{city}"
```

## Source Fetching Strategy

The fetcher should be responsible and robust.

Fetch method order:

1. Basic HTTP fetch with `httpx`.
2. Readability/trafilatura-style visible text extraction.
3. Playwright fallback for public JS-rendered pages.
4. RSS/feed parsing where available.
5. Manual fallback for pages that cannot be fetched.

The fetcher should include:

```text
timeouts
retries
backoff
domain-level rate limits
robots.txt awareness
content-type checks
canonical URL extraction
basic HTML cleaning
failure reason logging
```

Avoid:

```text
bypassing paywalls
evading authentication
circumventing bot protections
scraping private content
hammering domains with high request rates
```

## Text Hashing

Hash normalized visible text, not raw HTML.

Normalization should include:

```text
lowercasing where appropriate
removing excessive whitespace
removing tracking boilerplate if possible
removing repeated navigation/footer text if possible
normalizing unicode
stripping UTM parameters from URLs
```

Store:

```text
visible_text_hash
canonical_url
domain
fetched_at
```

## LLM Extraction Output

The model should return structured JSON.

Target shape:

```json
{
  "is_relevant": true,
  "relevance_reason": "The page announces a public grand opening for a restaurant.",
  "business_name": "Example Tacos",
  "event_name": "Grand Opening Celebration",
  "event_type": "grand_opening",
  "category": "restaurant",
  "event_date": "2026-06-14T10:00:00",
  "address": "123 Main St, Greenville, SC",
  "city": "Greenville",
  "state": "SC",
  "promotions": [
    "First 50 customers receive free tacos"
  ],
  "notes": "Ribbon cutting at 10 AM.",
  "evidence_quotes": [
    "Join us June 14 for our grand opening..."
  ],
  "confidence_score": 0.88,
  "missing_fields": []
}
```

## Conflict Handling

If sources disagree:

```text
source A says June 14
source B says June 15
source C says "this Friday"
```

The system should:

1. Store all claims.
2. Mark canonical event as `needs_review` if conflict is material.
3. Prefer sources with:

   * direct business website
   * official chamber/city page
   * recent source date
   * explicit date over relative date
   * multiple agreeing sources
4. Ask LLM for best guess only after preserving raw claims.

## Follow-Up Search Prompt Generation

If confidence is low or conflict exists, LLM can propose search prompts.

Example:

```text
"Example Tacos Greenville SC grand opening June 2026"
"Example Tacos 123 Main St Greenville ribbon cutting"
"Example Tacos Greenville opening date"
```

These prompts should be stored in `processing_decisions` or a later `followup_queries` table.

## Telemetry

Every MCP tool call is recorded as a `pipeline_tool_calls` row in Postgres.

Schema: `id`, `search_run_id`, `tool_name`, `input_summary`, `outcome`, `duration_ms`,
`http_status`, `error_message`, `attempt_number`, `created_at`.

Outcome codes: `success`, `error`, `timeout`, `rate_limit`, `duplicate`, `skipped`.

Aggregate stats (`queries_executed`, `search_results_found`, `urls_attempted`,
`source_docs_created`, `source_docs_skipped`, `fetch_errors`, `elapsed_seconds`) are written to
`search_runs` when the run finishes. These exist for fast dashboard queries without scanning
`pipeline_tool_calls`.

Telemetry flush failures are non-fatal — they are logged at WARNING and the run continues.

## Rate-Limit Handling

DuckDuckGo rate-limits by hanging rather than returning HTTP 429.

Protections in place:

| Layer | Mechanism |
|-------|-----------|
| MCP server (`web.search`) | `_SEARCH_TIMEOUT=8s` hard timeout per query |
| Worker `mcp_client.search()` | `timeout=12s`, `max_retries=1`; logs `RATE LIMIT WARNING` when all retries time out |
| Worker pipeline | `SCRAPER_RATE_LIMIT_SECONDS` (default `2.0`) sleep between consecutive queries |

Set `SCRAPER_RATE_LIMIT_SECONDS=0` in test environments to keep tests fast.

---

## LLM Call Logging (Phase 5 requirement)

Every OpenAI API call must be logged with full token accounting before the
system is used in production or incurs real cost.

### What to log

Each call to an LLM should produce a `llm_calls` row with:

```text
id                  UUID primary key
source_document_id  FK → source_documents (nullable)
event_id            FK → events (nullable)
call_type           "extraction" | "classification" | "conflict_resolution" | "followup_query"
model               e.g. "gpt-4o-mini"
prompt_tokens       integer — tokens in the system + user messages
completion_tokens   integer — tokens in the assistant response
total_tokens        integer — sum; may differ if cached
cost_usd            numeric(12,8) — derived from model pricing table at call time
latency_ms          integer — round-trip wall time
status              "success" | "validation_error" | "api_error"
error_message       text (nullable)
created_at          timestamp with time zone
```

### Implementation notes

- The OpenAI Python client returns `completion.usage` with
  `prompt_tokens`, `completion_tokens`, and `total_tokens` on every call.
  These must be captured and persisted alongside the decision record.
- A lightweight `ModelPricing` lookup (dict or DB table) converts tokens
  to estimated USD cost. Starting values: gpt-4o-mini input $0.15/1M tokens,
  output $0.60/1M tokens.
- `processing_decisions` should gain FK `llm_call_id → llm_calls.id` so any
  decision record can trace back to the exact LLM call that produced it.
- The existing `model_name` column on `processing_decisions` is a stopgap;
  it can be deprecated once `llm_calls` is in place.

### Alembic migration

Add in Phase 5 as part of the LangGraph extraction workflow migration:

```text
create table llm_calls (...)
alter table processing_decisions add column llm_call_id uuid references llm_calls(id)
```

---

## Multi-Event Page Support (Phase 5 requirement)

Some pages announce more than one business opening (e.g. a news roundup,
a chamber newsletter, a "5 new restaurants opening this summer" article).
The pipeline must handle these correctly.

### Detection step

Before extraction, a classification step determines how many distinct events
the page likely contains:

```text
classify_page_event_count node:
  input:  normalized page text
  output: { "event_count_estimate": 1 | "multi", "reasoning": "..." }
```

A heuristic pre-filter (count of business-name-like patterns, list structures,
heading count) can gate the LLM call to reduce cost.

### Extraction shape for multi-event pages

When `event_count_estimate == "multi"`, the extraction prompt requests a list:

```json
{
  "events": [
    {
      "is_relevant": true,
      "business_name": "...",
      ...
    },
    {
      "is_relevant": true,
      "business_name": "...",
      ...
    }
  ]
}
```

Pydantic schema: `MultiEventExtractionResult` wrapping
`list[LLMExtractionResult]`.

### Persistence

Each item in the `events` list goes through the same save path as a single
event: one `SourceDocument`, one `Event` per relevant item, all sharing the
same `source_document_id`.

The `event_sources` join table links one source document to many events.

### Plan placement

- Phase 5 (LangGraph): add `classify_page_event_count` node before
  `extract_event_claims` node.
- Phase 5: implement `MultiEventExtractionResult` schema alongside
  `LLMExtractionResult`.
- Phase 5: update `save_candidate` node to iterate over
  `extraction_result.events` when the multi-event path was taken.
