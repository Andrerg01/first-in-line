# Testing Strategy

## Priority

1. Unit tests for service logic
2. Unit tests for repository query logic (where practical)
3. API integration tests for critical endpoints
4. End-to-end smoke tests for compose startup and health

## Required Test Cases Per Feature

At minimum:
- happy path
- invalid input path
- one boundary/error path

## DB and Connection Testing

Required checks:
- database connection succeeds with configured URL
- failed connection produces actionable error
- schema migration path is testable

## Regression Policy

Any bug fix should add a regression test when practical.

## Test Organization

Use directory structure:

tests/
- unit/
- integration/
- e2e/

## Execution Policy

- Run affected tests before completion.
- If tests cannot run, document why and what remains unverified.
