# Database Plan

## Philosophy

The database should separate:

1. Raw search results.
2. Fetched source documents.
3. Extracted claims.
4. Canonical events.
5. Processing decisions.

This prevents the app from treating one LLM output as ground truth.

## Schema Layout

All tables live in one of four named PostgreSQL schemas.
The `public` schema is left empty.

| Schema | Purpose | Tables |
|--------|---------|--------|
| `events` | Canonical output — what the frontend reads | `events`, `event_claims`, `event_sources` |
| `ingestion` | Pipeline input — scraper state, fetched pages, city list | `source_documents`, `locations`, `search_runs`, `search_results`, `search_locations` |
| `users` | Identity domain — credentials, profiles, preferences | `users`, `user_profiles`, `user_credential_history`, `user_preferred_locations` |
| `logs` | Append-only telemetry and audit data | `llm_calls`, `pipeline_tool_calls`, `processing_decisions` |

Cross-schema foreign keys are allowed (e.g. `events.event_sources.source_document_id → ingestion.source_documents.id`).

`search_locations` lives in `ingestion` because it drives the scraper.
User preferred locations *write into* `ingestion.search_locations`; they do not own it.

## Core Tables

## `ingestion.locations`

Stores tracked geographic areas.

Columns:

```text
id uuid primary key
name text
city text
state text
country text
lat numeric
lon numeric
radius_miles numeric
created_at timestamp
updated_at timestamp
````

Example:

```text
Greenville, SC
lat/lon center
radius 25 miles
```

## `ingestion.search_runs`

Tracks each scheduled or manual discovery run.

Columns:

```text
id uuid primary key
location_id uuid references locations(id)
run_type text
status text
started_at timestamp
finished_at timestamp
query_set_version text
notes text
created_at timestamp
```

Possible `run_type` values:

```text
manual_url
scheduled_daily
manual_search
backfill
```

Possible `status` values:

```text
running
completed
failed
partial
cancelled
```

## `ingestion.search_results`

Stores search result metadata before fetching pages.

Columns:

```text
id uuid primary key
search_run_id uuid references search_runs(id)
query text
rank integer
title text
url text
snippet text
search_provider text
created_at timestamp
```

## `ingestion.source_documents`

Stores fetched and normalized web page content.

Columns:

```text
id uuid primary key
url text
canonical_url text
domain text
title text
fetched_at timestamp
source_published_at timestamp null
visible_text text
visible_text_hash text
fetch_status text
http_status integer
content_type text
fetch_method text
error_message text
created_at timestamp
updated_at timestamp
```

Important indexes:

```text
unique index on visible_text_hash
index on canonical_url
index on domain
index on fetched_at
```

## `events.events`

Stores canonical event records.

Columns:

```text
id uuid primary key
business_name text
event_name text
event_type text
category text
event_date timestamp null
address text
city text
state text
country text
lat numeric null
lon numeric null
promotion_text text
notes text
status text
confidence_score numeric
created_at timestamp
updated_at timestamp
```

Possible `event_type` values:

```text
grand_opening
soft_opening
ribbon_cutting
reopening
anniversary
unknown
```

Possible `status` values:

```text
candidate
verified
rejected
needs_review
merged
expired
```

Important indexes:

```text
index on event_date
index on city, state
index on status
index on business_name
index on lat, lon
```

## `events.event_sources`

Many-to-many relationship between events and source documents.

Foreign keys span schemas: `event_id → events.events.id`, `source_document_id → ingestion.source_documents.id`.

Columns:

```text
id uuid primary key
event_id uuid references events(id)
source_document_id uuid references source_documents(id)
relationship_type text
created_at timestamp
```

Possible `relationship_type` values:

```text
primary_source
supporting_source
conflicting_source
rejected_source
```

## `events.event_claims`

Stores extracted atomic claims from source documents.

Columns:

```text
id uuid primary key
event_id uuid null references events(id)
source_document_id uuid references source_documents(id)
claim_type text
claim_value text
claim_text text
confidence_score numeric
created_at timestamp
```

Possible `claim_type` values:

```text
business_name
event_date
address
city
state
promotion
event_type
category
opening_status
```

Example:

```text
claim_type: event_date
claim_value: 2026-06-14
claim_text: "Join us for our grand opening on June 14..."
confidence_score: 0.91
```

## `logs.processing_decisions`

Stores important automated decisions.

Columns:

```text
id uuid primary key
source_document_id uuid null references source_documents(id)
event_id uuid null references events(id)
decision_type text
decision_value text
reason text
model_name text null
created_at timestamp
```

Example decisions:

```text
page_is_relevant = true
duplicate_source = false
possible_duplicate_event = true
rejected_reason = "Job posting, not public grand opening"
needs_followup_search = true
```

---

## `users.users`

Core identity and credentials for registered accounts.
Added in migration `0006_users`.

```text
id              uuid primary key (generated at registration time, used as password pepper)
email           text unique not null
username        text unique not null
password_hash   text not null        (bcrypt, peppered with user_id)
tier            text default 'basic'
role            text default 'user'  (user | admin | developer)
is_active       boolean default true
created_at      timestamp
updated_at      timestamp
```

## `users.user_profiles`

Optional display metadata. Separate from `users` so profile can be null until filled.

```text
id              uuid primary key
user_id         uuid references users(id) unique
first_name      text null
middle_initial  text null
last_name       text null
phone_number    text null
created_at      timestamp
updated_at      timestamp
```

## `users.user_credential_history`

Immutable audit log — rows are never updated or deleted.

```text
id              uuid primary key
user_id         uuid references users(id)
field_changed   text              (email | username | password)
old_value       text null         (password changes store hashes; plain text for email/username)
new_value       text null
changed_at      timestamp default now()
```

## `users.user_preferred_locations`

Cities a user wants to receive event notifications for.

```text
id              uuid primary key
user_id         uuid references users(id)
city            text not null
state           text not null     (2-letter US state code)
created_at      timestamp
```

Unique constraint: `(user_id, city, state)`.

When a new preferred location is added it is also upserted into `search_locations`.

## `ingestion.search_locations`

The canonical list of city/state pairs the scraper searches.
Seeded with `Greenville, SC` (`is_default = true`) on first migration.

```text
id              uuid primary key
city            text not null
state           text not null
is_default      boolean default false
user_count      integer default 0    (how many users have this as a preferred location)
created_at      timestamp
updated_at      timestamp
```

Unique constraint: `(city, state)`.

---

## `logs.llm_calls`

Records every OpenAI API call for cost tracking and debugging.

```text
id              uuid primary key
model           text
prompt_tokens   integer
completion_tokens integer
total_tokens    integer
latency_ms      integer
purpose         text              (classify | extract | conflict | followup)
event_id        uuid null references events.events(id)
source_document_id uuid null references ingestion.source_documents(id)
created_at      timestamp
```

## `logs.pipeline_tool_calls`

Telemetry for MCP tool invocations by the worker pipeline.

```text
id              uuid primary key
run_id          uuid null references ingestion.search_runs(id)
tool_name       text
input_summary   text
output_summary  text
duration_ms     integer
success         boolean
error_message   text null
created_at      timestamp
```