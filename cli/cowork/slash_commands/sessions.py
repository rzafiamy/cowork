"""
cowork/slash_commands/sessions.py
──────────────────────────────────
Handlers for /sessions, /session, /load slash commands.
"""

from __future__ import annotations

from typing import Optional

import click

from ..config import Session, Scratchpad
from ..prompts import SESSION_RE_TITLE_PROMPT
from ..workspace import workspace_manager
from ..ui import (
    ThinkingSpinner,
    render_error,
    render_success,
    render_session_list,
    render_warning,
)
from ..core import _config, make_api_client


async def handle_sessions(
    cmd: str,
    parts: list[str],
    session: Session,
    api_client,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /sessions and /session commands."""
    sub = parts[1].lower() if len(parts) > 1 else "list"

    if sub == "list":
        updated = Session.list_all()
        render_session_list(updated)

    elif sub == "rm":
        if len(parts) < 3:
            render_error("Usage: /sessions rm <index>")
        else:
            try:
                idx = int(parts[2])
                all_s = Session.list_all()
                if 1 <= idx <= len(all_s):
                    s_info = all_s[idx - 1]
                    s_obj = Session.load(s_info["session_id"])
                    if s_obj:
                        if click.confirm(f"🗑️  Delete session '{s_info['title']}'?", default=False):
                            if s_obj.delete():
                                render_success(f"Session deleted: {s_info['title']}")
                            else:
                                render_error("Failed to delete session file.")
                    else:
                        render_error("Session could not be loaded.")
                else:
                    render_error(f"Invalid index {idx}.")
            except ValueError:
                render_error("Index must be a number.")

    elif sub == "retitle":
        async def _slash_retitle():
            all_sessions_info = Session.list_all()
            count = 0
            with ThinkingSpinner(f"Analyzing {len(all_sessions_info)} sessions"):
                for i, s_info in enumerate(all_sessions_info, 1):
                    session_obj = Session.load(s_info["session_id"])
                    if not session_obj or not session_obj.messages:
                        continue
                    content = session_obj.get_sandwich_content(max_chars=1200)
                    unique_num = f"{i:04d}"
                    prompt = SESSION_RE_TITLE_PROMPT.format(unique_id=unique_num, content=content)
                    try:
                        res = await api_client.chat(
                            messages=[{"role": "user", "content": prompt}],
                            model=_config.get("model_compress"),
                            temperature=0.0,
                        )
                        new_title_val = res.get("content", "").strip().strip('"').strip("'")
                        if new_title_val:
                            session_obj.title = new_title_val
                            ws_link = None
                            if session_obj.workspace_slug:
                                ws_link = workspace_manager.rename(session_obj.workspace_slug, new_title_val)
                            else:
                                for wi in workspace_manager.list_all():
                                    if wi["session_id"] == session_obj.session_id:
                                        ws_link = workspace_manager.rename(wi["slug"], new_title_val)
                                        break
                            if ws_link:
                                session_obj.workspace_slug = ws_link.slug
                            session_obj.save()
                            count += 1
                    except Exception:
                        pass
            render_success(f"✅ Successfully re-titled {count} sessions.")
            render_session_list(Session.list_all())

        await _slash_retitle()

    elif sub == "search":
        pattern = parts[2] if len(parts) > 2 else ""
        if not pattern:
            render_error("Usage: /sessions search <regex>")
        else:
            results = []
            all_s = Session.list_all()
            with ThinkingSpinner(f"Searching {len(all_s)} sessions"):
                for s_info in all_s:
                    s_obj = Session.load(s_info["session_id"])
                    if s_obj and s_obj.match(pattern):
                        results.append({
                            "session_id": s_obj.session_id,
                            "title": s_obj.title,
                            "created_at": s_obj.created_at,
                            "updated_at": s_obj.updated_at,
                            "message_count": len(s_obj.messages),
                        })
            if results:
                render_success(f"🔍 Found {len(results)} matching sessions.")
                render_session_list(results)
            else:
                render_warning(f"No matches found for '{pattern}'.")
    else:
        updated = Session.list_all()
        render_session_list(updated)

    return True, None, False


async def handle_load(
    parts: list[str],
    session: Session,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /load command."""
    if len(parts) < 2:
        render_error("Usage: /load <session_id_or_number>")
        return True, None, False

    target = parts[1]
    all_sessions = Session.list_all()
    loaded = None

    if target.isdigit():
        idx = int(target) - 1
        if 0 <= idx < len(all_sessions):
            loaded = Session.load(all_sessions[idx]["session_id"])
    else:
        for s in all_sessions:
            if s["session_id"].startswith(target):
                loaded = Session.load(s["session_id"])
                break

    if loaded:
        render_success(f"📂 Loaded session: '{loaded.title}' ({len(loaded.messages)} messages)")
        ws = workspace_manager.get_by_session_id(loaded.session_id)
        if ws:
            loaded._ws = ws
            loaded.workspace_slug = ws.slug
            loaded.save()
            render_success(f"📂 Workspace: workspace/{ws.slug}/")
        return True, loaded, False
    else:
        render_error(f"Session '{target}' not found.")

    return True, None, False
