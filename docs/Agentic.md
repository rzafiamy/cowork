# 🤖 Makix Agentic Documentation Hub

Welcome to the **Architectural Nerve Center** for the Makix Enterprise Agentic System. This documentation is designed for high-concurrency, long-context AI orchestration.

---

## 🏗️ System Overview
*Understand the "Manager-Worker" architecture and global strategy.*
- 🟦 **[Core Architecture & Overview](./agentic/Overview.md)**: Intro, Global Diagrams, and System Pillars.

---

## 🔄 Detailed Strategic Domains
*Dive into specific technical implementations and strategies.*

### 1️⃣ [Request Lifecycle & Workflow](./agentic/Workflow.md)
> *From input gatekeeping to final UI rendering.*
- 📡 **Phase-by-phase breakdown** of message lifecycle.
- 📉 **Sequence diagrams** for logic flow.
- ⏱️ **Live telemetry** and status feedback mechanisms.

### 2️⃣ [Memory & Context Strategy](./agentic/Memory.md)
> *Managing "Infinite" windows and massive data payloads.*
- 📝 **The Scratchpad**: Pass-by-Reference memory system.
- 🖇️ **Compression**: Recursive Map-Reduce summarization.
- 🥪 **Sandwich Previews**: Fast non-LLM text reduction.

### 3️⃣ [Intelligence & Reasoning](./agentic/Intelligence.md)
> *Maximizing efficiency, accuracy, and task-aware logic.*
- 🧠 **Meta-Router**: Dynamic tool schema loading via intent classification.
- 🌡️ **Temperature Tiers**: Precision-targeted execution logic.
- ⚡ **Action Mode**: High-priority specialized workflow bypass.

### 4️⃣ [Operations & Robustness](./agentic/Operations.md)
> *Persistence, safety, and operational boundaries.*
- 🛡️ **The Sentinel**: Persistent Job Queue and restoration logic.
- 🚧 **Execution Gateways**: Schema validation and safety clamps.
- 📊 **Operational Mapping**: System-wide limits and settings matrix.

---

## 🛠️ Developer Quick-Check
- [ ] **Modifying Tools?** 🛠️ Update schema in `BaseTools` and category in `Router.js`.
- [ ] **Updating Prompting?** 🗣️ Review "Manager" persona rules in `Overview.md`.
- [ ] **Changing Limits?** ⚙️ Reflect changes in the `Operations.md` mapping table.

---
*Generated with ❤️ for AI Architects.*
