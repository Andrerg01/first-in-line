# Cost Plan

## Goal

Keep the app alive at low cost while still demonstrating real cloud deployment skills.

## Recommended Setup

Use:

```text
One AKS cluster
Three namespaces:
  - grand-openings-dev
  - grand-openings-indus
  - grand-openings-prod

One Azure Database for PostgreSQL Flexible Server
Three databases or schemas:
  - grand_openings_dev
  - grand_openings_indus
  - grand_openings_prod

One Azure Container Registry
One Azure Key Vault
One domain
One DNS zone
Daily scraper CronJob
OpenAI nano/mini model strategy
````

## Expected Monthly Cost

Approximate:

```text
$100-$170/month
```

Lower-cost version:

```text
$25-$60/month
```

using mostly local development and only lightweight cloud services.

## Cost-Control Rules

1. Do not create three AKS clusters.
2. Do not create three separate Postgres servers unless needed.
3. Use one daily scraper run.
4. Limit number of pages processed by LLM.
5. Hash and skip duplicate source documents.
6. Use cheaper OpenAI models for classification/extraction.
7. Use stronger models only for conflict resolution.
8. Cap Azure Monitor logs.
9. Avoid SMS alerts until needed.
10. Avoid paid search APIs until the MVP works.

## LLM Cost Strategy

Use model routing:

```text
cheap model:
  relevance classification
  simple extraction

medium model:
  event extraction
  structured JSON repair

stronger model:
  conflict reasoning
  duplicate ambiguity
  follow-up query generation
```

## Daily Scraper Limits

Initial limits:

```text
locations: 1
queries per location: 5-10
search results per query: 10
max fetched pages per day: 100
max LLM-processed pages per day: 30-50
```

## Upgrade Triggers

Increase capacity only when:

```text
more users are active
more cities are added
scraper queue regularly hits limits
database grows enough to require tuning
notifications become important
```
