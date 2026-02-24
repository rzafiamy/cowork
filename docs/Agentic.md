# 🤖 Makix Agentic Documentation Hub

Welcome to the architectural index for the Cowork runtime.

---

## 🏗️ System Overview
- 🟦 **[Core Architecture & Overview](./agentic/Overview.md)**: High-level runtime diagram and design pillars.

---

## 🔄 Strategic Domains

### 1️⃣ [Request Lifecycle & Workflow](./agentic/Workflow.md)
- End-to-end phase flow from input gatekeeper to final response.
- Updated sequence diagrams including **Skill Runtime activation** and memory write gates.

### 2️⃣ [Memory & Context Strategy](./agentic/Memory.md)
- Scratchpad pass-by-reference pattern (`ref:key`).
- Context compression and large-output offloading.
- Memoria relevance/durability controls and consolidation behavior.

### 3️⃣ [Intelligence & Reasoning](./agentic/Intelligence.md)
- Meta-router category routing.
- Tool-schema minimization and prompt split strategy.
- REACT step budgeting and reflection loop.

### 4️⃣ [Operations & Robustness](./agentic/Operations.md)
- Job persistence (`~/.cowork/jobs.json`) and recovery behavior.
- Execution gateway, firewall checks, and safety constraints.
- Runtime limits and configuration mapping.

### 5️⃣ [Data & Relational Architecture](./new_docs/11_Concept_Relationships.md)
- Session/workspace mapping and persistence relationships.
- Cascading rename/delete behavior.

### 6️⃣ [Testing Strategy](../tests/TEST_ARCHITECTURE.md)
- Headless evaluation harness and dataset structure.
- Regressions coverage for reasoning, memory, and tools.

---

## 🛠️ Developer Quick-Check
- [ ] **Modifying routing?** Update `cli/cowork/router.py` and, if needed, `cli/cowork/skills/router.py`.
- [ ] **Modifying skills?** Check `cli/cowork/skills/runtime.py`, `catalog.py`, and `trust.py`.
- [ ] **Changing limits?** Sync `cli/cowork/config.py` defaults and docs tables.
