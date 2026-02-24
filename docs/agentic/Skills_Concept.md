# 🧩 Skills Progressive Disclosure Concept

## 🚀 Overview
The **Skills System** is a high-performance orchestration layer designed to provide the AI agent with deep, task-specific instructions without overwhelming the context window or increasing latency.

It operates on the principle of **Progressive Disclosure**: the agent is aware of the existence of all skills, but only "downloads" the full instructional payload when a specific skill is activated.

---

## 🏛️ The 3-Level Disclosure Strategy

| Level | Component | Injection Frequency | Token Cost | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Level 1** | **Library TOC** | Every Turn | ~200 | Provides awareness of available "experts" (Name + Description). |
| **Level 2** | **Skill Body** | Intent-Triggered | ~1k - 5k | Loads the full `SKILL.md` (Workflow, Guardrails, Persona). |
| **Level 3** | **Resources** | Explicit Directive | Up to 10k | Loads external files via `LOAD_REF(path)` directives. |

---

## 🧭 The Selection Mechanism (The Skill Router)
Unlike the **Meta-Router** (Phase 2), which uses an LLM to classify broad categories, the **Skill Router** uses a fast, deterministic scoring algorithm to select the active skill.

### 🧠 Why not use an LLM for selection?
1. **Latency**: A separate LLM call adds ~1s of latency. The scoring router is `<5ms`.
2. **Synergy**: It leverages the LLM's work by weighting skills that align with the categories already selected by the Meta-Router.
3. **Safety**: Deterministic triggers prevent "hallucinated activation" of high-privilege skills.

### ⚖️ Selection Weights
- **Explicit Mention** (`$skill_name`): 1.0 (Instant Lock)
- **Token Overlap**: Lexical match between user input and skill triggers/description.
- **Category Alignment**: `+0.35` bonus if the skill belongs to a category selected by the Meta-Router.
- **Trigger Match**: `+0.55` bonus if specific trigger keywords (e.g., "image", "fix bug") are present in the query.

---

## 🛡️ Security & Safety
The Skills system acts as a **Deterministic Firewall**:

- **Activation Limit**: Generally, only **one** skill is active at a time to prevent conflicting instructions.
- **Trust Tiers**: Skills have tiers (1-3). Advanced capabilities (like writing to the workspace) are only allowed if the trust evaluation passes.
- **Tool Filtering**: An active skill defines which tools it is allowed to use. The `SkillRuntime` prunes the global tool schema based on these permissions.

---

## 📍 Implementation Reference
- **Runtime Logic**: `cli/cowork/skills/runtime.py`
- **Scoring Algorithm**: `cli/cowork/skills/router.py`
- **Skill Library**: `cli/cowork/skills/library/`
- **Initial Phase**: Handled in `cli/cowork/agent.py` within the `run()` loop.
