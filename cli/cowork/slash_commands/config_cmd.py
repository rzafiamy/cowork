"""
cowork/slash_commands/config_cmd.py
────────────────────────────────────
Handlers for /config and /scratchpad slash commands.
"""

from __future__ import annotations

from typing import Optional

from rich.panel import Panel

from ..config import Session, Scratchpad, is_sensitive_key
from ..ui import console, render_config, render_error, render_success
from ..core import _config


async def handle_config(
    cmd: str,
    parts: list[str],
) -> tuple[bool, Optional[Session], bool]:
    """Handle /config command."""
    if len(parts) >= 3 and parts[1] == "set":
        rest = cmd.split(maxsplit=3)
        if len(rest) >= 4:
            key, value = rest[2], rest[3]
            try:
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                elif "." in value:
                    value = float(value)
                else:
                    value = int(value)
            except (ValueError, AttributeError):
                pass
            _config.set(key, value)
            shown_value = "●●●●●●●●" if is_sensitive_key(key) and value else value
            render_success(f"✅ Set {key} = {shown_value}")
        else:
            render_error("Usage: /config set <key> <value>")
    else:
        render_config(_config.all())

    return True, None, False


async def handle_scratchpad(
    parts: list[str],
    scratchpad: Scratchpad,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /scratchpad command."""
    try:
        scratchpad._load_index()
    except Exception:
        pass

    sub = parts[1].lower() if len(parts) > 1 else ""

    if sub in ("read", "get") and len(parts) > 2:
        target = parts[2].strip().split()[0]
        content = None
        display_ref = target

        if target.isdigit():
            idx = int(target)
            items = scratchpad.list_all()
            if idx < 1 or idx > len(items):
                render_error(
                    f"Scratchpad number out of range: {target}",
                    hint="Use /scratchpad to list valid numbers.",
                )
                return True, None, False
            item = items[idx - 1]
            display_ref = f"ref:{item['key']}"
            content = scratchpad.get(item["key"])
        else:
            content = scratchpad.get(target)
            display_ref = f"ref:{target.replace('ref:', '')}"

        if content is None:
            render_error(
                f"Scratchpad item not found: {target}",
                hint="Use /scratchpad to list item numbers.",
            )
        else:
            console.print(Panel(content, title=f"[memory]📝 {display_ref}[/memory]", border_style="memory"))
    else:
        items = scratchpad.list_all()
        if not items:
            console.print("[muted]Scratchpad is empty.[/muted]")
        else:
            from rich.table import Table
            from rich import box

            table = Table(title="📝 Scratchpad", box=box.ROUNDED, border_style="memory")
            table.add_column("No", style="muted", justify="right")
            table.add_column("Key", style="highlight")
            table.add_column("Description", style="text")
            table.add_column("Size", style="muted", justify="right")
            table.add_column("Saved At", style="dim_text")
            for i, item in enumerate(items, start=1):
                table.add_row(
                    str(i),
                    item["key"],
                    item.get("description", "—"),
                    f"{item['size_chars']:,} chars",
                    item.get("saved_at", "")[:16],
                )
            console.print(table)

    return True, None, False
