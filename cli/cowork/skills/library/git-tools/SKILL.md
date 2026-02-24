---
name: git-tools
description: Run git repository operations and status checks.
triggers:
  - git
  - commit
  - clone
  - push
  - status
trust_tier: 4
tool_categories:
  - GIT_TOOLS
permissions:
  categories:
    - GIT_TOOLS
  tools:
    - git_clone
    - git_commit
    - git_init
    - git_push
    - git_status
---
# Git Tools Skill

Purpose: Run git repository operations and status checks.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
