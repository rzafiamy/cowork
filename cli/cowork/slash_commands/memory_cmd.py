"""
cowork/slash_commands/memory_cmd.py
────────────────────────────────────
Handlers for /memory (/vector) and /issues slash commands.
"""

from __future__ import annotations

from typing import Optional

import click

from ..config import Session
from ..memoria import Memoria
from ..ui import (
    ThinkingSpinner,
    console,
    render_error,
    render_memory_dashboard,
    render_memory_search_results,
    render_success,
    render_warning,
)
from ..core import _config, get_memory_user_id


async def handle_memory(
    parts: list[str],
    memoria: Memoria,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /memory and /vector commands."""
    sub = parts[1].lower() if len(parts) > 1 else ""

    if not sub or sub in ("list", "view"):
        render_memory_dashboard(memoria.get_summary(), memoria.get_all_triplets(), memoria.kg_limit)

    elif sub == "search":
        if len(parts) < 3:
            render_error("Usage: /memory search <query>")
        else:
            query = parts[2].strip().strip('"').strip("'")
            results = memoria.search_triplets(query)
            render_memory_search_results(query, results)

    elif sub == "add":
        args = parts[2].split() if len(parts) > 2 else []
        if len(args) < 3:
            render_error("Usage: /memory add <subject> <predicate> <object>")
        else:
            subj = args[0].strip('"').strip("'")
            pred = args[1].strip('"').strip("'")
            obj = " ".join(args[2:]).strip('"').strip("'")
            tid = memoria.add_triplet(subj, pred, obj)
            render_success(f"✅ Added knowledge fact: {tid[:8]}")

    elif sub == "rm":
        if len(parts) < 3:
            render_error("Usage: /memory rm <id>")
        else:
            if memoria.delete_triplet(parts[2]):
                render_success(f"🗑️  Memory fact '{parts[2]}' deleted.")
            else:
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

    elif sub == "prune":
        with ThinkingSpinner("Pruning non-durable memory facts"):
            removed = memoria.prune_transient_triplets()
        if removed > 0:
            render_success(f"🧹 Pruned {removed} non-durable memory fact(s).")
        else:
            render_success("🧠 No non-durable memory facts found.")

    elif sub == "summarize":
        render_memory_dashboard(memoria.get_summary(), [], memoria.kg_limit)

    elif sub in ("compress", "consolidate"):
        with ThinkingSpinner("Consolidating knowledge graph"):
            success, reason = await memoria.consolidate()
        if success:
            render_success("🧠 Memory consolidated & redundancy removed.")
            render_memory_dashboard(memoria.get_summary(), memoria.get_all_triplets(), memoria.kg_limit)
        else:
            reason_map = {
                "no_triplets": "No memory facts to consolidate yet.",
                "no_changes": "Memory already consolidated (no changes needed).",
                "empty_model_output": "Consolidation model returned no triplets.",
                "no_valid_triplets": "Consolidation returned invalid triplets.",
                "exception": "Consolidation failed due to an internal error.",
            }
            render_error(reason_map.get(reason, f"Memory consolidation failed ({reason})."))

    else:
        render_memory_dashboard(memoria.get_summary(), memoria.get_all_triplets(), memoria.kg_limit)

    return True, None, False


async def handle_issues(
    parts: list[str],
) -> tuple[bool, Optional[Session], bool]:
    """Handle /issues command."""
    from ..issues import IssueManager
    import cowork.ui as ui

    sub = parts[1].lower() if len(parts) > 1 else ""
    user_id = get_memory_user_id()
    mgr = IssueManager(user_id, _config)

    if not sub or sub == "list":
        ui.render_issue_dashboard(mgr.get_triplet_count(), mgr.list_all())

    elif sub == "search":
        if len(parts) < 3:
            render_error("Usage: /issues search <query>")
        else:
            query = " ".join(parts[2:]).strip('"').strip("'")
            results = mgr.search_issues(query)
            ui.render_issue_search_results(query, results)

    elif sub == "add":
        # Usage: /issues add "Issue text" "Reason text" "Solution text"
        import shlex
        args = shlex.split(" ".join(parts[2:])) if len(parts) > 2 else []
        if len(args) < 3:
            render_error("Usage: /issues add \"Issue\" \"Reason\" \"Solution\"")
        else:
            tid = mgr.add_issue(args[0], args[1], args[2])
            render_success(f"✅ Issue recorded manually: {tid[:8]}")

    elif sub == "rm":
        if len(parts) < 3:
            render_error("Usage: /issues rm <id>")
        else:
            tid = parts[2]
            if mgr.delete_issue(tid):
                render_success(f"🗑️  Issue hint '{tid}' deleted.")
            else:
                all_t = mgr.list_all()
                found = [t for t in all_t if t["id"].startswith(tid)]
                if len(found) == 1:
                    mgr.delete_issue(found[0]["id"])
                    render_success(f"🗑️  Issue hint '{found[0]['id'][:8]}' deleted.")
                elif len(found) > 1:
                    render_error(f"Multiple matches for '{tid}'. Be more specific.")
                else:
                    render_error(f"Issue hint '{tid}' not found.")

    elif sub in ("clear", "clean"):
        confirm_txt = "Are you sure you want to clear ALL recorded issues?"
        if click.confirm(confirm_txt, default=False):
            mgr.clear_all()
            render_success("🧹 Issue database wiped clean.")

    elif sub == "compact":
        with ThinkingSpinner("Removing duplicate issue hints"):
            removed = mgr.compact_duplicates()
        if removed > 0:
            render_success(f"🧹 Removed {removed} duplicate issue hint(s).")
        else:
            render_success("✨ No duplicate issues found.")

    else:
        ui.render_issue_dashboard(mgr.get_triplet_count(), mgr.list_all())

    return True, None, False
