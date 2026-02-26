"""
cowork/slash_commands/misc_cmd.py
──────────────────────────────────
Handlers for miscellaneous slash commands:
  /exit, /quit, /q, /help, /clear, /new, /tools, /reset, /open
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import click
from rich.rule import Rule

from ..config import Session
from ..workspace import workspace_manager, WorkspaceSession, WORKSPACE_ROOT
from ..tools import get_all_available_tools
from ..ui import (
    ThinkingSpinner,
    console,
    print_banner,
    render_error,
    render_help,
    render_success,
    render_tools_list,
    render_warning,
)
from ..core import _job_manager, reset_all_cowork_state


def handle_exit() -> tuple[bool, Optional[Session], bool]:
    """Handle /exit, /quit, /q."""
    console.print()
    console.print(Rule(style="primary"))
    console.print("[primary]  👋 Goodbye! Your sessions are saved.[/primary]")
    console.print(Rule(style="primary"))
    console.print()
    return False, None, False


def handle_clear() -> tuple[bool, Optional[Session], bool]:
    """Handle /clear."""
    console.clear()
    print_banner()
    return True, None, False


def handle_new(session: Session) -> tuple[bool, Optional[Session], bool]:
    """Handle /new — start a fresh session."""
    new_session = Session(title="New Session")
    ws = workspace_manager.ensure_for_session(new_session.session_id, title="New Session")
    new_session._ws = ws
    new_session.workspace_slug = ws.slug
    new_session.save()
    render_success(
        f"✨ New session started: {new_session.session_id[:8]}\n"
        f"📂 Workspace: workspace/{ws.slug}/"
    )
    return True, new_session, False


def handle_tools() -> tuple[bool, Optional[Session], bool]:
    """Handle /tools."""
    render_tools_list(get_all_available_tools())
    return True, None, False


def handle_reset() -> tuple[bool, Optional[Session], bool]:
    """Handle /reset."""
    if click.confirm(
        "⚠️  This will permanently delete ALL data in ~/.cowork/* . Continue?",
        default=False,
    ):
        with ThinkingSpinner("Resetting Cowork state"):
            reset_all_cowork_state()
        render_success("🧹 Reset complete. All ~/.cowork/* data has been deleted.")
        return False, None, False
    return True, None, False


def handle_open(
    cmd: str,
    session: Session,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /open <path>."""
    if len(cmd.split(maxsplit=1)) < 2:
        render_error("Usage: /open <path_to_file>")
        return True, None, False

    path_str = cmd.split(maxsplit=1)[1].strip(' "\'')
    ws = getattr(session, "_ws", None)

    if ws:
        current_slug = ws.slug
        if "new-session" in path_str:
            path_str = path_str.replace("new-session", current_slug)
        else:
            match = re.search(r"workspace/([^/]+)/", path_str)
            if match:
                typed_slug = match.group(1)
                if current_slug.startswith(typed_slug):
                    path_str = path_str.replace(typed_slug, current_slug)

    raw_path = Path(path_str).expanduser()
    candidate_paths: list[Path] = []
    if raw_path.is_absolute():
        candidate_paths.append(raw_path)
    else:
        if ws:
            candidate_paths.extend([
                ws.path / raw_path,
                ws.artifacts_path / raw_path.name,
            ])
        candidate_paths.extend([
            WORKSPACE_ROOT / raw_path,
            (WORKSPACE_ROOT / "artifacts" / raw_path.name),
        ])
        candidate_paths.append(Path.cwd() / raw_path)

    resolved_existing = next((p.resolve() for p in candidate_paths if p.exists()), None)

    if not resolved_existing and ws:
        import difflib
        target_name = raw_path.name
        artifact_files = (
            [p for p in ws.artifacts_path.iterdir() if p.is_file()]
            if ws.artifacts_path.exists()
            else []
        )
        exact_ci = next((p for p in artifact_files if p.name.lower() == target_name.lower()), None)
        if exact_ci:
            resolved_existing = exact_ci.resolve()
        else:
            close = difflib.get_close_matches(
                target_name, [p.name for p in artifact_files], n=3, cutoff=0.6
            )
            if len(close) == 1:
                resolved_existing = (ws.artifacts_path / close[0]).resolve()
                render_warning(
                    f"Path not found. Opening closest artifact match instead: {resolved_existing.name}"
                )
            elif close:
                render_warning(f"Path not found. Did you mean one of: {', '.join(close)}")

    if not resolved_existing:
        target_name = raw_path.name
        for s_info in workspace_manager.list_all():
            slug = s_info["slug"]
            if ws and slug == ws.slug:
                continue
            p_ws = WorkspaceSession.load(slug)
            if p_ws and p_ws.artifacts_path.exists():
                match = next(
                    (p for p in p_ws.artifacts_path.iterdir() if p.name.lower() == target_name.lower()),
                    None,
                )
                if match:
                    resolved_existing = match.resolve()
                    render_warning(f"File found in session '[highlight]{slug}[/highlight]'.")
                    break

    if resolved_existing and resolved_existing.exists():
        try:
            click.launch(str(resolved_existing))
            render_success(f"📂 Opened: {resolved_existing}")
        except Exception as e:
            render_error(f"Failed to open '{resolved_existing}': {e}")
    else:
        attempted = (
            ", ".join(str(p.resolve()) for p in candidate_paths)
            if candidate_paths
            else str(raw_path)
        )
        render_warning(f"Path does not exist. Tried: {attempted}")

    return True, None, False
