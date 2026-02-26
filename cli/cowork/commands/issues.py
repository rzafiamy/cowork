"""
cowork/commands/issues.py
─────────────────────────
CLI command: `issues` group.
"""

from __future__ import annotations

import click

from ..ui import print_banner, render_error, render_success
from ..core import _config, get_memory_user_id


@click.group(invoke_without_command=True)
@click.pass_context
def issues(ctx: click.Context) -> None:
    """Manage recorded tool failures and solutions."""
    if ctx.invoked_subcommand is not None:
        return

    print_banner()
    if not _config.is_configured():
        render_error("Not configured.")
        return

    from ..issues import IssueManager
    import cowork.ui as ui
    user_id = get_memory_user_id()
    mgr = IssueManager(user_id, _config)
    ui.render_issue_dashboard(mgr.get_triplet_count(), mgr.list_all())


@issues.command(name="list")
def issues_list() -> None:
    """List all recorded issues."""
    from ..issues import IssueManager
    import cowork.ui as ui
    user_id = get_memory_user_id()
    mgr = IssueManager(user_id, _config)
    ui.render_issue_dashboard(mgr.get_triplet_count(), mgr.list_all())


@issues.command(name="rm")
@click.argument("id")
def issues_rm(id: str) -> None:
    """Delete a recorded issue by ID."""
    from ..issues import IssueManager
    user_id = get_memory_user_id()
    mgr = IssueManager(user_id, _config)

    if mgr.delete_issue(id):
        render_success(f"🗑️  Issue '{id}' deleted.")
    else:
        all_t = mgr.list_all()
        found = [t for t in all_t if t["id"].startswith(id)]
        if len(found) == 1:
            mgr.delete_issue(found[0]["id"])
            render_success(f"🗑️  Issue '{found[0]['id'][:8]}' deleted.")
        elif len(found) > 1:
            render_error(f"Multiple matches for '{id}'.")
        else:
            render_error(f"Issue '{id}' not found.")


@issues.command(name="search")
@click.argument("query")
def issues_search(query: str) -> None:
    """Search recorded issues."""
    from ..issues import IssueManager
    user_id = get_memory_user_id()
    mgr = IssueManager(user_id, _config)

    results = mgr.search_issues(query)
    import cowork.ui as ui
    ui.render_issue_search_results(query, results)
