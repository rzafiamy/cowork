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

## Workspace Sessions
Cowork saves sessions to the file system at `~/.cowork/workspace/<slug>/` making the entire session human-readable, inspectable, and editable.

Each session folder contains:
* `session.json`: Conversation messages and metadata.
* `context.md`: Free-form notes that both you and the agent can read and write to.
* `scratchpad/`: Large data blobs and task anchors.
* `notes/`: Structured markdown notes requested by the user.
* `artifacts/`: Files, PDFs, scripts, and other generated material.

Because the system relies on the file system, you can use traditional terminal tools or your code editor to search, grep, or edit the memory state directly.
