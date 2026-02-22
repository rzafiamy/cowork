# 2. Agent and Reasoning

The core loop of the Cowork Agent is the REACT execution cycle, managed by `agent.py` and directed by text definitions in `prompts.py`.

## Phases

Every agent run goes through five strict phases:
1. **Input Gatekeeper**: Checks token counts. Huge inputs are automatically saved to the session scratchpad, injecting a smaller `ref:key` to the model.
2. **Meta-Routing (The Brain)**: Triage step at Temp 0.0 to decide what capabilities (Tool Categories) the task actually requires.
3. **REACT Loop (The Worker)**: Repeated Reason $\rightarrow$ Act cycle using Temp 0.4.
4. **Context Compression**: Map-Reduce summarization when the context gets too big.
5. **Memory Ingestion**: Extraction of long-term facts for personalized response later.

## REACT Loop Details

* Uses the Manager-Worker pattern.
* Implements a **Step Budget** (default 15 steps).
* The agent can execute tools in parallel if they are independent.
* **Self Assessment**: If the agent reaches the step limit, a system notice forces it to self-assess and halt. It will reply exactly with `✅ GOAL ACHIEVED`, `⚠️ GOAL PARTIALLY ACHIEVED`, or `❌ GOAL NOT ACHIEVED`.

## Multi-Step Task Anchoring

Cowork handles iterative, complex goals (like writing this documentation, generating presentations, etc.) via **Task Anchoring**:
1. It writes a structured goal block into the scratchpad under `task_goal`.
2. This goal includes: Goal, Scope, Current State, Next Steps, and User Preferences.
3. On follow-up interaction, the agent immediately reads this to re-orient itself, preventing context-loss over long chat histories.

## Context Compression (Map-Reduce)

When the session memory grows past `context_limit_tokens` (default: 6000), Cowork compress the history to avoid API chokes and high latency.
* Running at Temperature 0.1, the `ContextCompressor` chunks text semantically.
* Preserves system prompts and the latest 2 user turns.
* Creates `[CONVERSATION SUMMARY]` which includes references to the original data in the scratchpad.
