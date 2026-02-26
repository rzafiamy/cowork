"""
cowork/commands/sessions.py
────────────────────────────
CLI commands: `sessions` and `session` groups.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import click

from ..config import Session
from ..prompts import SESSION_RE_TITLE_PROMPT
from ..workspace import workspace_manager
from ..ui import (
    ThinkingSpinner,
    print_banner,
    render_error,
    render_session_list,
    render_success,
    render_warning,
)
from ..core import _config, make_api_client


@click.group(name="sessions", invoke_without_command=True)
@click.pass_context
def sessions(ctx: click.Context) -> None:
    """Manage saved conversation sessions."""
    if ctx.invoked_subcommand is None:
        print_banner()
        all_sessions = Session.list_all()
        render_session_list(all_sessions)


@sessions.command(name="list")
def sessions_list() -> None:
    """List all saved sessions."""
    print_banner()
    all_sessions = Session.list_all()
    render_session_list(all_sessions)


@sessions.command(name="rm")
@click.argument("index", type=int)
def sessions_rm(index: int) -> None:
    """Permanently delete a session by index."""
    all_sessions = Session.list_all()
    if 1 <= index <= len(all_sessions):
        s_info = all_sessions[index - 1]
        session_id = s_info["session_id"]
        session = Session.load(session_id)
        if session:
            if click.confirm(f"🗑️  Delete session '{s_info['title']}'?", default=False):
                if session.delete():
                    render_success(f"Session deleted: {s_info['title']}")
                else:
                    render_error("Failed to delete session file.")
        else:
            render_error(f"Session {session_id} could not be loaded.")
    else:
        render_error(f"Invalid index {index}. (Current range: 1 to {len(all_sessions)})")


@sessions.command(name="retitle")
@click.option("--limit", default=300, help="Max tokens of content for analysis")
def sessions_retitle(limit: int) -> None:
    """Batch re-title all sessions using AI analysis."""
    print_banner()
    all_sessions_info = Session.list_all()
    if not all_sessions_info:
        render_warning("No sessions found.")
        return

    async def _run_retitle():
        api_client = make_api_client()
        count = 0

        with ThinkingSpinner(f"Analyzing {len(all_sessions_info)} sessions"):
            for i, s_info in enumerate(all_sessions_info, 1):
                session = Session.load(s_info["session_id"])
                if not session or not session.messages:
                    continue

                content = session.get_sandwich_content(max_chars=limit * 4)
                unique_num = f"{i:04d}"

                prompt = SESSION_RE_TITLE_PROMPT.format(unique_id=unique_num, content=content)
                try:
                    res = await api_client.chat(
                        messages=[{"role": "user", "content": prompt}],
                        model=_config.get("model_compress"),
                        temperature=0.0,
                    )
                    new_title = res.get("content", "").strip()
                    new_title = new_title.strip('"').strip("'")
                    if new_title:
                        session.title = new_title
                        session.save()
                        count += 1
                except Exception:
                    pass

        await api_client.close()
        render_success(f"✅ Successfully re-titled {count} sessions.")
        render_session_list(Session.list_all())

    asyncio.run(_run_retitle())


@sessions.command(name="search")
@click.argument("query", required=False)
@click.option("--title", help="Regex to match against session titles")
@click.option("--content", help="Regex to match against message contents")
@click.option("--summary", help="Regex to match against session summaries")
@click.option("--triplets", "triplets_opt", help="Regex to match against knowledge triplets")
def sessions_search(
    query: Optional[str],
    title: Optional[str],
    content: Optional[str],
    summary: Optional[str],
    triplets_opt: Optional[str],
) -> None:
    """Powerful regex-based search across sessions."""
    print_banner()
    all_sessions_info = Session.list_all()
    if not all_sessions_info:
        render_warning("No sessions found.")
        return

    fields = []
    if title:
        fields.append("title")
    if content:
        fields.append("content")
    if summary:
        fields.append("summary")
    if triplets_opt:
        fields.append("triplets")

    if not fields:
        fields = ["title", "content", "summary", "triplets"]

    pattern = query or title or content or summary or triplets_opt
    if not pattern:
        render_error(
            "No search pattern provided.",
            hint="Usage: sessions search <pattern> OR use --title/--content/--summary",
        )
        return

    results = []
    with ThinkingSpinner(f"Searching through {len(all_sessions_info)} sessions"):
        for s_info in all_sessions_info:
            session = Session.load(s_info["session_id"])
            if session and session.match(pattern, fields=fields):
                results.append({
                    "session_id": session.session_id,
                    "title": session.title,
                    "created_at": session.created_at,
                    "updated_at": session.updated_at,
                    "message_count": len(session.messages),
                })

    if results:
        render_success(f"🔍 Found {len(results)} matching sessions.")
        render_session_list(results)
    else:
        render_warning(f"No matches found for '{pattern}'.")


# ── Alias: session (singular) ─────────────────────────────────────────────────

@click.group(name="session")
@click.pass_context
def session_cmd(ctx: click.Context) -> None:
    """Session management (singular alias)."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(sessions)


session_cmd.add_command(sessions_list, name="list")
session_cmd.add_command(sessions_rm, name="rm")
session_cmd.add_command(sessions_retitle, name="retitle")
session_cmd.add_command(sessions_search, name="search")
