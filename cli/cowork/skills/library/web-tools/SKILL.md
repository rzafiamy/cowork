---
name: web-tools
description: Scrape, crawl, and download web resources.
triggers:
  - scrape
  - crawl
  - download
  - url
  - website
trust_tier: 2
tool_categories:
  - WEB_TOOLS
permissions:
  categories:
    - WEB_TOOLS
  tools:
    - firecrawl_crawl
    - firecrawl_scrape
    - web_download_file
---
# Web Tools Skill

Purpose: Scrape, crawl, and download web resources.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
