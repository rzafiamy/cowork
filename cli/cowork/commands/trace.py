"""
cowork/commands/trace.py
────────────────────────
CLI command: `trace`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
import json
from rich.syntax import Syntax

from ..tracing import find_latest_trace_file, load_trace_events, render_trace_timeline
from ..ui import print_banner, render_error, console
from ..core import _last_trace


@click.command()
@click.option("--file", "trace_file", type=click.Path(exists=True, path_type=Path), default=None, help="Open a specific JSONL trace file")
@click.option("--session-id", "-s", default=None, help="Find latest trace for a session ID")
@click.option("--raw", is_flag=True, default=False, help="Print raw JSON lines")
@click.option("--full/--summary", default=True, help="Show full event payloads or keys-only summary")
def trace(trace_file: Optional[Path], session_id: Optional[str], raw: bool, full: bool) -> None:
    """Render trace logs in a readable timeline format."""
    target = trace_file
    if target is None and _last_trace and _last_trace.get("path"):
        p = Path(_last_trace["path"])
        if p.exists():
            target = p
    if target is None:
        target = find_latest_trace_file(session_id=session_id)

    if target is None:
        render_error("No trace file found.", hint="Run 'cowork chat --trace' or pass --file <path>.")
        return

    events = load_trace_events(target)
    if not events:
        render_error(f"Trace is empty or unreadable: {target}")
        return

    print_banner()
    console.print(f"[muted]Trace file:[/muted] [highlight]{target}[/highlight]")
    console.print(f"[muted]Events:[/muted] {len(events)}")
    console.print()
    if raw:
        raw_jsonl = "\n".join(json.dumps(e, ensure_ascii=False) for e in events)
        console.print(Syntax(raw_jsonl, "json", theme="monokai", background_color="default"))
    else:
        console.print(
            render_trace_timeline(
                events,
                full=full,
                max_value_chars=20000,
                trace_file=str(target),
            )
        )
