"""
🚀 Cowork CLI — Main Entry Point
The autonomous agentic coworker powered by the Makix Enterprise Architecture.

This file is now a thin wrapper that registers subcommands from the commands/ package.
"""

import click

from .config import Session
from .workspace import workspace_manager
from .ui import render_success
from .core import verify_firewall_integrity

# Import commands
from .commands.chat import chat, run
from .commands.sessions import sessions, session_cmd
from .commands.config import config
from .commands.memory import memory, vector
from .commands.jobs import jobs
from .commands.issues import issues
from .commands.ai import ai
from .commands.mm import mm
from .commands.cron import cron
from .commands.tools import tools
from .commands.trace import trace
from .commands.misc import setup, ping, tokens, reset

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    🤖 Cowork — Makix Enterprise Agentic CLI Coworker

    A powerful autonomous AI agent with Manager-Worker architecture,
    long-term memory, meta-routing, and parallel tool execution.
    """
    verify_firewall_integrity()

    # Auto-clean ghost sessions (empty) at start
    s_deleted = Session.clean_empty()
    ws_deleted = workspace_manager.clean_empty()
    if s_deleted > 0 or ws_deleted > 0:
        render_success(f"🧹 Auto-cleaned {s_deleted} empty session(s) and {ws_deleted} empty workspace(s).")

    if ctx.invoked_subcommand is None:
        # Default: start interactive chat
        ctx.invoke(chat)

# Register subcommands
cli.add_command(chat)
cli.add_command(run)
cli.add_command(sessions)
cli.add_command(session_cmd)
cli.add_command(config)
cli.add_command(memory)
cli.add_command(vector)
cli.add_command(jobs)
cli.add_command(issues)
cli.add_command(ai)
cli.add_command(mm)
cli.add_command(cron)
cli.add_command(tools)
cli.add_command(trace)
cli.add_command(setup)
cli.add_command(ping)
cli.add_command(tokens)
cli.add_command(reset)

def main() -> None:
    cli()

if __name__ == "__main__":
    main()
