"""
cowork/slash_commands/handler.py
─────────────────────────────────
Main slash-command dispatcher — routes /commands to their module handlers.
"""

from __future__ import annotations

from typing import Optional

from ..config import Session, Scratchpad
from ..memoria import Memoria
from ..ui import render_warning

from .sessions import handle_sessions, handle_load
from .jobs import handle_jobs
from .config_cmd import handle_config, handle_scratchpad
from .workspace_cmd import handle_workspace
from .cron_cmd import handle_cron
from .memory_cmd import handle_memory, handle_issues
from .ai_cmd import handle_ai, handle_model, handle_mm
from .trace_cmd import handle_trace, handle_stats, handle_tokens
from .acl_cmd import handle_acl
from .misc_cmd import (
    handle_exit,
    handle_clear,
    handle_new,
    handle_tools,
    handle_reset,
    handle_open,
)


async def handle_command(
    cmd: str,
    session: Session,
    api_client,
    scratchpad: Scratchpad,
    memoria: Memoria,
    sessions_list: list[dict],
) -> tuple[bool, Optional[Session], bool]:
    """
    Handle slash commands typed in the interactive REPL.
    Returns (should_continue, new_session_if_changed, needs_rebuild).
    """
    parts = cmd.strip().split(maxsplit=2)
    command = parts[0].lower()

    # ── Exit ─────────────────────────────────────────────────────────────────
    if command in ("/exit", "/quit", "/q"):
        return handle_exit()

    # ── Clear / Help ──────────────────────────────────────────────────────────
    elif command == "/help":
        from ..ui import render_help
        render_help()

    elif command == "/clear":
        return handle_clear()

    # ── Session management ────────────────────────────────────────────────────
    elif command == "/new":
        return handle_new(session)

    elif command in ("/sessions", "/session"):
        return await handle_sessions(cmd, parts, session, api_client)

    elif command == "/load":
        return await handle_load(parts, session)

    # ── Jobs ──────────────────────────────────────────────────────────────────
    elif command == "/jobs":
        return await handle_jobs(parts, session, api_client, scratchpad, memoria)

    # ── Config / Scratchpad ───────────────────────────────────────────────────
    elif command == "/config":
        return await handle_config(cmd, parts)

    elif command == "/scratchpad":
        return await handle_scratchpad(parts, scratchpad)

    elif command == "/workspace":
        return await handle_workspace(parts, session)

    elif command == "/acl":
        return await handle_acl(parts, session)

    # ── Trace / Stats / Tokens ────────────────────────────────────────────────
    elif command == "/trace":
        return await handle_trace(parts, session)

    elif command in ("/stats", "/st"):
        return await handle_stats(session, memoria, scratchpad)

    elif command == "/tokens":
        return await handle_tokens(parts)

    # ── Cron ──────────────────────────────────────────────────────────────────
    elif command == "/cron":
        return await handle_cron(cmd, parts, session, api_client, scratchpad, memoria)

    # ── Issues ────────────────────────────────────────────────────────────────
    elif command in ("/issues",):
        return await handle_issues(parts)

    # ── Memory ───────────────────────────────────────────────────────────────
    elif command in ("/memory", "/vector"):
        return await handle_memory(parts, memoria)

    # ── Tools ─────────────────────────────────────────────────────────────────
    elif command == "/tools":
        return handle_tools()

    # ── Reset ─────────────────────────────────────────────────────────────────
    elif command == "/reset":
        return handle_reset()

    # ── AI / Model / MM ───────────────────────────────────────────────────────
    elif command == "/ai":
        return await handle_ai(cmd, parts)

    elif command == "/model":
        return await handle_model(parts, api_client)

    elif command == "/mm":
        return await handle_mm(cmd, parts)

    # ── Open ──────────────────────────────────────────────────────────────────
    elif command == "/open":
        return handle_open(cmd, session)

    # ── Unknown ───────────────────────────────────────────────────────────────
    else:
        render_warning(f"Unknown command: {command}. Type /help for available commands.")

    return True, None, False
