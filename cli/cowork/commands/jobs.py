"""
cowork/commands/jobs.py
───────────────────────
CLI command: `jobs`.
"""

from __future__ import annotations

from typing import Optional

import click

from ..ui import print_banner, render_job_dashboard, render_success
from ..core import _job_manager


@click.command()
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
