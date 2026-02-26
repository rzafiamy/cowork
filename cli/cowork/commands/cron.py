"""
cowork/commands/cron.py
───────────────────────
CLI command: `cron` group.
"""

from __future__ import annotations

import asyncio
import click

from ..config import Session, Scratchpad
from ..cron import CronManager
from ..memoria import Memoria
from ..ui import print_banner, render_cron_list, render_cron_result, render_error, render_success
from ..core import _config, get_memory_user_id, run_agent_turn, make_api_client


@click.group()
def cron() -> None:
    """Manage scheduled agentic tasks."""
    pass


@cron.command(name="list")
def cron_list() -> None:
    """List all scheduled cron jobs."""
    mgr = CronManager()
    render_cron_list(mgr.list_all())


@cron.command()
@click.argument("schedule_type", type=click.Choice(["once", "daily", "weekly"], case_sensitive=False))
@click.argument("schedule_value")
@click.argument("prompt", nargs=-1, required=True)
def add(schedule_type: str, schedule_value: str, prompt: tuple) -> None:
    """Add a new cron job."""
    mgr = CronManager()
    prompt_text = " ".join(prompt)
    job = mgr.add_job(
        prompt=prompt_text,
        schedule_type=schedule_type.lower(),
        schedule_value=schedule_value,
    )
    render_success(
        f"✅ Cron job added!\n"
        f"   ID: {job.job_id}  |  {schedule_type} @ {schedule_value}\n"
        f"   Next run: {(job.next_run or '—')[:16].replace('T', ' ')}"
    )


@cron.command()
@click.argument("job_id")
def view(job_id: str) -> None:
    """View details and last result of a cron job (supports partial ID)."""
    mgr = CronManager()
    found = mgr.get_job(job_id)
    if found:
        render_cron_result(found)
    else:
        render_error(f"Job not found: {job_id}")


@cron.command()
@click.argument("job_id")
def rm(job_id: str) -> None:
    """Remove a scheduled cron job (supports partial ID)."""
    mgr = CronManager()
    if mgr.remove_job(job_id):
        render_success(f"🗑️  Removed cron job: {job_id}")
    else:
        render_error(f"Job not found: {job_id}")


@cron.command()
@click.argument("query")
def search(query: str) -> None:
    """Search cron jobs by prompt text, job ID, or schedule."""
    mgr = CronManager()
    results = mgr.search_jobs(query)
    from ..ui import console
    if results:
        console.print(f"[success]🔍 {len(results)} job(s) matching '{query}':[/success]")
        render_cron_list(results)
    else:
        console.print(f"[muted]No cron jobs matching '{query}'.[/muted]")


@cron.command(name="run")
@click.argument("job_id")
@click.option("--interactive", is_flag=True, help="Allow firewall to prompt for confirmation")
def run_job(job_id: str, interactive: bool) -> None:
    """Force-run a specific cron job right now (ignores schedule)."""
    mgr = CronManager()
    found = mgr.get_job(job_id)
    if not found:
        render_error(f"Job not found: {job_id}")
        return

    from ..ui import console
    console.print(f"[sentinel]⚡ Force-running job: {found.job_id}[/sentinel]")
    console.print(f"[muted]Prompt: {found.prompt}[/muted]")

    async def _run():
        api_client = make_api_client()
        try:
            session = Session.load(found.session_id) if found.session_id else Session(title=f"Cron: {found.job_id}")
            if not session:
                session = Session(title=f"Cron: {found.job_id}")

            scratchpad = Scratchpad(session.session_id)
            user_id = get_memory_user_id()
            memoria = Memoria(user_id, session.session_id, api_client, _config)

            response, _ = await run_agent_turn(
                user_input=found.prompt,
                session=session,
                api_client=api_client,
                scratchpad=scratchpad,
                memoria=memoria,
                show_routing=False,
                unattended=not interactive,
            )
            mgr.mark_run(found.job_id, result=response)
            render_success(f"✅ Job '{found.job_id}' executed successfully.")
        finally:
            await api_client.close()

    asyncio.run(_run())


@cron.command(name="run-pending")
@click.option("--interactive", is_flag=True, help="Allow firewall to prompt for confirmation")
def run_pending(interactive: bool) -> None:
    """Execute all currently pending cron jobs."""
    mgr = CronManager()
    pending = mgr.get_pending_jobs()
    if not pending:
        from ..ui import console
        console.print("[dim_text]No pending cron jobs found.[/dim_text]")
        return

    render_success(f"⚡ Running {len(pending)} pending cron job(s)...")

    async def _run_jobs():
        api_client = make_api_client()
        try:
            from ..ui import console
            for job in pending:
                console.print(f"\n[sentinel]▶ Running Job: {job.job_id}[/sentinel]")
                console.print(f"[muted]Prompt: {job.prompt}[/muted]")

                session = Session.load(job.session_id) if job.session_id else Session(title=f"Cron: {job.job_id}")
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
                    unattended=not interactive,
                )

                mgr.mark_run(job.job_id, result=response)
                render_success(f"✅ Job {job.job_id} completed.")
        finally:
            await api_client.close()

    asyncio.run(_run_jobs())
