"""
cowork/slash_commands/cron_cmd.py
──────────────────────────────────
Handlers for /cron slash command.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..config import Session, Scratchpad
from ..cron import CronManager, _now
from ..memoria import Memoria
from ..ui import render_error, render_success, render_warning, render_cron_list
from ..core import _config, get_memory_user_id, run_agent_turn


async def handle_cron(
    cmd: str,
    parts: list[str],
    session: Session,
    api_client,
    scratchpad: Scratchpad,
    memoria: Memoria,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /cron command."""
    mgr = CronManager()
    sub = parts[1].lower() if len(parts) > 1 else ""

    if sub == "list" or not sub:
        render_cron_list(mgr.list_all())

    elif sub == "add":
        scmd = cmd.strip()
        try:
            import shlex
            all_parts = shlex.split(scmd)
        except Exception:
            all_parts = scmd.split()

        if len(all_parts) < 4:
            render_error(
                "Usage: /cron add <type> <time> <prompt>",
                hint="Types: once | daily | weekly  —  Time: HH:MM or ISO datetime",
            )
        else:
            stype = all_parts[2].lower()
            svalue = all_parts[3].strip("'\"")
            prompt_text = " ".join(all_parts[4:]).strip("'\" ")

            if stype not in ("once", "daily", "weekly"):
                render_error(f"Invalid schedule type '{stype}'.", hint="Use: once, daily, or weekly")
            elif not prompt_text.strip():
                render_error("Prompt cannot be empty.")
            else:
                job = mgr.add_job(
                    prompt=prompt_text.strip(),
                    schedule_type=stype,
                    schedule_value=svalue,
                    session_id=session.session_id,
                )
                next_run_dt = datetime.fromisoformat(job.next_run) if job.next_run else None
                tomorrow_hint = ""
                if stype == "once" and next_run_dt and next_run_dt.date() > _now().date():
                    tomorrow_hint = "\n[warning]⚠️  Time has already passed today; scheduled for TOMORROW.[/warning]"

                render_success(
                    f"✅ Cron job added!\n"
                    f"   ID: [highlight]{job.job_id}[/highlight]  |  "
                    f"{stype} @ {svalue}{tomorrow_hint}\n"
                    f"   Next run: {(job.next_run or '—')[:16].replace('T', ' ')}"
                )

    elif sub == "search":
        if len(parts) < 3:
            render_error("Usage: /cron search <query>")
        else:
            query = " ".join(parts[2:])
            results = mgr.search_jobs(query)
            if results:
                render_success(f"🔍 Found {len(results)} cron job(s) matching '{query}'.")
                render_cron_list(results)
            else:
                render_warning(f"No cron jobs matching '{query}'.")

    elif sub in ("run", "exec"):
        if len(parts) < 3:
            render_error("Usage: /cron run <job_id>")
        else:
            job_id = parts[2]
            found = mgr.get_job(job_id)
            if not found:
                render_error(f"Cron job '{job_id}' not found.")
            else:
                render_success(f"⚡ Running cron job '{found.job_id}' now…")
                _j_session = (
                    Session.load(found.session_id)
                    if found.session_id
                    else Session(title=f"Cron: {found.job_id}")
                ) or Session(title=f"Cron: {found.job_id}")
                _j_scratchpad = Scratchpad(_j_session.session_id)
                _j_user_id = get_memory_user_id()
                from ..memoria import Memoria as _Memoria
                _j_memoria = _Memoria(_j_user_id, _j_session.session_id, api_client, _config)
                response, _ = await run_agent_turn(
                    user_input=found.prompt,
                    session=_j_session,
                    api_client=api_client,
                    scratchpad=_j_scratchpad,
                    memoria=_j_memoria,
                    show_routing=False,
                    unattended=False,
                )
                mgr.mark_run(found.job_id, result=response)
                render_success(f"✅ Job '{found.job_id}' executed and marked as run.")

    elif sub == "view":
        if len(parts) < 3:
            render_error("Usage: /cron view <job_id>")
        else:
            job_id = parts[2]
            found = mgr.get_job(job_id)
            if found:
                from ..ui import render_cron_result
                render_cron_result(found)
            else:
                render_error(f"Cron job '{job_id}' not found.")

    elif sub in ("rm", "delete", "del"):
        if len(parts) < 3:
            render_error("Usage: /cron rm <job_id>")
        else:
            if mgr.remove_job(parts[2]):
                render_success(f"🗑️  Cron job '{parts[2]}' removed.")
            else:
                render_error(f"Cron job '{parts[2]}' not found.")

    else:
        render_cron_list(mgr.list_all())

    return True, None, False
