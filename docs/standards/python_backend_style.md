# Python Backend Style Standard

## Function Format

Each non-trivial function should include:
- type hints on parameters and return values
- a concise docstring describing purpose, args, returns, and raises where relevant
- clear argument names and predictable ordering

## Docstring Template

Use this style:

"""
Short summary sentence.

Args:
    arg_name: What this parameter means.

Returns:
    Description of return value.

Raises:
    ValueError: Condition that triggers it.
"""

## Error Handling

- Fail fast on invalid input.
- Raise explicit exceptions in service/repository layers.
- Return clean HTTP errors from router layer.
- Log contextual metadata for failures.

## Naming

- files/modules: snake_case
- classes: PascalCase
- functions/variables: snake_case
- constants: UPPER_SNAKE_CASE

## Dependency Rules

- No cross-layer shortcuts.
- Routers do not talk directly to raw DB when repository exists.
- Services should receive dependencies explicitly where practical.

## Main Entrypoint Rule

main.py should stay small and focused on app composition.

## Logging Standard

All modules use `worker.app.logger.get_logger` (worker) or the standard `logging.getLogger`
(backend). Never use `print()` for diagnostic output except deliberate user-facing CLI banners.

### Worker modules

```python
from worker.app.logger import get_logger

# Module-level fallback (no run context yet)
log = get_logger(__name__)

# Inside run_once(), after run_id is assigned
log = get_logger(__name__, run_id=run_id)
```

`RunLoggerAdapter` injects an 8-character `run_id` prefix into every log record so all lines
for a single pipeline run are trivially grep-able:

```
2025-01-15 12:00:01 INFO     [run:abcdef12] worker.app.pipeline Starting discovery run ...
```

### Log levels

| Level | When to use |
|-------|-------------|
| DEBUG | Per-URL decisions, raw MCP payloads, skip reasons |
| INFO  | Run start/end, per-query progress, document counts |
| WARNING | Rate-limit signals, flush failures, partial results |
| ERROR | Uncaught exceptions that abort a run or query |

### Quiet third-party loggers

`configure_logging()` suppresses `httpx`, `httpcore`, and `urllib3` to WARNING unless
the root level is DEBUG.

## Telemetry Standard

Every MCP tool call in the worker pipeline must be recorded via `TelemetryCollector`:

```python
t0 = collector.start_timer()
try:
    result = mcp_client.some_tool(...)
    collector.record(tool_name="tool.name", input_summary=..., outcome="success",
                     duration_ms=collector.elapsed_ms(t0))
except Exception as exc:
    collector.record(tool_name="tool.name", input_summary=...,
                     outcome=classify_outcome(exc), duration_ms=collector.elapsed_ms(t0),
                     error_message=str(exc))
    raise
```

All records are flushed in bulk at the end of the run via
`collector.flush(run_id, api_client.record_tool_calls)`. Flush failures are logged as
warnings and never abort the run. Records land in the `pipeline_tool_calls` table.

## Rate-limit Protection

The pipeline enforces a mandatory pause between consecutive search queries:

```python
QUERY_INTERVAL_SECONDS=2.0  # env var; set to 0 in tests
```

Set `QUERY_INTERVAL_SECONDS=0` in test environments. The MCP client also enforces an
8-second per-query timeout. When all retries time out, `mcp_client.search` logs a prominent
`RATE LIMIT WARNING` at the WARNING level before returning an empty result list.
