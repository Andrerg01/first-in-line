# LangGraph Plan

## Purpose

LangGraph coordinates the ingestion workflow. It should manage state and routing, not hide all logic inside one monolithic agent prompt.

## Graph State

Initial graph state:

```text
run_id
location
search_queries
search_results
source_documents
new_source_documents
relevant_documents
extracted_candidates
event_claims
similar_events
decisions
errors
````

## Nodes

## `build_search_queries`

Type: deterministic.

Input:

```text
location
query templates
```

Output:

```text
search_queries
```

## `search_web`

Type: deterministic tool call.

Uses MCP tool:

```text
web.search
```

Input:

```text
search_queries
max_results_per_query
```

Output:

```text
search_results
```

## `fetch_sources`

Type: deterministic tool call.

Uses MCP tool:

```text
web.fetch_page
```

Input:

```text
search_results
```

Output:

```text
source_documents
```

## `dedupe_sources`

Type: deterministic.

Input:

```text
source_documents
```

Checks:

```text
canonical_url
visible_text_hash
```

Output:

```text
new_source_documents
duplicate_source_documents
```

## `classify_relevance`

Type: LLM.

Input:

```text
new_source_documents
```

Output:

```text
relevance decisions
```

Possible labels:

```text
relevant_grand_opening
possibly_relevant
irrelevant
needs_more_context
```

## `extract_event_claims`

Type: LLM.

Input:

```text
relevant_documents
```

Output:

```text
candidate event fields
atomic event claims
evidence quotes
confidence score
```

## `find_similar_events`

Type: deterministic first, embedding later.

Input:

```text
candidate event
```

Matching signals:

```text
business name similarity
address similarity
city/state
event date window
lat/lon distance
category
```

Output:

```text
similar_events
```

## `decide_event_action`

Type: deterministic first, LLM-assisted later.

Possible actions:

```text
create_new_candidate
attach_source_to_existing_event
mark_possible_duplicate
mark_conflict
reject
needs_review
```

## `save_candidate`

Type: deterministic tool call.

Uses MCP safe database tools or direct backend repository code.

Output:

```text
created/updated event IDs
created claims
processing decisions
```

## `propose_followup_queries`

Type: LLM, conditional.

Run only if:

```text
confidence is low
event date is missing
address is missing
claims conflict
similar events exist but match is uncertain
```

Output:

```text
follow-up search queries
```

## Recommended First Version

Do not build the full graph immediately.

Start with this smaller graph:

```text
fetch_source
  -> dedupe_source
  -> classify_relevance
  -> extract_event_claims
  -> save_candidate
```

Then add search and conflict handling after manual URL ingestion works.