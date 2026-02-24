# 3. Meta-Routing

The Cowork Agent uses a two-stage "Brain" phase:
1. **Meta-Router** (`router.py`) for category intent classification at Temperature 0.0.
2. **Skill Runtime** (`skills/runtime.py`) for progressive `SKILL.md` activation and trust-gated tool filtering.

## Workflow

1. The user inputs a prompt.
2. The router reads the prompt, bypassing routing entirely via a Fast-Path for small, explicitly conversational prompts (labeled `CONVERSATIONAL_ONLY`).
3. For more complex prompts, the router invokes an LLM to select from 20+ specific categories (e.g. `WEB_TOOLS`, `CODING_TOOLS`, `DATA_AND_UTILITY`).
4. **Fallback Mechanism**: If the router model fails (e.g. due to an API timeout or bad JSON), the router automatically backs off to a keyword-based heuristic.
5. **Skill Activation**: The runtime picks the best-matching skill using lexical overlap, trigger matches, and routed category alignment.
6. **Trust & Permission Enforcement**: Skill instructions/resources are loaded only when trust gates pass; tools are then filtered by trust tier and skill manifest permissions.

## Categories Overview

Some popular categories include:
* `SEARCH_TOOLS`: Web research (Google/Brave Search)
* `WEB_TOOLS`: Scrape/read a URL (Firecrawl)
* `CODING_TOOLS`: Full purpose tool for python/dev tasks (`codebase_list_files`, `github_search`, etc.)
* `MULTIMODAL_TOOLS`: Vision, Image Generation (DALL-E), STT/TTS
* `SESSION_SCRATCHPAD`: Reading and writing large text blobs safely.
* `WORKSPACE_TOOLS`: Read/write files to the session workspace for human visibility.

## Dynamic Tool Injection
To prevent tools from breaking or loading improperly, the router checks the currently available API keys. If the user does not have a given API key configured, the tool will not even load into the schema. For example, if `OPENWEATHERMAP_API_KEY` is completely missing, the `WEATHER_TOOLS` category may be omitted or simply yield no tools if selected.

## Skill Progressive Disclosure
Skill loading is intentionally staged to reduce prompt bloat:
* **Level 1 (always on):** Inject metadata TOC only (`[SKILL LIBRARY METADATA]`).
* **Level 2 (on activation):** Inject active skill instructions (`[ACTIVE SKILL]` / `[SKILL INSTRUCTIONS]`).
* **Level 3 (explicit only):** Load referenced resource files only when `LOAD_REF(...)` appears in the skill body.

If a skill blocks all tools by mistake, the runtime falls back to the routed tool schema to prevent execution dead-ends.
