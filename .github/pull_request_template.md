## Summary

Describe what changed and why.

## Git Workflow Checklist

- [ ] Branch named correctly (`feat/`, `fix/`, `refactor/`, `docs/`, or `test/`)
- [ ] PR targets `develop`, not `main`
- [ ] `VERSION` file bumped (PATCH / MINOR / MAJOR — delete inapplicable)

## Architecture Checklist

- [ ] Boundary rules respected (frontend -> backend only, bounded MCP, etc.)
- [ ] No monolithic file growth without justification
- [ ] New logic placed in correct layer (router/service/repository/schema)

## Testing Checklist

- [ ] Unit tests added or updated
- [ ] Integration tests added or updated when relevant
- [ ] Connection/path error cases covered

## Documentation Checklist

- [ ] README or feature docs updated
- [ ] docs/standards references still accurate

## Cleanup Checklist

- [ ] Temporary files removed
- [ ] Debug code removed
