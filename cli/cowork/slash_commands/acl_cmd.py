"""
cowork/slash_commands/acl_cmd.py
─────────────────────────────────
Handlers for /acl slash commands.
"""

from __future__ import annotations

from typing import Optional
import json
from rich.table import Table

from ..config import Session
from ..acl import ACCESS_CONTROL, ACL_FILE, ACL_LOG_FILE, FileAccessAction
from ..ui import console, render_success, render_error

import click

async def handle_acl(
    parts: list[str],
    session: Session,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /acl command."""
    sub = parts[1].lower() if len(parts) > 1 else "list"

    if sub == "edit":
        if not ACL_FILE.exists():
            ACCESS_CONTROL._create_default()
        click.edit(filename=str(ACL_FILE))
        render_success(f"ACL configuration updated: [dim_text]{ACL_FILE}[/dim_text]")
        return True, None, False

    elif sub in ("trace", "log"):
        limit = 20
        session_only = True
        
        # Parse extra args
        if len(parts) > 2:
            try:
                limit = int(parts[2])
            except ValueError:
                if parts[2] == "all":
                    session_only = False
        
        if not ACL_LOG_FILE.exists():
            console.print("[muted]ACL log is empty.[/muted]")
            return True, None, False

        console.print(f"[primary]🗝️  ACL Log (last {limit} events{' for this session' if session_only else ''})[/primary]")
        
        events = []
        try:
            with open(ACL_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                        if session_only and ev.get("session_id") != session.session_id:
                            continue
                        events.append(ev)
                    except:
                        continue
        except Exception as exc:
            render_error(f"Failed to read ACL log: {exc}")
            return True, None, False

        events = events[-limit:]
        
        if not events:
            console.print("  [dim_text]No ACL events found.[/dim_text]")
            return True, None, False

        table = Table(box=None, padding=(0, 1))
        table.add_column("Time", style="dim")
        table.add_column("Action", style="bold")
        table.add_column("Access", style="dim")
        table.add_column("Path")
        table.add_column("Rule", style="dim")

        for ev in events:
            ts = ev.get("timestamp", "?").split("T")[-1][:8]
            data = ev.get("data", {})
            path = data.get("path", "?")
            access = data.get("access", "?").upper()
            action = data.get("action", "?").upper()
            rule = data.get("rule", "?")
            
            color = "success" if action == "ALLOW" else "error" if action == "BLOCK" else "warning"
            table.add_row(ts, f"[{color}]{action}[/{color}]", access, path, rule)
        
        console.print(table)
        return True, None, False

    elif sub == "reset":
        if click.confirm("Restore default ACL rules?", default=False):
            ACCESS_CONTROL._create_default()
            render_success("ACL rules reset to defaults.")
        return True, None, False

    else:
        # Default: list
        rules = ACCESS_CONTROL._rules
        policy = ACCESS_CONTROL._policy
        
        read_action = policy.get("default_read", FileAccessAction.ALLOW).value.upper()
        write_action = policy.get("default_write", FileAccessAction.ALLOW).value.upper()
        
        console.print(f"[primary]Global Policy:[/primary] Read=[bold]{read_action}[/bold], Write=[bold]{write_action}[/bold]")
        
        if rules:
            table = Table(title="🗝️ ACL Rules", border_style="primary")
            table.add_column("Pattern", style="cyan")
            table.add_column("Access", style="yellow")
            table.add_column("Action", style="magenta")
            table.add_column("Description")
            
            for r in rules:
                action_color = "success" if r.action == FileAccessAction.ALLOW else "error" if r.action == FileAccessAction.BLOCK else "warning"
                table.add_row(
                    r.pattern,
                    r.access.upper(),
                    f"[{action_color}]{r.action.value.upper()}[/{action_color}]",
                    r.description
                )
            console.print(table)
        else:
            console.print("  [dim_text]No explicit rules.[/dim_text]")
        
        console.print("[dim_text]Use [bold]/acl edit[/bold] to update rules or [bold]/acl log[/bold] to see audit trails.[/dim_text]")
        return True, None, False
