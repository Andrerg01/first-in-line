# Grand Opening Radar

Grand Opening Radar discovers nearby business grand openings and preserves source evidence, extracted claims, and canonical events.

## Phase 0 Status

This repository now includes:
- monorepo folders: frontend, backend, worker, mcp_server, shared, infra, docs
- docker-compose baseline
- FastAPI backend with health endpoint
- frontend placeholder page in Docker and React scaffold in source
- Postgres container
- MCP server skeleton with health and tools endpoint
- worker no-op CLI command
- environment template

## Local Run

1. Optionally copy .env.example to .env and adjust values.
2. Start containers:

   docker compose up --build

3. Verify services:
- backend health: http://localhost:8000/health
- frontend: http://localhost:5173
- mcp health: http://localhost:9000/health
- mcp tools: http://localhost:9000/tools

## Worker No-op Command

Run worker skeleton command locally:

python -m app.cli noop

From directory: worker

## Next Steps

1. Phase 1 database schema and migrations.
2. Event CRUD API endpoints.
3. Seed data and first frontend event list.
