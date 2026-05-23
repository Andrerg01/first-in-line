# Grand Opening Radar — Project Overview

## Purpose

Grand Opening Radar is a portfolio and learning application that discovers nearby business grand openings, especially restaurants, cafes, food trucks, breweries, and retail openings.

The app periodically searches public web sources, fetches relevant pages, extracts structured event information using LLMs, stores candidate events in Postgres, and displays them in a web UI with map and calendar views.

## Primary Goals

1. Build a real-world LLM application with clear deterministic and intelligent layers.
2. Use OpenAI models for extraction, classification, conflict handling, and candidate event reasoning.
3. Use LangGraph for workflow orchestration.
4. Use MCP as a reusable tool layer.
5. Use Postgres as the system of record.
6. Deploy with a cloud-native architecture using Azure and Kubernetes.
7. Keep cost low enough for a portfolio project with minimal users.

## Core User Flow

1. User opens the app.
2. User sees upcoming grand openings near selected locations.
3. User can browse events by:
   - Map
   - Calendar
   - List
   - Category
   - Distance
   - Confidence/status
4. User can inspect the source evidence for each event.
5. Admin user can verify, reject, or merge candidate events.
6. Later: users can subscribe to email/SMS alerts.

## Initial Target Location

Greenville, South Carolina.

## Technology Choices

| Layer | Choice |
|---|---|
| Frontend | React |
| Backend API | Python FastAPI |
| Database | Postgres |
| Workflow orchestration | LangGraph |
| Tool interface | MCP |
| LLM provider | OpenAI |
| Cloud platform | Azure |
| Container orchestration | Kubernetes / AKS |
| Local development | Docker Compose |
| CI/CD | GitHub Actions or GitLab CI |

## High-Level Architecture

```text
React Frontend
  -> FastAPI Backend
      -> Postgres
      -> OpenAI API
      -> MCP Client
          -> MCP Server
              -> Web tools
              -> Geocoding tools
              -> Safe database tools
              -> Notification tools

Scheduled Ingestion Worker
  -> LangGraph
      -> Deterministic search/fetch/hash pipeline
      -> OpenAI extraction/classification/conflict handling
      -> MCP tools
      -> Postgres
````

## Core Design Principle

Raw pages are sources.
Extracted facts are claims.
Canonical events are curated records.

The app should not blindly trust one LLM output as final truth. It should preserve source evidence, extracted claims, and the current best canonical event record separately.

## Initial MVP

The first MVP should support manual URL ingestion before automated scraping.

MVP flow:

```text
Paste URL
  -> fetch page
  -> extract visible text
  -> hash normalized text
  -> run LLM extraction
  -> show candidate event and evidence
  -> approve/reject candidate
  -> display event on list/map/calendar
```

## Later MVP+

After manual ingestion works:

```text
Daily scheduled run
  -> search web for target queries
  -> fetch top N pages
  -> hash and skip duplicates
  -> extract candidate events
  -> compare to existing events
  -> save candidates for review
```
