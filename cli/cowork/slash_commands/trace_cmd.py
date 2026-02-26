"""
cowork/slash_commands/trace_cmd.py
───────────────────────────────────
Handlers for /trace and /stats and /tokens slash commands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import json
from rich.syntax import Syntax
from rich.tree import Tree

from ..config import Session
from ..tracing import find_latest_trace_file, load_trace_events, render_trace_timeline, render_llm_trace
from ..ui import console, render_error, render_session_stats, render_success, render_token_usage, render_warning
from ..core import _config, _job_manager, _token_tracker, _last_job, get_memory_user_id

import click


async def handle_trace(
    parts: list[str],
    session: Session,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /trace command."""
    sub = parts[1].lower() if len(parts) > 1 else ""

    if sub in ("full", "raw", "path", "llm"):
        target_path = ""
        if len(parts) > 2:
            target_path = parts[2]
        elif _last_job and _last_job.session_id == session.session_id and getattr(_last_job, "trace_path", ""):
            target_path = _last_job.trace_path
        else:
            latest = find_latest_trace_file(session.session_id)
            if latest:
                target_path = str(latest)

        if not target_path:
            console.print("[muted]No trace file available for this session yet.[/muted]")
        else:
            p = Path(target_path)
            events = load_trace_events(p)
            if not events:
                console.print(f"[muted]Trace is empty or unreadable: {p}[/muted]")
            elif sub == "path":
                console.print(f"[highlight]{p}[/highlight]")
            elif sub == "raw":
                console.print(
                    Syntax(
                        "\n".join(json.dumps(e, ensure_ascii=False) for e in events),
                        "json",
                        theme="monokai",
                        background_color="default",
                    )
                )
            elif sub == "llm":
                console.print(render_llm_trace(events))
            else:
                console.print(
                    render_trace_timeline(
                        events,
                        full=True,
                        max_value_chars=12000,
                        trace_file=str(p),
                    )
                )
        return True, None, False

    if sub == "clean":
        if click.confirm("Are you sure you want to delete ALL trace files?", default=False):
            from ..tracing import clean_all_traces
            count = clean_all_traces()
            render_success(f"🧹 Deleted {count} trace file(s).")
        return True, None, False

    if _last_job:
        tree = Tree(f"[primary]🔍 Trace: Job {_last_job.job_id}[/primary]")
        tree.add(f"[muted]Status:[/muted] {_last_job.status}")
        if _last_job.skill_name:
            tree.add(f"🧩 [highlight]Active Skill:[/highlight] {_last_job.skill_name}")
        tree.add(f"[muted]Steps:[/muted] {_last_job.steps}")
        tree.add(f"[muted]Tool Calls:[/muted] {_last_job.tool_calls}")
        if getattr(_last_job, "trace_path", ""):
            tree.add(f"[muted]Trace File:[/muted] {_last_job.trace_path}")

        if hasattr(_last_job, "tool_calls_list") and _last_job.tool_calls_list:
            tools_tree = tree.add("[tool]🛠️  Tool Execution History[/tool]")
            for i, tc in enumerate(_last_job.tool_calls_list, 1):
                status_color = "success" if tc.get("status") == "success" else "error"
                tc_node = tools_tree.add(f"#{i} [{status_color}]{tc['name']}[/{status_color}]")
                if tc.get("args"):
                    args_str = json.dumps(tc["args"], indent=2)
                    tc_node.add(Syntax(args_str, "json", theme="monokai", background_color="default"))

        tree.add(f"[muted]Categories:[/muted] {', '.join(_last_job.categories)}")
        tree.add(f"[muted]Prompt:[/muted] {_last_job.prompt[:80]}...")
        console.print(tree)
    else:
        console.print("[muted]No trace available yet.[/muted]")

    return True, None, False


async def handle_stats(
    session: Session,
    memoria,
    scratchpad,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /stats command."""
    from ..ui import render_session_stats

    totals = _token_tracker.get_totals()
    items = scratchpad.list_all()
    stats = {
        "session_id": session.session_id,
        "title": session.title,
        "created_at": session.created_at[:19].replace("T", " ") if session.created_at else "—",
        "message_count": len(session.messages),
        "memory_triplets": memoria.get_triplet_count(),
        "has_summary": bool(memoria.get_summary()),
        "user_id": get_memory_user_id()[:8] + "...",
        "scratchpad_items": len(items),
        "scratchpad_chars": sum(it.get("size_chars", 0) for it in items),
        "workspace_path": str(session._ws.path) if hasattr(session, "_ws") and session._ws else "(none)",
        "total_tokens": totals.get("total_tokens", 0),
        "prompt_tokens": totals.get("prompt_tokens", 0),
        "completion_tokens": totals.get("completion_tokens", 0),
        "request_count": totals.get("request_count", 0),
    }
    render_session_stats(stats)

    return True, None, False


async def handle_tokens(
    parts: list[str],
) -> tuple[bool, Optional[Session], bool]:
    """Handle /tokens command."""
    if len(parts) > 1 and parts[1] == "reset":
        if click.confirm("Reset all token usage counters?", default=False):
            _token_tracker.reset()
            render_success("🧹 Token usage counters reset.")
    else:
        render_token_usage(_token_tracker.get_all(), _token_tracker.get_totals())

    return True, None, False
