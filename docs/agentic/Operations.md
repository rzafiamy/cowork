# 🛡️ Operations & Robustness

This document details the operational safeguards that ensure the Makix Agentic System is stable, persistent, and secure.

---

## 🚦 The Sentinel: Background Job Queue
The `AgentJobManager.js` handles concurrency and protects the session lifecycle.

### 💾 Persistence & Recovery
The system is built to be **"Refresh-Proof"**:
*   **🔄 State Sync**: Metadata for every job is saved in real-time to `localStorage`.
*   **🛠️ Reconstruction**: On startup, the system detects "Ghost Jobs" from previous sessions.
*   **🔔 Restoration Prompt**: Users can "Resume" interrupted tasks with full context recovery.

### 🛑 Concurrency Clamps
*   **Global Limit**: **10 active jobs** maximum across the platform.
*   **Session Lock**: Prevents race conditions by ensuring one session doesn't spawn duplicate logic loops.

### ⏱️ The Interaction Cooldown (Cron Safety)
To prevent the background cleanup (`CronService.js`) from interfering with active work:
*   **15-Minute Pause**: Any user interaction (click, keypress) or agent activity (`app-activity`) triggers a **15-minute global cooldown**.
*   **Zero-Conflict Execution**: Hygiene jobs (like session cleanup) are completely disabled during this period.
*   **Cross-Tab Sync**: The cooldown state is synchronized via `localStorage` ('cron_pause_until'), ensuring that a cleanup started in an idle tab doesn't delete a session being used in an active tab.

---

## 🚧 Technical Robustness: Execution Gateways
Before a tool is triggered, it must pass through the **Safety Middleware**.

### 1️⃣ Schema Enforcement
Every tool-call argument is validated against the defined JSON schema.
- ✅ Correct Types (String, Number, Array).
- ✅ Required Fields.
- ❌ **Fail-Fast**: Returns `[GATEWAY ERROR]` to the agent if malformed.

### 2️⃣ Safety Clamps (Anti-Hallucination)
Limits the "blast radius" of AI errors by enforcing strict string length limits for metadata:
*   🔑 **IDs / Keys**: Max **150** chars.
*   🏷️ **Titles / Names**: Max **500** chars.
*   *(Prevents agents from dumping giant text bodies into narrow database fields).*

### 🔗 Reference Resolution
The Gateway detects `ref:key` patterns in arguments.
*   **Action**: Recursively resolves them from the **Scratchpad**.
*   **Context Isolation**: Raw data is injected *only* for the tool execution, keeping it out of the potentially expensive chat history.

---

## 📊 Operational Settings Matrix
These values map from the **`profiles`** database table to specific system behaviors:

| ⚙️ UI Setting | 💾 DB Field | 🎯 Purpose |
| :--- | :--- | :--- |
| **Input Gatekeeper** | `op_user_input_limit_tokens` | **Input Guard**: Scratchpad threshold. |
| **Context Buffer** | `op_context_limit_tokens` | **History Guard**: Map-Reduce threshold. |
| **Tool Compression** | `op_tool_output_limit_tokens` | **Output Guard**: Tool result clamping. |
| **Max Iterations** | `op_max_steps` | **Step Guard**: REACT loop limit. |
| **Tools per Step** | `op_max_tool_calls_per_step` | **Concurrency Guard**: Max tools per single turn. |
| **Global Tool Limit** | `op_max_total_tool_calls` | **Budget Guard**: Max total tools per request. |
| **Idle Threshold** | `op_idle_threshold_seconds` | **Lifecycle**: Auto-session cleanup. |

---

## 🆘 Failure Propagation (Half-Halt Protocol)
The system ensures failures are handled gracefully through an observer-pattern approach, allowing the agent to "fail-forward".

### 🏷️ Error Classification
Errors are decorated with specific prefixes to help the LLM categorize the failure:
*   **`[GATEWAY ERROR]`**: Schema validation or reference resolution failures. Usually indicates the agent can self-correct by fixing tool arguments.
*   **`[TOOL ERROR]`**: Execution-level failures (e.g., API timeouts, external service 404s). Requires alternative pathways or user clarification.

### 💡 Intelligence Strategy: Actionable Hints
Every system-generated error returned to the agent includes a **`[HINT]`** tag. This ensures the LLM doesn't just "read" the error but understands the immediate logical next step (e.g., "Enclose value in quotes", "Check if data was saved to scratchpad").

### 🔍 Error & Hint Lookup Table
The following table maps common failure scenarios to the specific hints given to the AI Agent:

| 🚨 Error Scenario | 🏷️ Prefix | 💡 Actionable Hint |
| :--- | :--- | :--- |
| **Missing Parameter** | `[GATEWAY ERROR]` | `[HINT]: This field is mandatory.` |
| **Type Mismatch (String)** | `[GATEWAY ERROR]` | `[HINT]: Enclose the value in quotes.` |
| **Type Mismatch (Array)** | `[GATEWAY ERROR]` | `[HINT]: Use [item1, item2] format.` |
| **Reference Missing** | `[GATEWAY ERROR]` | `[HINT]: Save data to scratchpad first or check if you used the correct 'ref:key'.` |
| **Tool Not Found** | `[GATEWAY ERROR]` | `[HINT]: Verify the tool name or check if the required category was requested during meta-routing.` |
| **Execution Failure** | `[TOOL ERROR]` | `[HINT]: Check if parameters are correct or try an alternative tool.` |
| **Undefined Tool** | `[TOOL ERROR]` | `[HINT]: Use only tools available in your schema.` |

### 🧘 Agent Decision Matrix
As defined in the `Agent System Prompt`, the AI follows a 4-path recovery strategy:
1.  🔄 **Self-Correct**: Fix malformed JSON/Arguments and retry immediately.
2.  🛣️ **Pivot**: If a tool is unavailable, switch to a fallback tool (e.g., `web_search` -> `wiki_get`).
3.  👤 **Request Help**: If a reference (`ref:key`) is missing, ask the user to provide the context.
4.  🩹 **Graceful Exit**: If the failure is persistent, admit it honestly and summarize what *was* found.
