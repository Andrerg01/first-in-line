---
description: "Use when adding or editing MCP server tools, endpoints, or schemas. Enforces the narrow-tool rule and prohibits unsafe operations."
applyTo: "mcp_server/**/*.py"
---

Before adding or editing any MCP tool, read:
- .github/copilot-instructions.md (section: Security and Tooling Constraints)
- docs/standards/architecture_guardrails.md

Those files are the single source of truth for allowed tool categories, prohibited operations, and the frontend-cannot-call-MCP boundary rule.
