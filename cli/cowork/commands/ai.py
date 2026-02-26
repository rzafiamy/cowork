"""
cowork/commands/ai.py
─────────────────────
CLI command: `ai` group.
"""

from __future__ import annotations

import click

from ..ui import render_ai_profiles, render_error, render_success
from ..core import _config, _ai_profiles


@click.command()
@click.argument("action", type=click.Choice(["list", "add", "switch", "remove", "save"]), default="list")
@click.argument("args", nargs=-1)
def ai(action: str, args: tuple) -> None:
    """Manage AI profiles (endpoints, models, keys)."""
    from ..ui import print_banner
    print_banner()
    if action == "list":
        render_ai_profiles(_ai_profiles.list_all())
    elif action == "add":
        if len(args) < 3:
            render_error("Usage: cowork ai add <name> <endpoint> <model> [description]")
            return
        name, endpoint, model = args[0], args[1], args[2]
        desc = " ".join(args[3:]) if len(args) > 3 else ""
        _ai_profiles.add(name, endpoint, model, description=desc)
        render_success(f"✅ AI profile '{name}' saved.")
    elif action == "switch":
        if not args:
            render_error("Usage: cowork ai switch <name>")
            return
        name = args[0]
        profile = _ai_profiles.switch(name)
        if profile:
            render_success(f"🤖 Switched to profile '{name}' ({profile.model})")
        else:
            render_error(f"Profile '{name}' not found.")
    elif action == "remove":
        if not args:
            render_error("Usage: cowork ai remove <name>")
            return
        name = args[0]
        if _ai_profiles.remove(name):
            render_success(f"🗑️  Profile '{name}' removed.")
        else:
            render_error(f"Profile '{name}' not found.")
    elif action == "save":
        name = args[0] if args else "default"
        _ai_profiles.snapshot_current(_config, name)
        render_success(f"💾 Saved current config as profile '{name}'.")
