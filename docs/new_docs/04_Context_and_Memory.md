# 4. Context and Memory

The Cowork Agent employs a multi-tiered approach to maintaining state, context, and long-term memory.

## Short-Term Context (Context Compressor)
When a conversation grows beyond the sliding window buffer (default 6,000 tokens), the Agent preserves factual integrity using Map-Reduce Compression.
* **Map Phase**: The conversation history is chunked and summarized by a highly deterministic model.
* **Reduce Phase**: These summaries are combined into a dense `[CONVERSATION SUMMARY]` block.
* The original, full-text context is automatically archived to the Scratchpad, making it retrievable if needed without taking up context window space.

## Long-Term Memory (Memoria)
Memoria provides the agent with "Personality" and "Past".
* **Triplet Extraction:** Facts are extracted as Subject-Predicate-Object triplets (e.g. `(User, prefers, Python)`).
* **Local Vector Search:** Embeds the triplets with `all-MiniLM-L6-v2` and searches via local SQLite (`sqlite-vec`).
* **Temporal Decay:** Memoria uses Exponential Weighted Average (EWA) decay. A memory's relevance score is the product of its semantic similarity and an exponential time decay factor.
* **Knowledge Consolidation:** When triplets exceed a configurable limit (`memory_kg_limit_triplets`, default 100), the system automatically triggers an LLM-led consolidation turn to merge redundant facts into more concise ones.

### Memoria Lifecycle Summary

| Component | Created | Updated | Primary Use | Retention / Deletion |
| :--- | :--- | :--- | :--- | :--- |
| **Knowledge Triplets** | User turn (Fact extraction) | **Consolidation** (Deduplication) | Persona personalization | Persistent / Global |
| **Session Summary** | First turn of session | After every turn | Rolling session continuity | Persistent per session |
| **Vector Index** | First triplet ingestion | After new fact extraction | Semantic memory retrieval | Persistent / Rebuilt for sync |
| **`memoria.db`** | App initialization | After every durable turn | Central storage (SQLite) | Persistent / Global |

## Scratchpad and Reference Management
The Scratchpad acts as a session-specific blob store. To maintain efficiency, the agent offloads large data and references it via `ref:key` pointers.

### Naming Conventions
The system uses automated naming patterns to categorize stored information:
*   `run_step_ledger`: A **rolling turn history**. Stores a JSON-serialized ledger of assessments for every step in the current REACT loop, providing Continuity for multi-step reasoning.
*   `_index.json`: The **Scratchpad Metadata Index**. A hidden file in the scratchpad directory that tracks all entries, sizes, and descriptions.
*   `task_goal`: The **canonical task anchor**. Injected at the start of multi-step turns to prevent context loss.
*   `mem_*`: "Meaningful" snapshots of important conversation turns, preserved for durability.
*   `last_assistant_response`: The exact text of the previous turn, useful for chaining tools (e.g., TTS).
*   `assistant_step_<timestamp>_<step>`: Incremental reasoning snapshots from the REACT loop.
*   `input_<uuid>`: Large user inputs offloaded prior to processing.
*   `conversation_<timestamp>`: Full-text source archived before Map-Reduce compression.
*   `tool_output_<hint>_<timestamp>`: Large tool responses ("sandwiched" in chat but full-text in scratchpad).

### Scratchpad Lifecycle Summary

| File Pattern | Created | Updated | Primary Use | Retention / Deletion |
| :--- | :--- | :--- | :--- | :--- |
| `_index.json` | First scratchpad write | Every scratchpad save | Discovery & prompt indexing | Persistent per session |
| `task_goal` | Start of multi-step task | After each refinement turn | Turn re-orientation (reads first) | Persistent / Manual update |
| `run_step_ledger` | After first tool execution | After every tool execution | Continuity & Step-by-step debug | Rolling (last 12 steps) |
| `last_assistant_response`| Every turn completion | N/A (Overwritten) | Tool chaining (e.g. TTS) | Overwritten every turn |
| `assistant_step_*` | During REACT loop (>400 chars) | N/A (Unique per step) | Reasoning continuity | Persistent per session |
| `mem_*` | Durable user turn detected | N/A (Unique per turn) | Personality & Preferences | Persistent / Long-term |
| `input_*` | Phase 1 (Gatekeeper) | N/A | Agent ingestion (Phases 2-3) | Persistent per session |
| `conversation_*` | Phase 4 (Compression) | N/A | Context window overflow recovery | Persistent per session |
| `tool_output_*` | Tool results > token limit | N/A | Granular data synthesis | Persistent per session |

### LLM Interaction Pattern
1.  **Awareness**: The LLM receives a `[Scratchpad Index]` in its system prompt containing all keys and descriptions.
2.  **Explicit Rules**: 
    - At the start of a follow-up turn, the agent MUST read `ref:task_goal` as its first action if it exists.
    - The agent is instructed to use `scratchpad_read_chunk` to retrieve raw data before synthesizing.
3.  **Discovery**: If a reference is mentioned but not fully understood, the agent uses `scratchpad_list` or `scratchpad_search` to find relevant context.
