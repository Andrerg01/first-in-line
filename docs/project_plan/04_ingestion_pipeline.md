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
  -> execute search
  -> store search_results
  -> fetch result pages
  -> normalize/hash
  -> skip duplicates
  -> store new source_documents
  -> classify relevance
  -> extract claims
  -> find similar events
  -> save candidate events
  -> mark run completed
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
