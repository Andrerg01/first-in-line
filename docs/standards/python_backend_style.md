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
