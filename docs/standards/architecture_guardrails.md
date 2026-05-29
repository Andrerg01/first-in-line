# Architecture Guardrails

## Non-Negotiable Boundaries

1. Frontend calls backend API only.
2. Frontend never calls MCP directly.
3. MCP provides bounded tools only.
4. LangGraph owns orchestration.
5. Postgres is source of truth.

## Module Size and Structure Rules

- Avoid monolithic files.
- Soft limit: 300 lines per feature module.
- Hard warning threshold: 500 lines; split required unless justified.
- Keep one clear responsibility per module.

## Backend Layout Rules

Target layout:

backend/app/
- main.py (bootstrap only)
- config.py
- db.py
- routers/
- services/
- repositories/
- schemas/
- models/

Rules:
- main.py wires app, routers, and startup only.
- routers contain HTTP concerns only.
- services contain business logic only.
- repositories contain persistence access only.
- schemas define request/response contracts.

## Change Isolation Rules

For each feature:
- add or update router in routers/
- add or update service in services/
- add or update repository in repositories/
- add or update schema and tests
- update docs in docs/

## Temporary File Policy

- Temporary scripts and debug files are allowed only for active debugging.
- Remove temporary artifacts before completion.
- Never commit scratch files unless intentionally documented tooling.

## Database Schema Convention

The `public` schema is left empty. All tables belong to one of four named schemas:

| Schema | What lives here |
|--------|----------------|
| `events` | `events`, `event_claims`, `event_sources` |
| `ingestion` | `source_documents`, `locations`, `search_runs`, `search_results`, `search_locations` |
| `users` | `users`, `user_profiles`, `user_credential_history`, `user_preferred_locations` |
| `logs` | `llm_calls`, `pipeline_tool_calls`, `processing_decisions` |

Rules:
- Every new ORM model must declare `__table_args__ = {"schema": "<schema>"}`.
- Alembic migrations must include `schema=` on every `op.create_table()` call.
- Cross-schema FKs must use the fully-qualified form: `schema.table.column`.
- `search_path` for application connections: `events, ingestion, users, logs, public`.
- See `docs/project_plan/03_database_plan.md` for full table definitions.
