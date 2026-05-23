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
