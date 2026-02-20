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
    cowork tokens             # Show token usage per model/endpoint
    cowork ai                 # Manage AI profiles (endpoints/models)
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from .agent import GeneralPurposeAgent
from .api_client import APIClient, APIError
from .config import (
    CONFIG_DIR,
    AgentJob,
    AIProfileManager,
    ConfigManager,
    JobManager,
    Scratchpad,
    Session,
    TokenTracker,
    is_sensitive_key,
)
from .cron import CronManager
from .memoria import Memoria
from .workspace import WorkspaceSession, workspace_manager, WORKSPACE_ROOT
from .tools import get_all_available_tools
from .tracing import (
    WorkflowTraceLogger,
    find_latest_trace_file,
    load_trace_events,
    render_trace_timeline,
)
from .ui import (
    ThinkingSpinner,
    StreamingRenderer,
    confirm_tool_call,
    console,
    get_user_input,
    print_banner,
    print_welcome,
    render_ai_profiles,
    render_config,
    render_cron_list,
    render_error,
    render_help,
    render_job_dashboard,
    render_memory_status,
    render_response,
    render_routing_info,
    render_session_list,
    render_success,
    render_model_list,
    render_token_usage,
    render_tools_list,
    render_user_message,
    render_warning,
    run_setup_wizard,
)
from rich.tree import Tree
from rich.syntax import Syntax

# ─── Global State ─────────────────────────────────────────────────────────────
_config = ConfigManager()
_job_manager = JobManager(max_jobs=_config.get("max_concurrent_jobs", 10))
_token_tracker = TokenTracker()
_ai_profiles = AIProfileManager(_config)
_last_trace: Optional[dict] = None
_last_job: Optional[AgentJob] = None


def _reset_all_cowork_state() -> None:
    """
    Wipe all persisted Cowork state under ~/.cowork/* and recreate root dirs.
    """
    import shutil

    if CONFIG_DIR.exists():
        for p in CONFIG_DIR.iterdir():
            try:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
            except Exception:
                pass
    CONFIG_DIR.mkdir(exist_ok=True)
    (CONFIG_DIR / "sessions").mkdir(exist_ok=True)
    (CONFIG_DIR / "scratchpad").mkdir(exist_ok=True)

def _make_api_client() -> "APIClient":
    """Create an APIClient wired to the global token tracker."""
    def _token_cb(model: str, usage: dict) -> None:
        _token_tracker.record(_config.api_endpoint, model, usage)
    return APIClient(
        endpoint=_config.api_endpoint,
        api_key=_config.api_key,
        token_callback=_token_cb,
        request_delay_ms=_config.get("request_delay_ms", 0),
        max_retries=_config.get("max_retries", 5),
        retry_base_delay=_config.get("retry_base_delay", 2.0),
    )


# ─── Async Agent Runner ───────────────────────────────────────────────────────

async def run_agent_turn(
    user_input: str,
    session: Session,
    api_client: APIClient,
    scratchpad: Scratchpad,
    memoria: Memoria,
    action_mode: Optional[dict] = None,
    show_routing: bool = True,
    unattended: bool = False,
    trace_enabled: bool = False,
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
    trace_logger = WorkflowTraceLogger(
        enabled=trace_enabled,
        session_id=session.session_id,
        job_id=job.job_id,
        workspace_path=getattr(getattr(session, "_ws", None), "path", None),
    )
    if trace_logger.file_path:
        job.trace_path = str(trace_logger.file_path)

    # Spinner + status tracking
    spinner = ThinkingSpinner("Cowork is thinking")
    stream_renderer = StreamingRenderer()
    status_messages: list[str] = []
    routing_info: Optional[dict] = None

    # Patch router to capture routing info
    original_classify = None

    def on_status(msg: str) -> None:
        status_messages.append(msg)
        if not unattended:
            spinner.update(msg)

    def on_stream_token(token: str) -> None:
        if not unattended:
            stream_renderer.on_token(token)

    start_time = time.time()
    if not unattended:
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
            trace_callback=trace_logger.log,
        )

        # Capture routing decision for display
        original_classify = agent.router.classify

        async def patched_classify(prompt: str) -> dict:
            result = await original_classify(prompt)
            nonlocal routing_info
            routing_info = result
            return result

        async def on_confirm(name: str, reason: str, args: dict) -> bool:
            if unattended:
                # In unattended mode, we cannot ask for permission.
                # Default to blocking 'ask' tools for safety.
                nonlocal status_messages
                msg = f"🛡️ [UNATTENDED] Firewall blocked tool '{name}' (reason: {reason})"
                status_messages.append(msg)
                if not unattended: # Double check logic flow
                     spinner.update(msg)
                return False

            # Need to stop spinner before asking
            was_running = spinner._live is not None
            if was_running:
                spinner.stop()
            
            # Use run_in_executor for the synchronous UI prompt
            res = await asyncio.get_event_loop().run_in_executor(
                None, confirm_tool_call, name, reason, args
            )
            
            if was_running:
                spinner.start()
            return res

        agent.router.classify = patched_classify
        agent.confirm_cb = on_confirm

        response = await agent.run(user_input, session, job, action_mode=action_mode)
        elapsed = time.time() - start_time

        if not unattended:
            spinner.stop()

        # Show routing info if available
        if show_routing and routing_info:
            render_routing_info(
                routing_info["categories"],
                routing_info["confidence"],
                routing_info.get("reasoning", ""),
            )

        # Render response
        if not unattended:
            render_response(response, elapsed, job.tool_calls, job.steps)

        _job_manager.complete(job.job_id, response)

        # Save messages to session
        session.add_message("user", user_input)
        session.add_message("assistant", response)
        session.save()

        # Auto-generate title for new sessions (on first exchange)
        if len(session.messages) == 2 and response:
            try:
                title = await agent.generate_title(session)
                if title and title != "New Session":
                    session.title = title
                    # Rename workspace session folder to match the generated title
                    if hasattr(session, '_ws') and session._ws:
                        ws = session._ws
                        old_slug = ws.slug
                        new_ws = workspace_manager.rename(old_slug, title)
                        if new_ws:
                            session._ws = new_ws
            except Exception:
                pass

        # Sync to workspace session
        if hasattr(session, '_ws') and session._ws:
            ws = session._ws
            ws.messages = session.messages
            ws.title = session.title
            ws.summary = session.summary
            ws.save()

        _last_job = job
        trace_logger.close(
            {
                "status": "completed",
                "job_id": job.job_id,
                "steps": job.steps,
                "tool_calls": job.tool_calls,
                "trace_path": getattr(job, "trace_path", ""),
            }
        )
        global _last_trace
        _last_trace = {"path": getattr(job, "trace_path", ""), "job_id": job.job_id}
        return response, job

    except APIError as e:
        if not unattended:
            spinner.stop()
        elapsed = time.time() - start_time
        error_msg = f"API Error after {elapsed:.1f}s: {e}"
        _job_manager.fail(job.job_id, str(e))
        trace_logger.log("turn_error", {"type": "api_error", "error": str(e)})
        trace_logger.close({"status": "failed", "job_id": job.job_id, "error": str(e)})
        if not unattended:
            render_error(str(e), hint="Check your API key and endpoint in /config")
        return error_msg, job
    except Exception as e:
        if not unattended:
            spinner.stop()
        _job_manager.fail(job.job_id, str(e))
        trace_logger.log("turn_error", {"type": "exception", "error": str(e)})
        trace_logger.close({"status": "failed", "job_id": job.job_id, "error": str(e)})
        if not unattended:
            render_error(str(e))
        return str(e), job


async def _background_cron_poll():
    """Periodically check and run pending cron jobs while the app is open."""
    mgr = CronManager()
    api_client = _make_api_client()
    try:
        while True:
            pending = mgr.get_pending_jobs()
            for job in pending:
                # Load or create session for the job
                session = Session.load(job.session_id) if job.session_id else Session(title=f"Cron: {job.job_id}")
                if not session:
                    session = Session(title=f"Cron: {job.job_id}")
                
                scratchpad = Scratchpad(session.session_id)
                user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, _config.api_key or "anonymous"))
                memoria = Memoria(user_id, session.session_id, api_client, _config)

                response, _ = await run_agent_turn(
                    user_input=job.prompt,
                    session=session,
                    api_client=api_client,
                    scratchpad=scratchpad,
                    memoria=memoria,
                    show_routing=False,
                    unattended=True,
                )
                mgr.mark_run(job.job_id, result=response)
                render_success(f"🔔 Background Job Completed: {job.job_id}")
            
            await asyncio.sleep(60)
    except Exception:
        pass
    finally:
        await api_client.close()


# ─── Command Dispatcher ───────────────────────────────────────────────────────

async def handle_command(
    cmd: str,
    session: Session,
    api_client: APIClient,
    scratchpad: Scratchpad,
    memoria: Memoria,
    sessions_list: list[dict],
) -> tuple[bool, Optional[Session], bool]:
    """
    Handle slash commands.
    Returns (should_continue, new_session_if_changed, needs_rebuild).
    """
    parts = cmd.strip().split(maxsplit=2)
    command = parts[0].lower()
    needs_rebuild = False

    if command in ("/exit", "/quit", "/q"):
        console.print()
        console.print(Rule(style="primary"))
        console.print("[primary]  👋 Goodbye! Your sessions are saved.[/primary]")
        console.print(Rule(style="primary"))
        console.print()
        return False, None, False

    elif command == "/help":
        render_help()

    elif command == "/clear":
        console.clear()
        print_banner()

    elif command == "/new":
        new_session = Session(title="New Session")
        new_session.save()
        # Create matching workspace session
        ws = workspace_manager.create("New Session")
        new_session._ws = ws
        # Point scratchpad to workspace folder
        new_scratchpad = Scratchpad.__new__(Scratchpad)
        new_scratchpad.session_id = new_session.session_id
        new_scratchpad._dir = ws.scratchpad_path
        new_scratchpad._dir.mkdir(exist_ok=True)
        new_scratchpad._index = {}
        new_scratchpad._load_index()
        render_success(
            f"✨ New session started: {new_session.session_id[:8]}\n"
            f"📂 Workspace: workspace/{ws.slug}/"
        )
        return True, new_session, False

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
                # Try to link workspace session
                for ws_info in workspace_manager.list_all():
                    if ws_info["session_id"] == loaded.session_id:
                        ws = WorkspaceSession.load(ws_info["slug"])
                        if ws:
                            loaded._ws = ws
                            render_success(f"📂 Workspace: workspace/{ws.slug}/")
                        break
                return True, loaded, False
            else:
                render_error(f"Session '{target}' not found.")

    elif command == "/sessions":
        updated = Session.list_all()
        render_session_list(updated)

    elif command == "/jobs":
        sub = parts[1].lower() if len(parts) > 1 else ""
        if sub == "clean":
            if click.confirm("Wipe all job history?", default=False):
                _job_manager.clear_all()
                render_success("🧹 Job history cleared.")
        elif sub == "resume":
            if len(parts) < 3:
                render_error("Usage: /jobs resume <job_id>")
            else:
                job_id = parts[2]
                job = _job_manager.get_job(job_id)
                if job:
                    render_success(f"🚀 Resuming job {job.job_id}: [dim_text]{job.prompt}[/dim_text]")
                    # Recursive call to run_agent_turn
                    await run_agent_turn(
                        user_input=job.prompt,
                        session=session,
                        api_client=api_client,
                        scratchpad=scratchpad,
                        memoria=memoria,
                    )
                else:
                    render_error(f"Job '{job_id}' not found.")
        else:
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
                shown_value = "●●●●●●●●" if is_sensitive_key(key) and value else value
                render_success(f"✅ Set {key} = {shown_value}")
            else:
                render_error("Usage: /config set <key> <value>")
        else:
            render_config(_config.all())

    elif command == "/scratchpad":
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
                    render_error(f"Scratchpad number out of range: {target}", hint="Use /scratchpad to list valid numbers.")
                    return True, None, needs_rebuild
                item = items[idx - 1]
                display_ref = f"ref:{item['key']}"
                content = scratchpad.get(item["key"])
            else:
                content = scratchpad.get(target)
                display_ref = f"ref:{target.replace('ref:', '')}"

            if content is None:
                render_error(f"Scratchpad item not found: {target}", hint="Use /scratchpad to list item numbers.")
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

    elif command == "/workspace":
        from rich.table import Table
        from rich import box
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
                        console.print(f"    [dim_text]• {m}[/dim_text]")
        elif sub == "open":
            ws = getattr(session, '_ws', None)
            if ws:
                console.print(f"  [success]📂 Session workspace:[/success] [highlight]{ws.path}[/highlight]")
            else:
                console.print(f"  [muted]📂 Workspace root:[/muted] [highlight]{WORKSPACE_ROOT}[/highlight]")
        elif sub == "clean":
            if click.confirm("⚠️  Are you sure you want to delete ALL sessions and workspace folders? This cannot be undone.", default=False):
                with ThinkingSpinner("Cleaning workspace"):
                    # 1. Clear workspace folders
                    ws_count = workspace_manager.clear_all()
                    
                    # 2. Clear regular sessions
                    from .config import SESSIONS_DIR, SCRATCHPAD_DIR
                    import shutil
                    s_count = 0
                    for p in SESSIONS_DIR.glob("*.json"):
                        p.unlink()
                        s_count += 1
                    
                    # 3. Clear scratchpads
                    for p in SCRATCHPAD_DIR.iterdir():
                        if p.is_dir():
                            shutil.rmtree(p)
                
                render_success(f"🧹 Workspace cleaned. Deleted {ws_count} workspace folders and {s_count} session files.")
                # We should probably reset the current session too
                new_session = Session(title="New Session")
                new_session.save()
                ws = workspace_manager.create("New Session")
                new_session._ws = ws
                return True, new_session, False
        else:
            ws = getattr(session, '_ws', None)
            if ws:
                console.print(f"  [success]📂 Current session workspace:[/success] [highlight]{ws.path}[/highlight]")
                ctx = ws.read_context()
                if ctx:
                    from rich.markdown import Markdown
                    console.print(Markdown(ctx[:1000]))
            else:
                console.print(f"  [muted]No workspace session linked. Use /new to create one.[/muted]")
            console.print()
            console.print("[dim_text]  /workspace list          — list all sessions[/dim_text]")
            console.print("[dim_text]  /workspace search <q>    — search across sessions[/dim_text]")
            console.print("[dim_text]  /workspace open          — show current session path[/dim_text]")
            console.print("[dim_text]  /workspace clean         — delete all sessions and workspace folders[/dim_text]")

    elif command == "/trace":
        sub = parts[1].lower() if len(parts) > 1 else ""
        if sub in ("full", "raw", "path"):
            target_path = ""
            if len(parts) > 2:
                target_path = parts[2]
            elif _last_job and getattr(_last_job, "trace_path", ""):
                target_path = _last_job.trace_path
            else:
                latest = find_latest_trace_file(session.session_id)
                if latest:
                    target_path = str(latest)

            if not target_path:
                console.print("[muted]No trace file available yet.[/muted]")
            else:
                p = Path(target_path)
                events = load_trace_events(p)
                if not events:
                    console.print(f"[muted]Trace is empty or unreadable: {p}[/muted]")
                elif sub == "path":
                    console.print(f"[highlight]{p}[/highlight]")
                elif sub == "raw":
                    console.print(Syntax("\n".join(json.dumps(e, ensure_ascii=False) for e in events), "json", theme="monokai", background_color="default"))
                else:
                    console.print(
                        render_trace_timeline(
                            events,
                            full=True,
                            max_value_chars=12000,
                            trace_file=str(p),
                        )
                    )
            return True, None, needs_rebuild

        if _last_job:
            tree = Tree(f"[primary]🔍 Trace: Job {_last_job.job_id}[/primary]")
            tree.add(f"[muted]Status:[/muted] {_last_job.status}")
            tree.add(f"[muted]Steps:[/muted] {_last_job.steps}")
            tree.add(f"[muted]Tool Calls:[/muted] {_last_job.tool_calls}")
            if getattr(_last_job, "trace_path", ""):
                tree.add(f"[muted]Trace File:[/muted] {_last_job.trace_path}")
            
            if hasattr(_last_job, "tool_calls_list") and _last_job.tool_calls_list:
                tools_tree = tree.add("[tool]🛠️  Tool Execution History[/tool]")
                for i, tc in enumerate(_last_job.tool_calls_list, 1):
                    status_color = "success" if tc.get("status") == "success" else "error"
                    tc_node = tools_tree.add(f"#{i} [{status_color}]{tc['name']}[/{status_color}]")
                    if tc.get("args"):
                        import json
                        args_str = json.dumps(tc["args"], indent=2)
                        tc_node.add(Syntax(args_str, "json", theme="monokai", background_color="default"))
            
            tree.add(f"[muted]Categories:[/muted] {', '.join(_last_job.categories)}")
            tree.add(f"[muted]Prompt:[/muted] {_last_job.prompt[:80]}...")
            console.print(tree)
        else:
            console.print("[muted]No trace available yet.[/muted]")

    elif command == "/tokens":
        if len(parts) > 1 and parts[1] == "reset":
            if click.confirm("Reset all token usage counters?", default=False):
                _token_tracker.reset()
                render_success("🧹 Token usage counters reset.")
        else:
            render_token_usage(_token_tracker.get_all(), _token_tracker.get_totals())

    elif command == "/cron":
        mgr = CronManager()
        sub = parts[1].lower() if len(parts) > 1 else ""
        if sub == "list" or not sub:
            render_cron_list(mgr.list_all())
        elif sub == "view":
            if len(parts) < 3:
                render_error("Usage: /cron view <job_id>")
            else:
                job_id = parts[2]
                all_jobs = mgr.list_all()
                found = next((j for j in all_jobs if j.job_id == job_id), None)
                if found:
                    from .ui import render_cron_result
                    render_cron_result(found)
                else:
                    render_error(f"Cron job '{job_id}' not found.")
        elif sub == "rm" or sub == "delete":
            if len(parts) < 3:
                render_error("Usage: /cron rm <job_id>")
            else:
                if mgr.remove_job(parts[2]):
                    render_success(f"🗑️  Cron job '{parts[2]}' removed.")
                else:
                    render_error(f"Cron job '{parts[2]}' not found.")
        else:
            render_cron_list(mgr.list_all())

    elif command == "/memory":
        sub = parts[1].lower() if len(parts) > 1 else ""
        if not sub or sub == "list" or sub == "view":
            from .ui import render_memory_dashboard
            render_memory_dashboard(memoria.get_summary(), memoria.get_all_triplets())
        elif sub == "rm":
            if len(parts) < 3:
                render_error("Usage: /memory rm <id>")
            else:
                if memoria.delete_triplet(parts[2]):
                    render_success(f"🗑️  Memory fact '{parts[2]}' deleted.")
                else:
                    # Try partial match (the UI shows short IDs)
                    all_t = memoria.get_all_triplets()
                    found = [t for t in all_t if t["id"].startswith(parts[2])]
                    if len(found) == 1:
                        memoria.delete_triplet(found[0]["id"])
                        render_success(f"🗑️  Memory fact '{found[0]['id'][:8]}' deleted.")
                    elif len(found) > 1:
                        render_error(f"Multiple matches for '{parts[2]}'. Be more specific.")
                    else:
                        render_error(f"Memory fact '{parts[2]}' not found.")
        elif sub == "clear":
            if click.confirm("Are you sure you want to clear ALL persona and session memory?", default=False):
                memoria.clear_all()
                render_success("🧹 Memory wiped clean.")
        elif sub == "summarize":
            # Just show the summary in a dedicated panel
            from .ui import render_memory_dashboard
            render_memory_dashboard(memoria.get_summary(), [])
        else:
            from .ui import render_memory_dashboard
            render_memory_dashboard(memoria.get_summary(), memoria.get_all_triplets())

    elif command == "/tools":
        render_tools_list(get_all_available_tools())

    elif command == "/reset":
        if click.confirm("⚠️  This will permanently delete ALL data in ~/.cowork/* . Continue?", default=False):
            with ThinkingSpinner("Resetting Cowork state"):
                _reset_all_cowork_state()
            render_success("🧹 Reset complete. All ~/.cowork/* data has been deleted.")
            return False, None, False

    elif command == "/ai":
        sub = parts[1].lower() if len(parts) > 1 else ""

        if not sub or sub == "list":
            render_ai_profiles(_ai_profiles.list_all())

        elif sub == "add":
            # /ai add <name> <endpoint> <model> [description...]
            raw = cmd.split(maxsplit=5)
            if len(raw) < 5:
                render_error(
                    "Usage: /ai add <name> <endpoint> <model> [description]",
                    hint="Example: /ai add gpt4 https://api.openai.com/v1 gpt-4o My GPT-4 profile",
                )
            else:
                name, endpoint, model = raw[2], raw[3], raw[4]
                description = raw[5] if len(raw) > 5 else ""
                _ai_profiles.add(name=name, endpoint=endpoint, model=model, description=description)
                render_success(f"✅ AI profile '{name}' saved ({model} @ {endpoint})")

        elif sub == "switch":
            if len(parts) < 3:
                render_error("Usage: /ai switch <name>")
            else:
                name = parts[2]
                profile = _ai_profiles.switch(name)
                if profile:
                    render_success(
                        f"🤖 Switched to profile '[highlight]{name}[/highlight]'\n"
                        f"   Model: {profile.model}\n"
                        f"   Endpoint: {profile.endpoint}"
                    )
                    needs_rebuild = True
                else:
                    render_error(f"Profile '{name}' not found.", hint="Use /ai to list available profiles.")

        elif sub == "remove":
            if len(parts) < 3:
                render_error("Usage: /ai remove <name>")
            else:
                name = parts[2]
                if _ai_profiles.remove(name):
                    render_success(f"🗑️  Profile '{name}' removed.")
                else:
                    render_error(f"Profile '{name}' not found.")

        elif sub == "save":
            name = parts[2] if len(parts) > 2 else "default"
            _ai_profiles.snapshot_current(_config, name)
            render_success(
                f"💾 Saved current config as profile '[highlight]{name}[/highlight]'\n"
                f"   Model: {_config.model_text}\n"
                f"   Endpoint: {_config.api_endpoint}"
            )
        else:
            render_warning(f"Unknown /ai subcommand: {sub}. Use /ai, /ai add, /ai switch, /ai remove, /ai save.")

    elif command == "/model":
        if len(parts) > 1:
            # /model <name>
            new_model = parts[1]
            _config.set("model_text", new_model)
            _config.set("model_router", new_model)
            _config.set("model_compress", new_model)
            render_success(f"🤖 Model switched to: [highlight]{new_model}[/highlight]")
            needs_rebuild = True
        else:
            # /model (list)
            with ThinkingSpinner("Fetching models"):
                models = await api_client.list_models()
            render_model_list(models, _config.model_text)

    elif command == "/mm":
        # /mm [status|vision|images|asr|tts] [endpoint <url>|token <key>|model <name>]
        # Re-split to get up to 4 tokens: /mm <service> <field> <value>
        mm_parts = cmd.strip().split(maxsplit=3)
        sub = mm_parts[1].lower() if len(mm_parts) > 1 else "status"
        MM_SERVICES = {
            "vision": ("mm_vision_endpoint", "mm_vision_token", "mm_vision_model", "👁️  Vision (Image Analysis)"),
            "images": ("mm_image_endpoint",  "mm_image_token",  "mm_image_model",  "🎨 Image Generation"),
            "asr":    ("mm_asr_endpoint",    "mm_asr_token",    "mm_asr_model",    "🎤 Speech-to-Text (ASR)"),
            "tts":    ("mm_tts_endpoint",    "mm_tts_token",    "mm_tts_model",    "🔊 Text-to-Speech (TTS)"),
        }
        if sub == "status" or sub not in MM_SERVICES:
            from rich.table import Table
            from rich import box
            table = Table(title="🎨 Multi-Modal Services", box=box.ROUNDED, border_style="primary")
            table.add_column("Service", style="highlight", min_width=28)
            table.add_column("Endpoint", style="text")
            table.add_column("Model", style="muted")
            table.add_column("Token", style="success", justify="center")
            for svc_key, (ep_key, tok_key, mdl_key, label) in MM_SERVICES.items():
                ep  = _config.get(ep_key, "") or ""
                tok = _config.get(tok_key, "") or ""
                mdl = _config.get(mdl_key, "") or ""
                table.add_row(
                    label,
                    ep[:50] if ep else "[muted]—[/muted]",
                    mdl if mdl else "[muted]—[/muted]",
                    "✅" if (ep and tok) else "❌",
                )
            console.print(table)
            console.print()
            console.print("[dim_text]  Usage:[/dim_text]")
            console.print("[dim_text]  /mm vision endpoint <url>   — set vision endpoint[/dim_text]")
            console.print("[dim_text]  /mm vision token <key>      — set vision API key[/dim_text]")
            console.print("[dim_text]  /mm vision model <name>     — set vision model[/dim_text]")
            console.print("[dim_text]  /mm images|asr|tts ...      — same for other services[/dim_text]")
        elif sub in MM_SERVICES:
            ep_key, tok_key, mdl_key, label = MM_SERVICES[sub]
            if len(mm_parts) < 4:
                render_error(
                    f"Usage: /mm {sub} <endpoint|token|model> <value>",
                    hint=f"Example: /mm {sub} endpoint https://api.openai.com/v1",
                )
            else:
                field = mm_parts[2].lower()
                value = mm_parts[3].strip() if len(mm_parts) > 3 else ""
                if field == "endpoint":
                    _config.set(ep_key, value.rstrip("/"))
                    render_success(f"✅ {label} endpoint set to: {value}")
                elif field in ("token", "key"):
                    # Sensitive — kept in memory only (not written to config.json)
                    _config.set(tok_key, value)
                    render_success(f"✅ {label} token updated. (stored in memory, not persisted to disk)")
                elif field == "model":
                    _config.set(mdl_key, value)
                    render_success(f"✅ {label} model set to: {value}")
                else:
                    render_error(f"Unknown field '{field}'. Use: endpoint, token, model.")

    else:
        render_warning(f"Unknown command: {command}. Type /help for available commands.")

    return True, None, needs_rebuild


# ─── Interactive Chat Loop ────────────────────────────────────────────────────

async def interactive_loop(
    session: Session,
    api_client: APIClient,
    trace_enabled: bool = False,
) -> None:
    """Main interactive REPL loop."""
    scratchpad_session_id = session.session_id
    # Use workspace scratchpad folder if available
    ws = getattr(session, '_ws', None)
    if ws:
        scratchpad = Scratchpad.__new__(Scratchpad)
        scratchpad.session_id = session.session_id
        scratchpad._dir = ws.scratchpad_path
        scratchpad._dir.mkdir(exist_ok=True)
        scratchpad._index = {}
        scratchpad._load_index()
    else:
        scratchpad = Scratchpad(session.session_id)
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, _config.api_key or "anonymous"))
    _memoria = Memoria(user_id, session.session_id, api_client, _config)

    sessions_list = Session.list_all()

    # Start background scheduler
    poll_task = asyncio.create_task(_background_cron_poll())

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
                api_client = _make_api_client()
                _memoria.api_client = api_client

            if new_session:
                session = new_session
                # Use workspace scratchpad if available
                ws = getattr(session, '_ws', None)
                if ws:
                    scratchpad = Scratchpad.__new__(Scratchpad)
                    scratchpad.session_id = session.session_id
                    scratchpad._dir = ws.scratchpad_path
                    scratchpad._dir.mkdir(exist_ok=True)
                    scratchpad._index = {}
                    scratchpad._load_index()
                else:
                    scratchpad = Scratchpad(session.session_id)
                _memoria = Memoria(user_id, session.session_id, api_client, _config)
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
        elif "#cron" in user_input.lower() or "#schedule" in user_input.lower():
            action_mode = {"categories": ["CRON_TOOLS"], "pill": "#cron"}
        elif "#email" in user_input.lower() or "#comms" in user_input.lower():
            action_mode = {"categories": ["COMMUNICATION_TOOLS"], "pill": "#email"}
        elif "#coding" in user_input.lower() or "#code" in user_input.lower() or "#web" in user_input.lower():
            action_mode = {"categories": ["CODING_TOOLS", "WORKSPACE_TOOLS"], "pill": "#coding"}

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
            memoria=_memoria,
            action_mode=action_mode,
            show_routing=True,
            trace_enabled=trace_enabled,
        )
        if trace_enabled and getattr(job, "trace_path", ""):
            console.print(f"  [dim_text]🧾 Trace saved: {job.trace_path}[/dim_text]")

        # Workspace can be renamed after title generation; rebind scratchpad path if it moved.
        ws = getattr(session, "_ws", None)
        if ws and getattr(scratchpad, "_dir", None) != ws.scratchpad_path:
            scratchpad = Scratchpad.__new__(Scratchpad)
            scratchpad.session_id = session.session_id
            scratchpad._dir = ws.scratchpad_path
            scratchpad._dir.mkdir(exist_ok=True)
            scratchpad._index = {}
            scratchpad._load_index()

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
@click.option("--trace/--no-trace", default=None, help="Enable full workflow trace logs")
def chat(session_id: Optional[str], no_banner: bool, trace: Optional[bool]) -> None:
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
        # Try to link workspace session
        for ws_info in workspace_manager.list_all():
            if ws_info["session_id"] == session.session_id:
                ws = WorkspaceSession.load(ws_info["slug"])
                if ws:
                    session._ws = ws
                    console.print(f"  [dim_text]📂 Workspace: workspace/{ws.slug}/[/dim_text]")
                break
    else:
        session = Session(title="New Session")
        session.save()
        # Create matching workspace session
        ws = workspace_manager.create("New Session")
        session._ws = ws
        console.print(f"  [dim_text]📂 Workspace: workspace/{ws.slug}/[/dim_text]")

    api_client = _make_api_client()
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


@cli.command()
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

    api_client = _make_api_client()
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
            trace_enabled=trace_enabled,
        )
        if trace_enabled and getattr(job, "trace_path", ""):
            console.print(f"  [dim_text]🧾 Trace saved: {job.trace_path}[/dim_text]")
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
            shown_value = "●●●●●●●●" if is_sensitive_key(key) and value else value
            render_success(f"Set {key} = {shown_value}")
    else:
        render_config(_config.all())


@cli.command()
def memory() -> None:
    """Show Memoria (long-term memory) status."""
    print_banner()
    if not _config.is_configured():
        render_error("Not configured.")
        return
    api_client = _make_api_client()
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
@click.argument("action", required=False)
def jobs(action: Optional[str] = None) -> None:
    """Manage the Sentinel job queue (e.g. 'jobs clean')."""
    if action == "clean":
        if click.confirm("Wipe all job history?", default=False):
            _job_manager.clear_all()
            render_success("🧹 Job history cleared.")
        return

    print_banner()
    recent = _job_manager.list_recent(24)
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

    api_client = _make_api_client()

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


@cli.command()
@click.option("--reset", is_flag=True, help="Reset all token usage counters")
def tokens(reset: bool) -> None:
    """Show cumulative token usage per model/endpoint."""
    print_banner()
    if reset:
        if click.confirm("Reset all token usage counters?", default=False):
            _token_tracker.reset()
            render_success("🧹 Token usage counters reset.")
    else:
        render_token_usage(_token_tracker.get_all(), _token_tracker.get_totals())


@cli.command()
def tools() -> None:
    """List all currently activated tools."""
    print_banner()
    render_tools_list(get_all_available_tools())


@cli.command()
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def reset(yes: bool) -> None:
    """Destroy all ~/.cowork/* state and start fresh."""
    print_banner()
    if not yes and not click.confirm("⚠️  Delete ALL data in ~/.cowork/* ? This cannot be undone.", default=False):
        console.print("[muted]Reset cancelled.[/muted]")
        return

    with ThinkingSpinner("Resetting Cowork state"):
        _reset_all_cowork_state()
    render_success("🧹 Reset complete. All ~/.cowork/* data has been deleted.")


@cli.command()
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
        latest = find_latest_trace_file(session_id=session_id)
        if latest:
            target = latest

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


@cli.command()
@click.argument("action", type=click.Choice(["list", "add", "switch", "remove", "save"]), default="list")
@click.argument("args", nargs=-1)
def ai(action: str, args: tuple) -> None:
    """Manage AI profiles (endpoints, models, keys)."""
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


@cli.group()
def mm() -> None:
    """Manage multi-modal service endpoints (vision, images, ASR, TTS)."""
    pass


@mm.command(name="status")
def mm_status() -> None:
    """Show current multi-modal service configuration."""
    print_banner()
    from rich.table import Table
    from rich import box
    MM_SERVICES = {
        "vision": ("mm_vision_endpoint", "mm_vision_token", "mm_vision_model", "👁️  Vision (Image Analysis)"),
        "images": ("mm_image_endpoint",  "mm_image_token",  "mm_image_model",  "🎨 Image Generation"),
        "asr":    ("mm_asr_endpoint",    "mm_asr_token",    "mm_asr_model",    "🎤 Speech-to-Text (ASR)"),
        "tts":    ("mm_tts_endpoint",    "mm_tts_token",    "mm_tts_model",    "🔊 Text-to-Speech (TTS)"),
    }
    table = Table(title="🎨 Multi-Modal Services", box=box.ROUNDED, border_style="primary")
    table.add_column("Service", style="highlight", min_width=28)
    table.add_column("Endpoint", style="text")
    table.add_column("Model", style="muted")
    table.add_column("Token", style="success", justify="center")
    for svc_key, (ep_key, tok_key, mdl_key, label) in MM_SERVICES.items():
        ep  = _config.get(ep_key, "") or ""
        tok = _config.get(tok_key, "") or ""
        mdl = _config.get(mdl_key, "") or ""
        table.add_row(
            label,
            ep[:55] if ep else "[muted]—[/muted]",
            mdl if mdl else "[muted]—[/muted]",
            "✅" if (ep and tok) else "❌",
        )
    console.print(table)


@mm.command(name="set")
@click.argument("service", type=click.Choice(["vision", "images", "asr", "tts"]))
@click.argument("field", type=click.Choice(["endpoint", "token", "model"]))
@click.argument("value")
def mm_set(service: str, field: str, value: str) -> None:
    """Set a multi-modal service property (endpoint/token/model).

    Examples:
      cowork mm set vision endpoint https://api.openai.com/v1
      cowork mm set vision token sk-...
      cowork mm set images model dall-e-3
    """
    MM_KEYS = {
        "vision": ("mm_vision_endpoint", "mm_vision_token", "mm_vision_model", "👁️  Vision"),
        "images": ("mm_image_endpoint",  "mm_image_token",  "mm_image_model",  "🎨 Image Generation"),
        "asr":    ("mm_asr_endpoint",    "mm_asr_token",    "mm_asr_model",    "🎤 ASR"),
        "tts":    ("mm_tts_endpoint",    "mm_tts_token",    "mm_tts_model",    "🔊 TTS"),
    }
    ep_key, tok_key, mdl_key, label = MM_KEYS[service]
    if field == "endpoint":
        _config.set(ep_key, value.rstrip("/"))
        render_success(f"✅ {label} endpoint set to: {value}")
    elif field == "token":
        _config.set(tok_key, value)
        render_success(f"✅ {label} token updated. (stored in memory, not persisted to disk)")
    elif field == "model":
        _config.set(mdl_key, value)
        render_success(f"✅ {label} model set to: {value}")


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main() -> None:
    cli()


@cli.group()
def cron() -> None:
    """Manage scheduled agentic tasks."""
    pass


@cron.command()
def list() -> None:
    """List all scheduled cron jobs."""
    mgr = CronManager()
    render_cron_list(mgr.list_all())


@cron.command()
@click.argument("job_id")
def view(job_id: str) -> None:
    """View details and last result of a cron job."""
    mgr = CronManager()
    all_jobs = mgr.list_all()
    found = next((j for j in all_jobs if j.job_id == job_id), None)
    if found:
        from .ui import render_cron_result
        render_cron_result(found)
    else:
        render_error(f"Job not found: {job_id}")


@cron.command()
@click.argument("job_id")
def rm(job_id: str) -> None:
    """Remove a scheduled cron job."""
    mgr = CronManager()
    if mgr.remove_job(job_id):
        render_success(f"🗑️  Removed cron job: {job_id}")
    else:
        render_error(f"Job not found: {job_id}")


@cron.command()
@click.option("--interactive", is_flag=True, help="Allow firewall to prompt for confirmation")
def run_pending(interactive: bool) -> None:
    """Execute all pending cron jobs."""
    mgr = CronManager()
    pending = mgr.get_pending_jobs()
    if not pending:
        console.print("[dim_text]No pending cron jobs found.[/dim_text]")
        return

    render_success(f"⚡ Running {len(pending)} pending cron job(s)...")

    async def _run_jobs():
        api_client = _make_api_client()
        try:
            for job in pending:
                console.print(f"\n[sentinel]▶ Running Job: {job.job_id}[/sentinel]")
                console.print(f"[muted]Prompt: {job.prompt}[/muted]")
                
                # Load or create session for the job
                session = Session.load(job.session_id) if job.session_id else Session(title=f"Cron: {job.job_id}")
                if not session:
                    session = Session(title=f"Cron: {job.job_id}")
                
                scratchpad = Scratchpad(session.session_id)
                user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, _config.api_key or "anonymous"))
                memoria = Memoria(user_id, session.session_id, api_client, _config)

                response, _ = await run_agent_turn(
                    user_input=job.prompt,
                    session=session,
                    api_client=api_client,
                    scratchpad=scratchpad,
                    memoria=memoria,
                    show_routing=False,
                    unattended=not interactive,
                )
                
                mgr.mark_run(job.job_id, result=response)
                render_success(f"✅ Job {job.job_id} completed.")
        finally:
            await api_client.close()

    asyncio.run(_run_jobs())


if __name__ == "__main__":
    main()
