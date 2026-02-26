"""
cowork/commands/tools.py
────────────────────────
CLI command: `tools`.
"""

from __future__ import annotations

import click

from ..tools import get_all_available_tools
from ..ui import print_banner, render_tools_list


@click.command()
def tools() -> None:
    """List all currently activated tools."""
    print_banner()
    render_tools_list(get_all_available_tools())
