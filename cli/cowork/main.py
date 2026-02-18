"""
🚀 Cowork CLI — Main Entry Point
The autonomous agentic coworker powered by the Makix Enterprise Architecture.

Usage:
    cowork                    # Start interactive session
    cowork chat               # Start interactive chat
    cowork run "your prompt"  # One-shot agent run
    cowork sessions           # List sessions
    cowork config             # Show/edit config
    cowork memory             # Show memory status
    cowork jobs               # Show job dashboard
"""

import asyncio
import os
import sys
import time
import uuid
from typing import Optional

import click
from rich.console import Console
from rich.rule import Rule

from .agent import GeneralPurposeAgent
from .api_client import APIClient, APIError
from .config import AgentJob, ConfigManager, JobManager, Scratchpad, Session
from .memoria import Memoria
from .ui import (
    ThinkingSpinner,
    StreamingRenderer,
    console,
    get_user_input,
    print_banner,
    print_welcome,
    render_config,
    render_error,
    render_help,
    render_job_dashboard,
    render_memory_status,
    render_response,
    render_routing_info,
    render_session_list,
    render_success,
    render_user_message,
    render_warning,
    run_setup_wizard,
)

# ─── Global State ─────────────────────────────────────────────────────────────
_config = ConfigManager()
_job_manager = JobManager(max_jobs=_config.get("max_concurrent_jobs", 10))
_last_trace: Optional[dict] = None
_last_job: Optional[AgentJob] = None


# ─── Async Agent Runner ───────────────────────────────────────────────────────

async def run_agent_turn(
    user_input: str,
    session: Session,
    api_client: APIClient,
    scratchpad: Scratchpad,
    memoria: Memoria,
    show_routing: bool = True,
) -> tuple[str, AgentJob]:
    """
    Execute one full agentic turn.
    Returns (response_text, job).
    """
    global _last_job

    # Register job with Sentinel
    job = AgentJob(
        session_id=session.session_id,
        prompt=user_input[:200],
    )
    if not _job_manager.register(job):
        return "⚠️  Job queue is full (max 10 concurrent jobs). Please wait.", job

    _job_manager.start(job.job_id)

    # Spinner + status tracking
    spinner = ThinkingSpinner("Cowork is thinking")
    stream_renderer = StreamingRenderer()
    status_messages: list[str] = []
    routing_info: Optional[dict] = None

    def on_status(msg: str) -> None:
        status_messages.append(msg)
        spinner.update(msg)

    def on_stream_token(token: str) -> None:
        stream_renderer.on_token(token)

    # Patch router to capture routing info
    original_classify = None

    start_time = time.time()
    spinner.start()

    try:
        agent = GeneralPurposeAgent(
            api_client=api_client,
            config=_config,
            scratchpad=scratchpad,
            memoria=memoria,
            job_manager=_job_manager,
            status_callback=on_status,
            stream_callback=on_stream_token,
        )

        # Capture routing decision for display
        original_classify = agent.router.classify

        async def patched_classify(prompt: str) -> dict:
            result = await original_classify(prompt)
            nonlocal routing_info
            routing_info = result
            return result

        agent.router.classify = patched_classify

        response = await agent.run(user_input, session, job)
        elapsed = time.time() - start_time

        spinner.stop()

        # Show routing info if available
        if show_routing and routing_info:
            render_routing_info(
                routing_info["categories"],
                routing_info["confidence"],
                routing_info.get("reasoning", ""),
            )

        # Render response
        render_response(response, elapsed, job.tool_calls, job.steps)

        _job_manager.complete(job.job_id, response)

        # Auto-generate title for new sessions
        if len(session.messages) == 0 and response:
            try:
                title = await agent.generate_title(session)
                session.title = title
            except Exception:
                pass

        # Save messages to session
        session.add_message("user", user_input)
        session.add_message("assistant", response)
        session.save()

        _last_job = job
        return response, job

    except APIError as e:
        spinner.stop()
        elapsed = time.time() - start_time
        error_msg = f"API Error after {elapsed:.1f}s: {e}"
        _job_manager.fail(job.job_id, str(e))
        render_error(str(e), hint="Check your API key and endpoint in /config")
        return error_msg, job
    except Exception as e:
        spinner.stop()
        _job_manager.fail(job.job_id, str(e))
        render_error(str(e))
        return str(e), job


# ─── Command Dispatcher ───────────────────────────────────────────────────────

async def handle_command(
    cmd: str,
    session: Session,
    api_client: APIClient,
    scratchpad: Scratchpad,
    memoria: Memoria,
    sessions_list: list[dict],
) -> tuple[bool, Optional[Session]]:
    """
    Handle slash commands.
    Returns (should_continue, new_session_if_changed).
    """
    parts = cmd.strip().split(maxsplit=2)
    command = parts[0].lower()

    if command in ("/exit", "/quit", "/q"):
        console.print()
        console.print(Rule(style="primary"))
        console.print("[primary]  👋 Goodbye! Your sessions are saved.[/primary]")
        console.print(Rule(style="primary"))
        console.print()
        return False, None

    elif command == "/help":
        render_help()

    elif command == "/clear":
        console.clear()
        print_banner()

    elif command == "/new":
        new_session = Session(title="New Session")
        new_session.save()
        render_success(f"✨ New session started: {new_session.session_id[:8]}")
        return True, new_session

    elif command == "/sessions":
        updated = Session.list_all()
        render_session_list(updated)

    elif command == "/load":
        if len(parts) < 2:
            render_error("Usage: /load <session_id_or_number>")
        else:
            target = parts[1]
            all_sessions = Session.list_all()
            loaded = None

            # Try by number
            if target.isdigit():
                idx = int(target) - 1
                if 0 <= idx < len(all_sessions):
                    loaded = Session.load(all_sessions[idx]["session_id"])
            else:
                # Try by partial ID
                for s in all_sessions:
                    if s["session_id"].startswith(target):
                        loaded = Session.load(s["session_id"])
                        break

            if loaded:
                render_success(f"📂 Loaded session: '{loaded.title}' ({len(loaded.messages)} messages)")
                return True, loaded
            else:
                render_error(f"Session '{target}' not found.")

    elif command == "/memory":
        if len(parts) > 1 and parts[1] == "clear":
            if click.confirm("Clear all memory for this user?", default=False):
                memoria.clear_all()
                render_success("🧹 Memory cleared.")
        else:
            render_memory_status(memoria.get_triplet_count(), memoria.get_summary())

    elif command == "/jobs":
        jobs = _job_manager.list_recent(20)
        render_job_dashboard(jobs)

    elif command == "/config":
        if len(parts) >= 3 and parts[1] == "set":
            # /config set key value
            rest = cmd.split(maxsplit=3)
            if len(rest) >= 4:
                key, value = rest[2], rest[3]
                # Try to cast to appropriate type
                try:
                    if value.lower() in ("true", "false"):
                        value = value.lower() == "true"
                    elif "." in value:
                        value = float(value)
                    else:
                        value = int(value)
                except (ValueError, AttributeError):
                    pass  # Keep as string
                _config.set(key, value)
                render_success(f"✅ Set {key} = {value}")
            else:
                render_error("Usage: /config set <key> <value>")
        else:
            render_config(_config.all())

    elif command == "/scratchpad":
        items = scratchpad.list_all()
        if not items:
            console.print("[muted]Scratchpad is empty.[/muted]")
        else:
            from rich.table import Table
            from rich import box
            table = Table(title="📝 Scratchpad", box=box.ROUNDED, border_style="memory")
            table.add_column("Key", style="highlight")
            table.add_column("Description", style="text")
            table.add_column("Size", style="muted", justify="right")
            table.add_column("Saved At", style="dim_text")
            for item in items:
                table.add_row(
                    item["key"],
                    item.get("description", "—"),
                    f"{item['size_chars']:,} chars",
                    item.get("saved_at", "")[:16],
                )
            console.print(table)

    elif command == "/trace":
        if _last_job:
            from rich.tree import Tree
            tree = Tree(f"[primary]🔍 Trace: Job {_last_job.job_id}[/primary]")
            tree.add(f"[muted]Status:[/muted] {_last_job.status}")
            tree.add(f"[muted]Steps:[/muted] {_last_job.steps}")
            tree.add(f"[muted]Tool Calls:[/muted] {_last_job.tool_calls}")
            tree.add(f"[muted]Categories:[/muted] {', '.join(_last_job.categories)}")
            tree.add(f"[muted]Prompt:[/muted] {_last_job.prompt[:80]}...")
            console.print(tree)
        else:
            console.print("[muted]No trace available yet.[/muted]")

    else:
        render_warning(f"Unknown command: {command}. Type /help for available commands.")

    return True, None


# ─── Interactive Chat Loop ────────────────────────────────────────────────────

async def interactive_loop(
    session: Session,
    api_client: APIClient,
) -> None:
    """Main interactive REPL loop."""
    scratchpad = Scratchpad(session.session_id)
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, _config.api_key or "anonymous"))
    memoria = Memoria(user_id, session.session_id, api_client, _config)

    sessions_list = Session.list_all()

    # Show ghost job warning
    ghost_jobs = _job_manager.get_ghost_jobs()
    if ghost_jobs:
        render_warning(
            f"⚠️  Found {len(ghost_jobs)} interrupted job(s) from a previous session. "
            "Type /jobs to review."
        )

    console.print("[dim_text]  Type your message or use /help for commands. Press Ctrl+C to exit.[/dim_text]")
    console.print()

    while True:
        try:
            user_input = get_user_input(session.title)
        except (KeyboardInterrupt, EOFError):
            user_input = "/exit"

        if not user_input:
            continue

        # Slash command
        if user_input.startswith("/"):
            should_continue, new_session = await handle_command(
                user_input, session, api_client, scratchpad, memoria, sessions_list
            )
            if not should_continue:
                break
            if new_session:
                session = new_session
                scratchpad = Scratchpad(session.session_id)
                memoria = Memoria(user_id, session.session_id, api_client, _config)
            continue

        # Hashtag detection (Action Pills)
        action_mode = None
        if "#research" in user_input.lower():
            action_mode = {"categories": ["SEARCH_AND_INFO"], "pill": "#research"}
        elif "#task" in user_input.lower() or "#kanban" in user_input.lower():
            action_mode = {"categories": ["APP_CONNECTORS"], "pill": "#task"}
        elif "#calc" in user_input.lower() or "#math" in user_input.lower():
            action_mode = {"categories": ["DATA_AND_UTILITY"], "pill": "#calc"}
        elif "#note" in user_input.lower():
            action_mode = {"categories": ["APP_CONNECTORS"], "pill": "#note"}

        if action_mode:
            console.print(f"  [accent]⚡ Action Pill detected: {action_mode['pill']}[/accent]")

        # Render user message
        render_user_message(user_input)

        # Run agent
        response, job = await run_agent_turn(
            user_input=user_input,
            session=session,
            api_client=api_client,
            scratchpad=scratchpad,
            memoria=memoria,
            show_routing=True,
        )

        # Cleanup old jobs periodically
        _job_manager.cleanup_completed(keep=50)


# ─── CLI Commands ─────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    🤖 Cowork — Makix Enterprise Agentic CLI Coworker

    A powerful autonomous AI agent with Manager-Worker architecture,
    long-term memory, meta-routing, and parallel tool execution.
    """
    if ctx.invoked_subcommand is None:
        # Default: start interactive chat
        ctx.invoke(chat)


@cli.command()
@click.option("--session-id", "-s", default=None, help="Resume a specific session by ID")
@click.option("--no-banner", is_flag=True, default=False, help="Skip the banner")
def chat(session_id: Optional[str], no_banner: bool) -> None:
    """Start an interactive agentic chat session."""
    if not no_banner:
        print_banner()

    if not _config.is_configured():
        if not run_setup_wizard(_config):
            sys.exit(1)

    print_welcome(_config)

    # Load or create session
    if session_id:
        session = Session.load(session_id)
        if not session:
            render_error(f"Session '{session_id}' not found.")
            session = Session(title="New Session")
    else:
        session = Session(title="New Session")
        session.save()

    api_client = APIClient(
        endpoint=_config.api_endpoint,
        api_key=_config.api_key,
    )

    try:
        asyncio.run(interactive_loop(session, api_client))
    except KeyboardInterrupt:
        console.print()
        console.print("[primary]  👋 Session saved. Goodbye![/primary]")
    finally:
        asyncio.run(api_client.close())


@cli.command()
@click.argument("prompt")
@click.option("--session-id", "-s", default=None, help="Session ID to use")
@click.option("--model", "-m", default=None, help="Override model")
@click.option("--no-stream", is_flag=True, default=False, help="Disable streaming")
def run(prompt: str, session_id: Optional[str], model: Optional[str], no_stream: bool) -> None:
    """Run a single agentic task and exit."""
    if not _config.is_configured():
        render_error("Not configured. Run 'cowork chat' first to set up.")
        sys.exit(1)

    if model:
        _config.set("model_text", model)
    if no_stream:
        _config.set("stream", False)

    session = Session.load(session_id) if session_id else Session(title="One-shot")
    if not session:
        session = Session(title="One-shot")

    api_client = APIClient(endpoint=_config.api_endpoint, api_key=_config.api_key)
    scratchpad = Scratchpad(session.session_id)
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, _config.api_key or "anonymous"))
    memoria = Memoria(user_id, session.session_id, api_client, _config)

    render_user_message(prompt)

    async def _run() -> None:
        response, job = await run_agent_turn(
            user_input=prompt,
            session=session,
            api_client=api_client,
            scratchpad=scratchpad,
            memoria=memoria,
        )
        await api_client.close()

    asyncio.run(_run())


@cli.command()
def sessions() -> None:
    """List all saved sessions."""
    print_banner()
    all_sessions = Session.list_all()
    render_session_list(all_sessions)


@cli.command()
@click.option("--set", "set_values", nargs=2, multiple=True, metavar="KEY VALUE", help="Set a config value")
def config(set_values: tuple) -> None:
    """Show or update configuration."""
    print_banner()
    if set_values:
        for key, value in set_values:
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
            render_success(f"Set {key} = {value}")
    else:
        render_config(_config.all())


@cli.command()
def memory() -> None:
    """Show Memoria (long-term memory) status."""
    print_banner()
    if not _config.is_configured():
        render_error("Not configured.")
        return
    api_client = APIClient(endpoint=_config.api_endpoint, api_key=_config.api_key)
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, _config.api_key or "anonymous"))
    mem = Memoria(user_id, "status_check", api_client, _config)
    render_memory_status(mem.get_triplet_count(), mem.get_summary())

    # Show RAG mode
    if mem.is_semantic_search_available():
        console.print(
            "  [green]🔍 Local RAG:[/green] [dim]sqlite-vec + all-MiniLM-L6-v2 (semantic search active)[/dim]"
        )
    else:
        console.print(
            "  [yellow]🔍 Local RAG:[/yellow] [dim]keyword fallback "
            "(install sentence-transformers + sqlite-vec for semantic search)[/dim]"
        )


@cli.command()
def jobs() -> None:
    """Show the Sentinel job queue dashboard."""
    print_banner()
    recent = _job_manager.list_recent(20)
    render_job_dashboard(recent)


@cli.command()
def setup() -> None:
    """Run the interactive setup wizard."""
    print_banner()
    run_setup_wizard(_config)


@cli.command()
def ping() -> None:
    """Test connectivity to the configured API endpoint."""
    print_banner()
    if not _config.is_configured():
        render_error("Not configured. Run 'cowork setup' first.")
        return

    api_client = APIClient(endpoint=_config.api_endpoint, api_key=_config.api_key)

    async def _ping() -> None:
        console.print(f"[muted]Pinging {_config.api_endpoint}...[/muted]")
        ok = await api_client.ping()
        if ok:
            render_success(f"✅ Connected to {_config.api_endpoint}")
            models = await api_client.list_models()
            if models:
                console.print(f"[muted]Available models: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}[/muted]")
        else:
            render_error(f"Cannot reach {_config.api_endpoint}", hint="Check your endpoint URL and network connection.")
        await api_client.close()

    asyncio.run(_ping())


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
