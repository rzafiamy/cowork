"""
cowork/commands/acl.py
───────────────────────
CLI command: `acl`.
"""

from __future__ import annotations

import click
import json
from pathlib import Path
from typing import Optional

from ..acl import ACCESS_CONTROL, ACL_FILE, ACL_LOG_FILE, FileAccessAction
from ..ui import print_banner, render_success, render_error, console
from rich.table import Table

@click.group(invoke_without_command=True)
@click.pass_context
def acl(ctx: click.Context) -> None:
    """🗝️ Manage the file access control layer (ACL)."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_rules)

@acl.command(name="list")
def list_rules() -> None:
    """List all ACL rules and global policy."""
    print_banner()
    rules = ACCESS_CONTROL._rules
    policy = ACCESS_CONTROL._policy
    
    # Global Policy
    read_action = policy.get("default_read", FileAccessAction.ALLOW).value.upper()
    write_action = policy.get("default_write", FileAccessAction.ALLOW).value.upper()
    
    console.print(f"  [bold]Global Policy:[/bold]")
    console.print(f"    Default Read:  [success]{read_action}[/success]" if read_action == "ALLOW" else f"    Default Read:  [error]{read_action}[/error]")
    console.print(f"    Default Write: [success]{write_action}[/success]" if write_action == "ALLOW" else f"    Default Write: [error]{write_action}[/error]")
    console.print()
    
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
        console.print("  [dim_text]No explicit ACL rules defined.[/dim_text]")

@acl.command()
def edit() -> None:
    """Open the ACL configuration in your default editor."""
    if not ACL_FILE.exists():
        ACCESS_CONTROL._create_default()
    click.edit(filename=str(ACL_FILE))
    render_success(f"ACL configuration updated: [dim_text]{ACL_FILE}[/dim_text]")

@acl.command()
@click.option("--limit", "-n", default=20, help="Number of last log entries to show")
@click.option("--session-id", "-s", default=None, help="Filter by session ID")
def trace(limit: int, session_id: Optional[str]) -> None:
    """Show the file access audit log (ACL trace)."""
    if not ACL_LOG_FILE.exists():
        render_error("ACL log file not found.")
        return

    print_banner()
    console.print(f"[muted]ACL Trace (last {limit} entries):[/muted]")
    console.print()

    events = []
    try:
        with open(ACL_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                    if session_id and ev.get("session_id") != session_id:
                        continue
                    events.append(ev)
                except:
                    continue
    except Exception as exc:
        render_error(f"Failed to read ACL log: {exc}")
        return

    events = events[-limit:]
    
    if not events:
        console.print("  [dim_text]No ACL events found matching criteria.[/dim_text]")
        return

    table = Table(box=None, padding=(0, 1))
    table.add_column("Timestamp", style="dim")
    table.add_column("Session", style="blue")
    table.add_column("Action", style="bold")
    table.add_column("Access", style="dim")
    table.add_column("Path")
    table.add_column("Rule", style="dim")

    for ev in events:
        ts = ev.get("timestamp", "?").split("T")[-1][:8]
        sid = (ev.get("session_id") or "system")[:8]
        event_type = ev.get("event", "?")
        data = ev.get("data", {})
        path = data.get("path", "?")
        access = data.get("access", "?").upper()
        action = data.get("action", "?").upper()
        rule = data.get("rule", "?")
        
        color = "success" if action == "ALLOW" else "error" if action == "BLOCK" else "warning"
        
        table.add_row(
            ts,
            sid,
            f"[{color}]{action}[/{color}]",
            access,
            path,
            rule
        )
    
    console.print(table)

@acl.command()
@click.confirmation_option(prompt="This will overwrite your existing ACL rules. Continue?")
def reset() -> None:
    """Restore default ACL configuration."""
    ACCESS_CONTROL._create_default()
    render_success("ACL configuration reset to defaults.")
