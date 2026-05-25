# First In Line - Agent Roles

This file defines project-specific execution roles for coding sessions and pull requests.

## Core Rule

All roles must follow:
- architecture boundaries in .github/copilot-instructions.md
- coding and testing standards in docs/standards/
- phase scope in docs/project_plan/09_phases.md

## 1) Feature Agent

Purpose:
- implement a new feature within current phase scope

Required workflow:
1. Confirm phase and acceptance criteria.
2. Propose module-level file changes.
3. Implement in small files by domain.
4. Add/adjust tests.
5. Update docs for changed behavior.

Outputs:
- implementation
- tests
- docs updates
- short verification summary

## 2) Bug Fix Agent

Purpose:
- reproduce and fix a defect with minimal regression risk

Required workflow:
1. Capture exact failing behavior.
2. Add failing test (when practical).
3. Apply minimal fix in correct layer.
4. Re-run relevant tests.
5. Document root cause and prevention note.

Outputs:
- bug fix
- regression test
- root cause note

## 3) Reviewer Agent

Purpose:
- perform code review with correctness and risk first

Required focus order:
1. correctness bugs
2. architecture boundary violations
3. security and data safety issues
4. missing tests
5. maintainability concerns

Outputs:
- severity-ranked findings with file references
- required fixes
- residual risks

## 4) Refactor Agent

Purpose:
- improve structure without behavior changes

Required workflow:
1. Define behavior invariants.
2. Refactor by module.
3. Keep commits or patches small and reversible.
4. Validate by tests and smoke checks.

Outputs:
- cleaner structure
- unchanged behavior proof via tests

## 5) Test Agent

Purpose:
- increase confidence with targeted, high-value tests

Required workflow:
1. Identify critical paths and boundaries.
2. Add unit tests first.
3. Add integration tests for DB/API boundaries.
4. Ensure failure messages are actionable.

Outputs:
- test coverage improvements
- command list to run tests

## 6) Docs Agent

Purpose:
- keep docs accurate and navigable

Required workflow:
1. Update docs in same PR as behavior changes.
2. Keep docs close to owning module.
3. Maintain index links in docs/standards/README.md.

Outputs:
- updated docs
- changed sections summary
