"""
cowork/slash_commands/jobs.py
──────────────────────────────
Handlers for /jobs slash commands.
"""

from __future__ import annotations

from typing import Optional

import click

from ..config import Session, Scratchpad
from ..memoria import Memoria
from ..ui import render_error, render_success, render_job_dashboard
from ..core import _job_manager, _config, get_memory_user_id, make_api_client, run_agent_turn


async def handle_jobs(
    parts: list[str],
    session: Session,
    api_client,
    scratchpad: Scratchpad,
    memoria: Memoria,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /jobs command."""
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

    return True, None, False
