"""
cowork/commands/chat.py
────────────────────────
CLI commands: `chat` and `run`, plus the interactive REPL loop.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

import click

from ..config import Session, Scratchpad
from ..memoria import Memoria
from ..workspace import workspace_manager
from ..ui import (
    console,
    get_user_input,
    print_banner,
    print_welcome,
    render_error,
    render_success,
    render_user_message,
    run_setup_wizard,
)
from ..core import (
    _config,
    _job_manager,
    get_memory_user_id,
    make_api_client,
    make_session_scratchpad,
    background_cron_poll,
    run_agent_turn,
)
from ..slash_commands import handle_command


async def interactive_loop(
    session: Session,
    api_client,
    trace_enabled: bool = False,
) -> None:
    """Main interactive REPL loop."""
    scratchpad = make_session_scratchpad(session.session_id)
    user_id = get_memory_user_id()
    _memoria = Memoria(user_id, session.session_id, api_client, _config)

    sessions_list = Session.list_all()

    poll_task = asyncio.create_task(background_cron_poll())

    ghost_jobs = _job_manager.get_ghost_jobs()
    if ghost_jobs:
        from ..ui import render_warning
        render_warning(
            f"⚠️  Found {len(ghost_jobs)} interrupted job(s) from a previous session. "
            "Type /jobs to review."
        )

    console.print("[dim_text]  Type your message or use /help for commands. Press Ctrl+C to exit.[/dim_text]")
    console.print()

    while True:
        try:
            user_input = await get_user_input(session.title)
        except (KeyboardInterrupt, EOFError):
            user_input = "/exit"

        if not user_input:
            continue

        # Slash command
        if user_input.startswith("/"):
            should_continue, new_session, needs_rebuild = await handle_command(
                user_input, session, api_client, scratchpad, _memoria, sessions_list
            )
            if not should_continue:
                break

            if needs_rebuild:
                await api_client.close()
                api_client = make_api_client()
                _memoria.api_client = api_client

            if new_session:
                session = new_session
                scratchpad = make_session_scratchpad(session.session_id)
                _memoria = Memoria(user_id, session.session_id, api_client, _config)
            continue

        # Hashtag detection (Action Pills)
        action_mode = None
        ui = user_input.lower()
        if "#research" in ui:
            action_mode = {"categories": ["SEARCH_AND_INFO"], "pill": "#research"}
        elif "#task" in ui or "#kanban" in ui:
            action_mode = {"categories": ["APP_CONNECTORS"], "pill": "#task"}
        elif "#calc" in ui or "#math" in ui:
            action_mode = {"categories": ["DATA_AND_UTILITY"], "pill": "#calc"}
        elif "#note" in ui:
            action_mode = {"categories": ["APP_CONNECTORS"], "pill": "#note"}
        elif "#cron" in ui or "#schedule" in ui:
            action_mode = {"categories": ["CRON_TOOLS"], "pill": "#cron"}
        elif "#email" in ui or "#comms" in ui:
            action_mode = {"categories": ["COMMUNICATION_TOOLS"], "pill": "#email"}
        elif "#coding" in ui or "#code" in ui or "#web" in ui:
            action_mode = {"categories": ["CODING_TOOLS", "WORKSPACE_TOOLS"], "pill": "#coding"}

        if action_mode:
            console.print(f"  [accent]⚡ Action Pill detected: {action_mode['pill']}[/accent]")

        render_user_message(user_input)

        response, job = await run_agent_turn(
            user_input=user_input,
            session=session,
            api_client=api_client,
            scratchpad=scratchpad,
            memoria=_memoria,
            action_mode=action_mode,
            show_routing=True,
            trace_enabled=trace_enabled,
        )
        if trace_enabled and getattr(job, "trace_path", ""):
            console.print(f"  [dim_text]🧾 Trace saved: {job.trace_path}[/dim_text]")

        ws = getattr(session, "_ws", None)
        if ws and getattr(scratchpad, "_dir", None) != ws.scratchpad_path:
            scratchpad = make_session_scratchpad(session.session_id)

        _job_manager.cleanup_completed(keep=50)


# ─── CLI: chat ────────────────────────────────────────────────────────────────

@click.command()
@click.option("--session-id", "-s", default=None, help="Resume a specific session by ID")
@click.option("--no-banner", is_flag=True, default=False, help="Skip the banner")
@click.option("--trace/--no-trace", default=None, help="Enable full workflow trace logs")
def chat(session_id: Optional[str], no_banner: bool, trace: Optional[bool]) -> None:
    """Start an interactive agentic chat session."""
    if not no_banner:
        print_banner()

    if not _config.is_configured():
        if not run_setup_wizard(_config):
            sys.exit(1)

    print_welcome(_config)

    if session_id:
        session = Session.load(session_id)
        if not session:
            render_error(f"Session '{session_id}' not found.")
            session = Session(title="New Session")

        ws = workspace_manager.get_by_session_id(session.session_id)
        if ws:
            session._ws = ws
            session.workspace_slug = ws.slug
            session.save()
            console.print(f"  [dim_text]📂 Workspace: workspace/{ws.slug}/[/dim_text]")
        else:
            ws = workspace_manager.ensure_for_session(session.session_id, title=session.title or "New Session")
            session._ws = ws
            session.workspace_slug = ws.slug
            session.save()
            console.print(f"  [dim_text]📂 Workspace: workspace/{ws.slug}/[/dim_text]")
    else:
        session = Session(title="New Session")
        ws = workspace_manager.ensure_for_session(session.session_id, title="New Session")
        session._ws = ws
        session.workspace_slug = ws.slug
        session.save()
        console.print(f"  [dim_text]📂 Workspace: workspace/{ws.slug}/[/dim_text]")

    api_client = make_api_client()
    trace_enabled = _config.get("show_trace", False) if trace is None else trace

    async def _run_chat():
        try:
            await interactive_loop(session, api_client, trace_enabled=trace_enabled)
        finally:
            await api_client.close()

    try:
        asyncio.run(_run_chat())
    except KeyboardInterrupt:
        console.print()
        console.print("[primary]  👋 Session saved. Goodbye![/primary]")


# ─── CLI: run ─────────────────────────────────────────────────────────────────

@click.command()
@click.argument("prompt")
@click.option("--session-id", "-s", default=None, help="Session ID to use")
@click.option("--model", "-m", default=None, help="Override model")
@click.option("--no-stream", is_flag=True, default=False, help="Disable streaming")
@click.option("--trace/--no-trace", default=None, help="Enable full workflow trace logs")
def run(prompt: str, session_id: Optional[str], model: Optional[str], no_stream: bool, trace: Optional[bool]) -> None:
    """Run a single agentic task and exit."""
    if not _config.is_configured():
        render_error("Not configured. Run 'cowork chat' first to set up.")
        sys.exit(1)

    if model:
        _config.set("model_text", model)
    if no_stream:
        _config.set("stream", False)
    trace_enabled = _config.get("show_trace", False) if trace is None else trace

    session = Session.load(session_id) if session_id else Session(title="One-shot")
    if not session:
        session = Session(title="One-shot")
    ws = workspace_manager.ensure_for_session(session.session_id, title=session.title or "One-shot")
    session._ws = ws
    session.workspace_slug = ws.slug
    session.save()

    api_client = make_api_client()
    scratchpad = make_session_scratchpad(session.session_id)
    user_id = get_memory_user_id()
    memoria = Memoria(user_id, session.session_id, api_client, _config)

    render_user_message(prompt)

    async def _run() -> None:
        response, job = await run_agent_turn(
            user_input=prompt,
            session=session,
            api_client=api_client,
            scratchpad=scratchpad,
            memoria=memoria,
            trace_enabled=trace_enabled,
        )
        if trace_enabled and getattr(job, "trace_path", ""):
            console.print(f"  [dim_text]🧾 Trace saved: {job.trace_path}[/dim_text]")
        await api_client.close()

    asyncio.run(_run())
