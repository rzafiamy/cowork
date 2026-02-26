---
name: commandline-tools
description: Execute Linux commands safely on the local machine with automated risk assessment and failsafes.
triggers:
  - shell
  - bash
  - command
  - terminal
  - linux
  - cli
trust_tier: 4
tool_categories:
  - COMMAND_LINE
permissions:
  tools:
    - codebase_bash
---
# Commandline Tools Skill

Purpose: Provide the AI with the ability to interact with the Linux system via command line, ensuring maximum safety and user transparency.

## Workflow

### 1. Risk-Aware Command Proposal
Before calling any command or starting a sequence, the AI must categorize the intent:
- 🔴 **DANGEROUS**: Destructive or system-wide changes (e.g., `rm`, `sudo`, `sed -i` on configs).
- ⚠️ **WARNING**: State changes, resource-intensive, or complex operations (e.g., `git push`, `npm install`, network requests).
- ✅ **SAFE**: Read-only operations or non-destructive checks (e.g., `ls`, `cat`, `grep`, `find`, `wc`).

For any 🔴 or ⚠️ command, the AI **MUST** briefly:
- State the risk and why it's necessary.
- **Ensure Failsafe**: List the backup taken (e.g., `cp config.json config.json.bak`).
- Provide a recovery hint (e.g., "If this fails, restore the backup").

### 2. Firewall Authorization
- All commands are blocked by the **Firewall Ask Rule** by default.
- The AI should not ask the user for permission *in text* (to avoid redundant questions), as the firewall will automatically trigger the system-level `[Y/n]` prompt.

### 3. Execution Summary
Once the command finishes (or fails), provide a clear recap:
- **Result**: Success/Failure.
- **Changes**: Summary of what was modified.
- **Next Step**: What the AI will do now based on the output.

## Guardrails
- **Dry-run first**: When applicable, use dry-run flags or read-only checks first.
- **No Obfuscation**: Never use complex pipes or encodings to hide the intent of a command.
