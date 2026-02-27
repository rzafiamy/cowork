# 🧠 Cowork Prompt Architecture

This document describes how the **Cowork** system prompt is constructed, what information is dynamically injected, and the expected message formatting.

## 🏗️ Prompt Construction

The system prompt is a fusion of a static base template and several dynamic context blocks. It is centralized in `cli/cowork/prompts.py`.

### 1. Static Base (`AGENT_SYSTEM_PROMPT`)
Defines the core identity, operating guidelines, and task anchoring strategies. It uses placeholders like `{current_datetime}` and `{memory_context}`.

### 2. Dynamic Enhancements
At runtime, the following sections are computed and injected:

- **DateTime**: The current local time and session ID.
- **Memory**: 
  - **Session Context**: A rolling summary of the current conversation.
  - **Persona Knowledge**: Triplet-based facts stored in the long-term memory (Memoria).
- **Working Memory (Scratchpad)**: An index of all keys and metadata currently stored in the session's scratchpad.
- **Execution Strategy & Plan**: 
  - In conversational mode, this notes that no plan is needed.
  - In tool mode, this contains the **Execution Plan** generated during the planning phase.
- **Capabilities & Skills**: Documentation of active skills and a Table of Contents for all available toolsets.
- **Tool Contract**: Strict rules on which tools can be called in the current turn.

## 🗺️ Message & Context Fusion

When a message is prepared for the LLM, the system performs "Context Fusion". This merges:
1.  The **System Prompt** (identity + instructions).
2.  The **Tool Records** (what has already been done in this session).
3.  The **Tool Contract** (what is allowed now).
4.  The **User Message**.

### Example Structure:
```markdown
## 📋 System Information
- **DateTime**: 2026-02-27 13:44 +0100 | **Session**: 299264f4
- **Context**: 0 msgs

## 🧠 Memory
## 📝 Session Context
(No session summary yet)

## 🧩 Persona Knowledge
• Lola has name Lola

... Operating Guidelines ...

## 🗺️ Execution Strategy & Plan
## 🗺️ Execution Plan
Goal: Search bird images and upload to Nextcloud.
Steps:
  Step 1: [search_web] Find bird images...
  Step 2: [nextcloud_upload_from_url] Upload...

- *(Follow the plan above sequentially. Note deviations explicitly. Stop when the goal is met.)*
```

## 📏 Formatting Expectations

The agent is instructed to strictly follow these formatting rules:

- **Markdown**: Use GitHub-flavored Markdown for all responses.
- **Headings**: 
  - `##` for major sections.
  - `###` for sub-sections.
- **Lists**: Use `-` for bullet points for consistency.
- **Tables & Code**: Ensure empty lines exist *around* all tables and code blocks to prevent layout issues in modern UIs.
- **Paths**: Only share file paths relative to the current workspace.
- **Precision**: Fail loudly with actionable hints instead of hallucinating paths or results.

## ⏱️ Step Budgeting

The agent tracks its own reasoning steps. If the budget is nearing its limit, the prompt forces the agent to lead its response with:
- `✅ ACHIEVED`
- `⚠️ PARTIALLY ACHIEVED`
- `❌ NOT ACHIEVED`

Followed by a detailed summary of remaining work.
