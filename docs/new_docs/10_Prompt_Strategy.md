# 10. Prompt Strategy & Engineering

This document outlines the prompting architecture and strategy used across the Cowork Agentic system. The system centralizes all prompts in `cli/cowork/prompts.py` to decouple instruction design from code logic, enabling prompt engineers to view, iterate, and version instructions safely.

## Core Philosophy

Cowork's prompting strategy relies on **Context over Explicit Rigidity**.
Rather than providing 1,000 lines of hardcoded edge-cases, the prompt framework relies on supplying the LLM with a highly structured state (temporal context, live memory context, explicit tool reflection logs) and trusts modern LLMs (like GPT-4o) to infer the right actions based on their capabilities.

**Key Principles:**
1. **Be Deterministic on Routing, Creative on Generation**: The Router operates with simple JSON parameters, while the Main Agent focuses on synthesis and reasoning.
2. **Fail Loudly (The HINT system)**: We do not hide tool errors from the LLM. If an error or gatekeeper collision occurs, the system injects a structured hint detailing how to recover (e.g., `[GATEWAY ERROR]: parameter start_line must be an integer`).
3. **Step Budget Awareness**: The agent is explicitly told via the prompt how to behave when hitting its loop limits, prioritizing honesty over hallucination.

---

## Centralized Registry (`prompts.py`)
All prompts are managed in `prompts.py`. They follow a strict naming convention:
*   `<DOMAIN>_SYSTEM_PROMPT` — Static system/persona definitions
*   `<DOMAIN>_USER_TEMPLATE` — User-turn templates containing `{placeholders}`
*   `<DOMAIN>_TEMPLATE` — Freeform multi-use templates

---

## 🏗️ 1. The Main Agent Prompts

### `AGENT_SYSTEM_PROMPT` (v2.1)
The core reasoning engine. It fuses the agent persona with its runtime identity.

**Structure:**
*   **Persona:** "Thoughtful coordinator who synthesizes information."
*   **Principles:** Context is currency, parallel execution > sequential, finish strong (don't loop endlessly).
*   **Step Budget Awareness (CRITICAL):** Explicit rules on handling limits. It dictates what the agent must output (e.g., `✅ GOAL ACHIEVED`) *only* when prompted by an active limit notice.
*   **Formatting Rules:** Enforces empty lines before/after tables and markdown code blocks to avoid UI rendering bugs.
*   **Tool Usage & Virtual IDE:** Gives hints on edge-case tools. For example, explicitly states to use the *Virtual IDE tools* (`scratchpad_fork`, `get_outline`, `edit_lines`, `append`) instead of rewriting the entire document linearly.
*   **Task Anchoring (Multi-Step):** Instructs the agent to read `ref:task_goal` as its very first action on multi-step follow-ups to maintain deep context.
*   **Dynamic Context Fusion:** Injects `{current_datetime}`, `{memory_context}`, `{session_id}`, and the `{scratchpad_index}` directly at the bottom of the system prompt.

### `AGENT_CHAT_SYSTEM_PROMPT` (v1.0)
A lightweight variant of the main prompt used when the `MetaRouter` classifies intent as `CONVERSATIONAL_ONLY`.
*   Strips away tool usage instructions and complex step-budgeting.
*   Retains the persona, memory context, and time awareness.
*   **Why?** Saves tokens, speeds up API calls, and forces the model to engage conversationally rather than attempting fake tool calls.

---

## 🧭 2. Meta-Routing & Intelligence

### `ROUTER_SYSTEM_TEMPLATE` (v2.0)
Used in the "Brain" phase (Zero-shot intent classification).
*   **Input:** The raw `user_input`.
*   **Output Strategy:** Forces the LLM to return strict JSON containing `"categories"` and a `"confidence"` score.
*   **Anti-Hallucination:** Explicitly provides `{category_list}` and commands the LLM to *only* output exact category IDs from that list.

---

## 🗜️ 3. Compression & Memory Management

### `COMPRESS_PROMPT` (v1.2)
Used by the Map-Reduce context compressor when the session exceeds the token limit.
*   **Instruction Focus:** Instructs the LLM to act as a "lossless compressor".
*   **Rule:** Preserve facts, tool results, numbers, and decisions while ripping out greetings, redundant text, and filler.
*   **Identifier:** Mandates that the output begins with `[CONVERSATION SUMMARY]`, which the downstream systems use to parse the compressed block.

### `TRIPLET_EXTRACTION_PROMPT` (v1.1)
The engine behind `Memoria` (Long-Term Memory).
*   **Goal:** Read a single user message and extract durable facts.
*   **Output:** Returns a JSON array of Subject-Predicate-Object triplets.
*   **Constraint:** Instructs the model to skip speculative or irrelevant statements and return an empty array if nothing factual is present.

### `SESSION_SUMMARY_PROMPT` (v1.0)
A rolling state maintainer.
*   **Input:** `{current_summary}` + `{user_message}` + `{assistant_response}`.
*   **Instruction Focus:** Instructs the LLM to *merge* the new interaction into the existing summary (under 200 words) rather than recalculating the entire history from scratch.

### `MEMORY_CONSOLIDATION_PROMPT` (v1.0)
Triggered when the triplet database exceeds the configurable limit (e.g. 100).
*   **Goal:** Deduplicate and consolidate the knowledge graph.
*   **Rules:** Outlines logical reductions (e.g., merging "John likes Python" and "John prefers Python coding" into a single edge).
*   **Constraint:** Prioritizes resolving contradictions optimally before serialization to JSON.

---

## 📘 Tuning and Versioning Practice

When updating prompts, Engineers should remember:
1. **Never hardcode APIs or Tool signatures in prompts.** The `registry.py` handles dynamic injection.
2. **Leverage the `[TOOL_REFLECTION]` block (Agent internals).** Don't try to prompt the LLM to infer tool statuses purely from metadata. The backend pre-processes tool outputs to provide clear `"ok"`, `"error"`, or `"partial"` findings directly into the message loop.
3. **Guardrails for the `Scratchpad`:** Always retain the hint letting the LLM know the `Scratchpad` exists, as LLMs naturally default to trying to inject massive blobs of text directly into the chat unless instructed otherwise.
