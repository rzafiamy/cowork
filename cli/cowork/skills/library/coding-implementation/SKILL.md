---
name: coding-implementation
description: Use this for codebase tasks that require inspecting files, planning targeted edits, implementing changes, and validating with local tests.
triggers:
  - implement
  - fix bug
  - refactor
  - add test
  - patch
trust_tier: 3
tool_categories:
  - CODING_TOOLS
  - WORKSPACE_TOOLS
permissions:
  categories:
    - CODING_TOOLS
    - WORKSPACE_TOOLS
---
# Coding Implementation Skill

Goal: complete coding requests with small, verifiable edits and clear validation.

Workflow:
1. Discover impacted files first (`codebase_list_files`, `codebase_search_text`, `codebase_read_file`).
2. Make minimal edits that solve the user request with no unrelated refactors.
3. Validate using focused checks (tests/lint for touched area) before finalizing.
4. Report exactly what changed and any limits in verification.

Guardrails:
- Prefer read operations before write operations.
- Avoid destructive operations unless the user explicitly asks.
- Keep architecture changes incremental.
