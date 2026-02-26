"""
cowork/core.py
──────────────
Shared global state and core async logic.

Everything imported here is a stable public surface used across
the CLI command modules and the slash-command handler.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import TYPE_CHECKING, Any, Optional

import click

from .agent import GeneralPurposeAgent
from .api_client import APIClient, APIError
from .config import (
    CONFIG_DIR,
    AgentJob,
    AIProfileManager,
    ConfigManager,
    FirewallManager,
    JobManager,
    Scratchpad,
    Session,
    TokenTracker,
    is_sensitive_key,
)
from .cron import CronManager
from .memoria import Memoria
from .workspace import workspace_manager, WorkspaceSession, WORKSPACE_ROOT
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
    render_error,
    render_plan_info,
    render_response,
    render_routing_info,
    render_skill_info,
    render_success,
)

# ─── Global State ────────────────────────────────────────────────────────────

_config = ConfigManager()
_job_manager = JobManager(max_jobs=_config.get("max_concurrent_jobs", 10))
_token_tracker = TokenTracker()
_ai_profiles = AIProfileManager(_config)
_last_trace: Optional[dict] = None
_last_job: Optional[AgentJob] = None


# ─── Helper Functions ─────────────────────────────────────────────────────────

def get_memory_user_id() -> str:
    """Return a stable memory identity persisted in config."""
    existing = str(_config.get("memory_user_id", "") or "").strip()
    if existing:
        return existing
    generated = str(uuid.uuid4())
    _config.set("memory_user_id", generated)
    return generated


def verify_firewall_integrity() -> None:
    """Validate firewall.yaml integrity at startup."""
    fw = FirewallManager()
    ok, reason = fw.is_integrity_ok()
    if ok:
        return
    render_error(
        "Invalid firewall configuration.",
        hint=f"Fix {fw.path}. Reason: {reason}",
    )
    raise click.exceptions.Exit(2)


def reset_all_cowork_state() -> None:
    """Wipe all persisted Cowork state under ~/.cowork/*."""
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


def make_api_client() -> APIClient:
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


def make_session_scratchpad(session_id: str) -> Scratchpad:
    """Build a scratchpad bound to the given session."""
    return Scratchpad(session_id)


def is_continuation_prompt(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return False
    if len(s) > 120:
        return False
    patterns = [
        r"^(continue|continue please|resume|go on|keep going|proceed)\b",
        r"^(poursuis|continue stp|continue s'il te plait|reprends|vas-y)\b",
    ]
    return any(re.search(p, s) for p in patterns)


def get_pending_goal(session: Session) -> Optional[dict]:
    md = getattr(session, "metadata", {}) or {}
    pending = md.get("pending_goal")
    if isinstance(pending, dict) and pending:
        return pending
    return None


def set_pending_goal(session: Session, pending: Optional[dict]) -> None:
    if not isinstance(session.metadata, dict):
        session.metadata = {}
    if pending:
        session.metadata["pending_goal"] = pending
    else:
        session.metadata.pop("pending_goal", None)


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

    effective_input = user_input
    effective_action_mode = action_mode
    pending_goal = get_pending_goal(session)
    if effective_action_mode is None and pending_goal and is_continuation_prompt(user_input):
        routed = pending_goal.get("categories") or ["ALL_TOOLS"]
        remaining = str(pending_goal.get("remaining", "")).strip()
        original = str(pending_goal.get("original_request", "")).strip()
        completed_tools = pending_goal.get("completed_tools", [])
        # Build a grounding section listing tools already executed — names+status only
        if completed_tools:
            tool_lines = [
                f"  {i}. {'\u2705' if t.get('status','ok')=='ok' else '\u274c'} {t.get('name','?')}"
                for i, t in enumerate(completed_tools[-20:], 1)  # cap at last 20
            ]
            completed_tools_text = (
                "\nTools ALREADY executed (do NOT repeat these):\n"
                + "\n".join(tool_lines)
            )
        else:
            completed_tools_text = ""
        continuation_note = (
            "[CONTINUATION CONTEXT]\n"
            "Resume the pending task from the previous turn.\n"
            f"Original request: {original or '(not captured)'}\n"
            f"Remaining work: {remaining or '(continue from latest tool evidence)'}\n"
            + completed_tools_text
            + "\nImportant: Do not claim any tool action succeeded unless it is executed and evidenced in this turn."
            + "\nDo NOT redo tools marked \u2705 above unless the user explicitly requests it."
        )
        effective_input = f"{continuation_note}\n\nUser follow-up: {user_input}"
        effective_action_mode = {"categories": routed, "pill": "#continue"}

    # Register job with Sentinel
    job = AgentJob(
        session_id=session.session_id,
        prompt=effective_input[:200],
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

    spinner = ThinkingSpinner("Cowork is thinking")
    stream_renderer = StreamingRenderer()
    status_messages: list[str] = []
    routing_info: Optional[dict] = None
    active_skill_info: Optional[Any] = None

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

        original_classify = agent.router.classify

        async def patched_classify(prompt: str) -> dict:
            result = await original_classify(prompt)
            nonlocal routing_info
            routing_info = result
            return result

        original_activate = agent.skill_runtime.activate

        def patched_activate(user_input: str, routed_categories: list[str]):
            result = original_activate(user_input, routed_categories)
            nonlocal active_skill_info
            active_skill_info = result
            return result

        async def on_confirm(name: str, reason: str, args: dict) -> bool:
            if unattended:
                nonlocal status_messages
                msg = f"🛡️ [UNATTENDED] Firewall blocked tool '{name}' (reason: {reason})"
                status_messages.append(msg)
                return False

            was_running = spinner._live is not None
            if was_running:
                spinner.stop()

            res = await asyncio.get_event_loop().run_in_executor(
                None, confirm_tool_call, name, reason, args
            )

            if was_running:
                spinner.start()
            return res

        agent.router.classify = patched_classify
        agent.skill_runtime.activate = patched_activate
        agent.confirm_cb = on_confirm

        response = await agent.run(effective_input, session, job, action_mode=effective_action_mode)
        elapsed = time.time() - start_time

        if not unattended:
            spinner.stop()

        plan_dict = getattr(job, "plan_dict", None)
        if show_routing and plan_dict and plan_dict.get("steps"):
            render_plan_info(plan_dict)

        if show_routing and routing_info:
            render_routing_info(
                routing_info["categories"],
                routing_info["confidence"],
                routing_info.get("reasoning", ""),
            )

        if show_routing and active_skill_info and active_skill_info.skill:
            render_skill_info(
                active_skill_info.skill.name,
                active_skill_info.score,
                active_skill_info.trust.tier if active_skill_info.trust else 1,
                active_skill_info.skill.description,
                active_skill_info.skill.tool_categories,
            )

        if not unattended:
            render_response(response, elapsed, job.tool_calls, job.steps)

        _job_manager.complete(job.job_id, response)

        session.add_message("user", user_input)
        session.add_message("assistant", response)
        if getattr(job, "step_limit_reached", False):
            original_request = user_input
            if pending_goal and isinstance(pending_goal.get("original_request"), str):
                original_request = pending_goal.get("original_request") or user_input
            # Merge completed tools from any previous pending_goal with this turn's tool calls.
            # Store only name+status (no args) to keep the pending_goal size small.
            prior_tools = list(pending_goal.get("completed_tools", []) if pending_goal else [])
            this_turn_tools = [
                {"name": t.get("name", "?"), "status": t.get("status", "ok")}
                for t in getattr(job, "tool_calls_list", []) or []
            ]
            all_completed_tools = prior_tools + this_turn_tools
            set_pending_goal(
                session,
                {
                    "created_at": int(time.time()),
                    "original_request": original_request,
                    "remaining": response[:1600],
                    "categories": list(getattr(job, "routed_categories", []) or []),
                    "step_limit_reached": True,
                    "completed_tools": all_completed_tools[-40:],  # keep last 40 to cap size
                },
            )
        elif pending_goal and is_continuation_prompt(user_input):
            set_pending_goal(session, None)
        session.save()

        # Auto-generate title for new sessions
        if len(session.messages) == 2 and response:
            try:
                title = await agent.generate_title(session)
                if title and title != "New Session":
                    session.title = title
                    if hasattr(session, "_ws") and session._ws:
                        ws = session._ws
                        old_slug = ws.slug
                        new_ws = workspace_manager.rename(old_slug, title)
                        if new_ws:
                            session._ws = new_ws
                            session.workspace_slug = new_ws.slug
                            session.save()
                            render_success(f"🏷️  Session re-titled: [highlight]{title}[/highlight]")
                            render_success(
                                f"📂 Workspace moved to: [dim_text]workspace/{new_ws.slug}/[/dim_text]"
                            )
            except Exception:
                pass

        # Sync to workspace session
        if hasattr(session, "_ws") and session._ws:
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


# ─── Background Cron Poller ───────────────────────────────────────────────────

async def background_cron_poll() -> None:
    """Periodically check and run pending cron jobs while the app is open."""
    api_client = make_api_client()
    try:
        while True:
            await asyncio.sleep(60)
            mgr = CronManager()
            pending = mgr.get_pending_jobs()
            for job in pending:
                try:
                    session = (
                        Session.load(job.session_id)
                        if job.session_id
                        else Session(title=f"Cron: {job.job_id}")
                    )
                    if not session:
                        session = Session(title=f"Cron: {job.job_id}")

                    scratchpad = Scratchpad(session.session_id)
                    user_id = get_memory_user_id()
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
                    render_success(f"🔔 Cron Job Completed: {job.job_id}")
                except Exception as exc:
                    render_error(f"Cron job {job.job_id} failed: {exc}")
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        await api_client.close()
