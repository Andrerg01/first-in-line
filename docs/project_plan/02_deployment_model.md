# Deployment Model

## Local Development

Use Docker Compose.

Services:

```text
postgres
backend-api
frontend
mcp-server
ingestion-worker
````

The worker can be run manually during early development.

Example local flow:

```text
docker compose up postgres backend-api frontend mcp-server

python -m worker.run_manual_url --url "https://example.com/grand-opening"
python -m worker.run_once --location "Greenville, SC"
```

## Kubernetes Development

Use one namespace for each environment:

```text
grand-openings-dev
grand-openings-indus
grand-openings-prod
```

These namespaces can live in one AKS cluster.

Important: frontend and backend pods are not 1:1.

Kubernetes service routing should look like this:

```text
frontend pods
  -> backend-api Service
      -> backend-api pods
```

The frontend should use either:

```text
/api/events
```

through ingress routing, or an environment-specific API URL.

Preferred ingress pattern:

```text
https://grandopeningradar.com/
  -> frontend service

https://grandopeningradar.com/api/*
  -> backend-api service
```

## Dev Namespace

```text
namespace: grand-openings-dev

Deployments:
  frontend
  backend-api
  mcp-server

CronJobs:
  ingestion-worker-daily

Optional StatefulSets:
  postgres-dev
```

## Indus Namespace

Indus is a staging/pre-production environment.

```text
namespace: grand-openings-indus

Deployments:
  frontend
  backend-api
  mcp-server

CronJobs:
  ingestion-worker-daily
```

Uses either:

* same managed Postgres server with separate database/schema, or
* separate Postgres server if stricter isolation is desired.

## Prod Namespace

```text
namespace: grand-openings-prod

Deployments:
  frontend
  backend-api
  mcp-server

CronJobs:
  ingestion-worker-daily
```

Uses managed Azure Database for PostgreSQL.

## Recommended Azure Setup

For cost control:

```text
One AKS cluster
  - dev namespace
  - indus namespace
  - prod namespace

One Azure Database for PostgreSQL Flexible Server
  - grand_openings_dev
  - grand_openings_indus
  - grand_openings_prod

One Azure Container Registry
One Azure Key Vault
One DNS zone
One domain
```

Do not create three AKS clusters unless isolation is more important than cost.

## Expected Low-Usage Cost

Estimated monthly cost:

```text
Local-mostly development:
  $25-$60/month

One AKS cluster with three namespaces:
  $100-$170/month

Three fully isolated cloud environments:
  $250-$600+/month
```

## Environment Variables

Each service should receive environment-specific config.

Common variables:

```text
APP_ENV
DATABASE_URL
OPENAI_API_KEY
MCP_SERVER_URL
LOG_LEVEL
ALLOWED_ORIGINS
GEOCODING_PROVIDER
SEARCH_PROVIDER
```

Worker-specific variables:

```text
SCRAPER_TARGET_LOCATION
SCRAPER_MAX_RESULTS_PER_QUERY
SCRAPER_DAILY_PAGE_LIMIT
SCRAPER_LLM_PAGE_LIMIT
SCRAPER_RATE_LIMIT_SECONDS
```

Frontend-specific variables:

```text
VITE_API_BASE_URL
```

If using same-domain ingress, frontend can call `/api` and may not need a full backend URL.