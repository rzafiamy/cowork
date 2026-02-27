# 🛡️ File Access Control Layer (ACL)

## Overview

The **ACL** is a centralized file I/O gateway that enforces read/write rules on every file operation performed by Cowork. It is the filesystem equivalent of the firewall that governs tool execution.

**Key guarantee:** Every file read, write, append, or binary write in every tool goes through `file_manager` — the singleton `FileManager` instance. There are no bypasses.

---

## Architecture

```
Tool / WorkspaceSession
        │
        ▼
   FileManager              ← single gateway for all file I/O
        │
        ▼
 AccessControlManager       ← loads ~/.cowork/acl.yaml
        │
    ┌───┴────┐
  Allow   Block / Audit
    │
    ▼
 acl.log                    ← every access event is logged
```

### Core Files

| File | Role |
|------|------|
| `cli/cowork/acl.py` | `AccessControlManager`, `FileManager`, singletons |
| `~/.cowork/acl.yaml` | User-editable ACL rules (created on first run) |
| `~/.cowork/acl.log` | Per-access audit log (JSON lines) |

---

## FileManager API

Import the singleton from anywhere in the codebase:

```python
from .acl import file_manager
```

### Text

```python
# Read UTF-8 text (ACL-checked)
text = file_manager.read_text(path, reason="tool: context read")

# Overwrite a text file (parent dirs created automatically)
file_manager.write_text(path, content, reason="workspace artifact")

# Append to a text file
file_manager.append_text(path, extra, reason="session log append")
```

### Binary

```python
# Read raw bytes (e.g. image, audio)
raw = file_manager.read_bytes(path, reason="vision_analyze")

# Write raw bytes (e.g. generated PDF, TTS audio)
file_manager.write_bytes(path, data, reason="document_create_pdf")
```

### JSON

```python
data = file_manager.read_json(path, reason="load index")
file_manager.write_json(path, data, indent=2, reason="update index")
```

### Directory

```python
file_manager.makedirs(path, reason="ensure workspace dir")
```

### Stat helpers (no ACL check)

```python
file_manager.exists(path)   # → bool
file_manager.is_file(path)  # → bool
file_manager.is_dir(path)   # → bool
```

---

## ACL Rules (`~/.cowork/acl.yaml`)

Rules are evaluated in order. The **first matching rule** wins. If no rule matches, the **default policy** applies.

```yaml
# 🗝️ Cowork File Access Control (ACL)

policy:
  default_read: allow      # allow | block | audit
  default_write: allow     # allow | block | audit

rules:
  - pattern: ~/.cowork/workspace/**
    access: any            # any | read | write
    action: allow
    description: Allow full access to workspace storage.

  - pattern: ~/.cowork/config.json
    access: write
    action: block
    description: Protect the main config from agent writes.

  - pattern: */secret/**
    access: write
    action: block
    description: Block writes to any 'secret' folder.

  - pattern: /etc/**
    access: any
    action: block
    description: Never touch system files.
```

### Pattern Syntax

| Pattern form | Behaviour |
|---|---|
| `~/.cowork/**` | Home-dir-expanded, recursive |
| `/absolute/path/**` | Absolute, passed through |
| `*/secret/*` | Pure glob — no anchoring |
| `relative/path` | Anchored to `~/.cowork/` |

`fnmatch` semantics apply: `*` matches any path segment, `**` matches across separators only when the full path is used. Use `**/subdir/**` for depth-independent matching.

### Access values

| Value | Meaning |
|---|---|
| `any` | Match all access types |
| `read` | Match reads only |
| `write` | Match writes and appends |

### Action values

| Value | Behaviour |
|---|---|
| `allow` | Permit the operation (logged as `acl_allow`) |
| `block` | Raise `FileAccessDenied`, log as `acl_block` |
| `audit` | Permit but log as `acl_audit` (extra visibility) |

---

## Coverage — Where FileManager Is Used

All the following subsystems are now ACL-enforced:

| Module | Operations covered |
|--------|-------------------|
| `workspace.py` | Session `save()`, `load()`, `write_context()`, `read_context()`, `scratchpad_save/get/list`, `save_note`, `write_artifact`, `rename`, `search` |
| `tools/builtin/workspace.py` | `WorkspaceReadTool`, `WorkspaceWriteTool` |
| `tools/builtin/coding.py` | `CodebaseReadFileTool`, `CodebaseWriteFileTool`, `CodebaseSearchTextTool` |
| `tools/builtin/document.py` | PDF bytes write, PPTX/XLSX/DOCX saves |
| `tools/builtin/multimodal.py` | Image read for vision, image/audio write for generation and TTS |
| `tools/builtin/media.py` | All artifact writes |
| `tools/builtin/connectors.py` | `StorageWriteTool` |

---

## Audit Log

Every file access event is appended to `~/.cowork/acl.log` as a JSON line:

```json
{"timestamp": "2026-02-27T12:00:00Z", "event": "acl_allow", "data": {"path": "/home/user/.cowork/workspace/my-session/artifacts/report.pdf", "access": "write", "action": "allow", "rule": "Allow writing artifacts and scratchpad data.", "reason": "document_create_pdf: report.pdf"}}
{"timestamp": "2026-02-27T12:00:05Z", "event": "acl_block", "data": {"path": "/etc/passwd", "access": "read", "action": "block", "rule": "Never touch system files.", "reason": "codebase_read_file: /etc/passwd"}}
```

Events: `acl_allow`, `acl_audit`, `acl_block`.

---

## Errors

When access is blocked, `FileAccessDenied` (a subclass of `PermissionError`) is raised:

```
PermissionError: WRITE access denied for /etc/passwd — action=block, Never touch system files.
```

This propagates up through the tool executor and is returned to the LLM as a tool error, preventing silent failures or hallucinations.

---

## Related Documentation

- [Operations.md](./Operations.md) — Firewall for tool execution
- [Tools.md](./Tools.md) — Tool registry and execution model
- [Workflow.md](./Workflow.md) — End-to-end agent execution flow
