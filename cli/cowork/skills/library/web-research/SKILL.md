---
name: web-research
description: Use this for time-sensitive web lookup tasks requiring search, source comparison, and concise synthesis with links.
triggers:
  - latest
  - news
  - today
  - look it up
  - compare sources
trust_tier: 2
tool_categories:
  - SEARCH_TOOLS
  - WEB_TOOLS
  - NEWS_TOOLS
permissions:
  categories:
    - SEARCH_TOOLS
    - WEB_TOOLS
    - NEWS_TOOLS
---
# Web Research Skill

Goal: produce accurate, source-backed answers for time-sensitive questions.

Workflow:
1. Run focused searches with date constraints when possible.
2. Compare at least two independent sources for important claims.
3. Extract concrete facts: dates, names, numbers, and direct links.
4. Highlight uncertainty when sources disagree.

When deep domain policy is needed, load:
- LOAD_REF(references/source_quality.md)
