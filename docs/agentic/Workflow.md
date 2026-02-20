# 🔄 Request Lifecycle & Workflow

This document traces the path of a user request from the moment it leaves the keyboard to final visual rendering.

---

## 🟢 Phase 1: User Input & UI Layer
*Components: `cli/cowork/main.py` ⮕ `cli/cowork/ui.py`*

1.  **⌨️ User Interaction**: Input is captured in the terminal interface.
2.  **🧩 Pill Detection**: Checks for "Action Pills" (user workflows).
3.  **🏷️ Tagging**: Processes inline hashtags (e.g., `#research`).
4.  **⏱️ Timer Init**: A high-precision elapsed timer appears in the UI.

## 🟡 Phase 2: Session & Job Management
*Components: `cli/cowork/main.py` ⮕ `cli/cowork/config.py` (`JobManager`)*

1.  **🛡️ Input Gatekeeper**:
    *   Estimates tokens.
    *   If payload is too large ⮕ 📝 **Offloads to Scratchpad** and injects a `ref:key`.
2.  **🚦 Job Registration**: 
    *   Enforces 10-job concurrency limit.
    *   💾 **Syncs to localStorage** for crash survival.

## 🔵 Phase 3: The Brain (Meta-Routing)
*Components: `cli/cowork/agent.py` ⮕ `cli/cowork/router.py`*

1.  **⚡ Fast-Path Detection**: Short conceptual turns can skip full router and route directly to `CONVERSATIONAL_ONLY`.
2.  **🧭 Intent Discovery**: If not fast-pathed, run lightweight classification at **Temp 0.0**.
3.  **🛠️ Schema Pruning**:
    *   `CONVERSATIONAL_ONLY` ⮕ no tool schema construction.
    *   Tool-capable turns ⮕ filter to relevant categories.
4.  **🎚️ Router Calibration**:
    *   A tool-need probability score can downgrade a broad route to `CONVERSATIONAL_ONLY`.
    *   📉 Reduces unnecessary orchestration and latency.

## 🟣 Phase 4: The Worker (REACT Loop)
*Components: `cli/cowork/agent.py` (`GeneralPurposeAgent` + `ContextCompressor`)*

1.  **🧩 Prompt Split**:
    *   `AGENT_CHAT_SYSTEM_PROMPT` for conversational-only turns.
    *   `AGENT_SYSTEM_PROMPT` for workflow/tool turns.
2.  **🤔 Reasoning**: Agent analyzes context and formulates a plan.
3.  **🖇️ Context Tuning**:
    *   Triggers **Atomic Compression** on giant messages.
    *   Inlines conversation summaries if the window is cramped.
4.  **⚙️ Multi-Action**: Executes tools (Parallelized when possible).
5.  **🥪 Output Guard**: Large tool results are "Sandwiched" before returning to the loop.

## 🟠 Phase 5: Rendering & Finalization
*Components: `cli/cowork/ui.py` ⮕ `cli/cowork/api_client.py` ⮕ `cli/cowork/config.py` (`Session`)*

1.  **📡 Streaming**: Incremental markdown rendering with syntax highlighting.
2.  **🎨 Multimodal Display**:
    *   🖼️ **Images**: Lightbox support.
    *   📊 **Charts**: Live Chart.js visualization.
3.  **🕵️ Trace Viewer**: 
    *   **On-Demand Loading**: Large `agent_trace` payloads are excluded from session load and fetched only when "Trace" is clicked.
4.  **⚡ Non-Blocking Exit**:
    *   **Memory Ingestion**: `Memoria.update()` is called only for durable user turns.
    *   **DB Persistence**: Message saving and title generation are backgrounded, allowing the UI to stay responsive.

### 🚨 Step-Limit Status Contract
- `✅ GOAL ACHIEVED` / `⚠️ GOAL PARTIALLY ACHIEVED` / `❌ GOAL NOT ACHIEVED` banners are used **only** for step-limit self-assessment turns.
- Normal conversational/tool turns should return direct answers without the banner.

---

## 📉 Workflow Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant User as 👤 User
    participant CM as 📑 ChatManager
    participant JobMgr as 🚦 Agent Job Queue
    participant Agent as 🤖 General Agent
    participant Comp as 🖇️ Context Comp
    participant Router as 🧭 Meta-Router
    participant API as 📡 API Client
    participant UI as 💻 Chat UI

    User->>CM: Sends message
    
    CM->>CM: 🛡️ Gatekeeper check
    alt Input > Limit
        CM->>CM: 📝 Offload to Scratchpad
    end
    
    CM->>JobMgr: 🚦 startJob()
    JobMgr->>JobMgr: 💾 Persist job state (jobs.json)
    
    JobMgr->>Agent: 🏃 run()
    
    alt Action Mode
        Agent->>Agent: ⚡ Inject Strict Intent
    else Fast Conversational Path
        Agent->>Agent: 💭 Route = CONVERSATIONAL_ONLY
        Agent->>Agent: 🧩 Use Chat Prompt + No Tools Schema
    else Standard Mode
        Agent->>Router: 🧭 _classifyRequest (T=0.0 + tool probability)
        Router-->>Agent: 🛠️ Relevant Tools
    end
    
    loop REACT Loop
        Agent->>Comp: 🖇️ optimizeContext()
        alt Buffer low
            Comp->>API: 📉 Map-Reduce (T=0.1)
            API-->>Comp: Summary
        end
        
        Agent->>API: 📡 sendMessageStream (T=0.4)
        activate API
        loop Streaming
            API-->>UI: 🌊 onChunk()
        end
        API-->>Agent: Result
        deactivate API
        
        alt Tool Use
            Agent->>Agent: ⚙️ Execute Tools
            alt Output Large
                Agent->>Comp: 🥪 sandwichPreview()
            end
        end
    end
    
    Agent-->>JobMgr: ✅ Job Complete
    JobMgr->>CM: onComplete(result)
    CM->>UI: 🔔 Render Final Response
    
    Note over CM,Agent: 🚀 Background Persistence Phase
    par Background Tasks
        CM->>CM: 💾 addMessage(trace, answer)
        CM->>CM: 📝 autoGenerateTitleIfUnnamed()
        alt Durable user message
            Agent->>Agent: 🧠 memory.update()
        else Non-durable one-off turn
            Agent->>Agent: ⏭️ Skip memory update
        end
    end
```

---

## 📡 Live Telemetry Feedback
The Agent provides real-time "Thought Stream" updates to the user:
*   **Step 1**: "Analyzing request & architecting strategy..."
*   **Step 2**: "Routing intent to [Category] tools..."
*   **Step 3**: "Interrogating [External Source]..."
*   **Step 4**: "Synthesizing final intelligence..."
