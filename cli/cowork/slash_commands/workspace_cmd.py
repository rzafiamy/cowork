"""
cowork/slash_commands/workspace_cmd.py
───────────────────────────────────────
Handlers for /workspace slash command.
"""

from __future__ import annotations

from typing import Optional

import click
from rich.markdown import Markdown

from ..config import Session, Scratchpad
from ..workspace import workspace_manager, WORKSPACE_ROOT
from ..ui import ThinkingSpinner, console, render_success
from ..core import _config


async def handle_workspace(
    parts: list[str],
    session: Session,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /workspace command."""
    from rich.table import Table
    from rich import box
    from ..config import SESSIONS_DIR, SCRATCHPAD_DIR
    import shutil

    sub = parts[1].lower() if len(parts) > 1 else ""

    if sub == "list":
        sessions = workspace_manager.list_all()
        if not sessions:
            console.print("[muted]No workspace sessions found.[/muted]")
        else:
            table = Table(title="🗂️  Workspace Sessions", box=box.ROUNDED, border_style="primary")
            table.add_column("Slug / Folder", style="highlight", min_width=24)
            table.add_column("Title", style="bold_white")
            table.add_column("Msgs", justify="center", style="muted")
            table.add_column("Last Active", style="dim_text")
            for s in sessions[:20]:
                updated = s.get("updated_at", "")[:16].replace("T", " ")
                table.add_row(s["slug"], s["title"][:40], str(s["message_count"]), updated)
            console.print(table)
            console.print(f"[dim_text]  📂 Root: {WORKSPACE_ROOT}[/dim_text]")

    elif sub == "search" and len(parts) > 2:
        query = parts[2]
        results = workspace_manager.search(query)
        if not results:
            console.print(f"[muted]No matches for '{query}'.[/muted]")
        else:
            for r in results:
                console.print(f"  [highlight]{r['slug']}/[/highlight] — {r['title']}")
                for m in r["matches"]:
                    console.print(f"    [dim_text]• {r['slug']}/{m}[/dim_text]")

    elif sub == "open":
        ws = getattr(session, "_ws", None)
        if ws:
            console.print(f"  [success]📂 Session workspace:[/success] [highlight]{ws.path}[/highlight]")
        else:
            console.print(f"  [muted]📂 Workspace root:[/muted] [highlight]{WORKSPACE_ROOT}[/highlight]")

    elif sub == "clean":
        if click.confirm(
            "⚠️  Are you sure you want to delete ALL sessions and workspace folders? This cannot be undone.",
            default=False,
        ):
            with ThinkingSpinner("Cleaning workspace"):
                ws_count = workspace_manager.clear_all()
                s_count = 0
                for p in SESSIONS_DIR.glob("*.json"):
                    p.unlink()
                    s_count += 1
                from ..config import SCRATCHPAD_DIR
                for p in SCRATCHPAD_DIR.iterdir():
                    if p.is_dir():
                        shutil.rmtree(p)

            render_success(
                f"🧹 Workspace cleaned. Deleted {ws_count} workspace folders and {s_count} session files."
            )
            new_session = Session(title="New Session")
            ws = workspace_manager.ensure_for_session(new_session.session_id, title="New Session")
            new_session.workspace_slug = ws.slug
            new_session._ws = ws
            new_session.save()
            return True, new_session, False

    else:
        ws = getattr(session, "_ws", None)
        if ws:
            console.print(f"  [success]📂 Current session workspace:[/success] [highlight]{ws.path}[/highlight]")
            ctx = ws.read_context()
            if ctx:
                console.print(Markdown(ctx[:1000]))
        else:
            console.print("  [muted]No workspace session linked. Use /new to create one.[/muted]")
        console.print()
        console.print("[dim_text]  /workspace list          — list all sessions[/dim_text]")
        console.print("[dim_text]  /workspace search <q>    — search across sessions[/dim_text]")
        console.print("[dim_text]  /workspace open          — show current session path[/dim_text]")
        console.print("[dim_text]  /workspace clean         — delete all sessions and workspace folders[/dim_text]")

    return True, None, False
