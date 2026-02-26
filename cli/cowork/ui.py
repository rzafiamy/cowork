"""
💻 Terminal UI Layer
Beautiful Rich-based interface for the Cowork CLI.
Handles all rendering: panels, spinners, live streaming, traces, dashboards.
"""

import asyncio
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Generator, Optional

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

# ── prompt_toolkit for smart input (autocomplete + history) ───────────────────
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from .theme import (
    BANNER,
    CATEGORY_STYLES,
    COWORK_THEME,
    OP_DEFAULTS,
    PALETTE,
    PHASE_LABELS,
    TAGLINE,
    TELEMETRY_STEPS,
)
from .config import is_sensitive_key

# ─── Console Singleton ────────────────────────────────────────────────────────
console = Console(theme=COWORK_THEME, highlight=True)


# ─── Banner & Welcome ─────────────────────────────────────────────────────────

def print_banner() -> None:
    console.print()
    console.print(BANNER)
    console.print(Align.center(TAGLINE))
    console.print()
    console.print(Rule(style="primary"))
    console.print()


def print_welcome(config: Any) -> None:
    """Print welcome panel with system status."""
    model = config.get("model_text", "unknown")
    endpoint = config.get("api_endpoint", "unknown")
    configured = config.is_configured()

    status_icon = "✅" if configured else "⚠️ "
    status_text = "[success]Connected[/success]" if configured else "[warning]Not configured[/warning]"

    info = Table.grid(padding=(0, 2))
    info.add_column(style="muted", justify="right")
    info.add_column()
    info.add_row("Model", f"[highlight]{model}[/highlight]")
    info.add_row("Endpoint", f"[dim_text]{endpoint}[/dim_text]")
    info.add_row("Status", f"{status_icon} {status_text}")
    info.add_row("Time", f"[dim_text]{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}[/dim_text]")

    console.print(Panel(
        info,
        title="[primary]🤖 Cowork Agentic CLI[/primary]",
        border_style="primary",
        padding=(1, 2),
    ))
    console.print()


# ─── Phase Indicators ─────────────────────────────────────────────────────────

def print_phase(phase_num: int) -> None:
    if phase_num in PHASE_LABELS:
        label, desc = PHASE_LABELS[phase_num]
        console.print(f"  {label} [dim_text]·[/dim_text] {desc}")


def print_status(message: str, style: str = "muted") -> None:
    """Print a status/telemetry line."""
    console.print(f"  [{style}]{message}[/{style}]")


# ─── Streaming Response Renderer ──────────────────────────────────────────────

import re as _re
_TABLE_RE = _re.compile(r"([^\n])\n\|")

class StreamingRenderer:
    """
    Renders streaming LLM output token-by-token with a live panel.
    Updates are throttled to ≤8 fps to avoid burning CPU on every token.
    """

    _UPDATE_INTERVAL = 0.125  # seconds (~8 fps)

    def __init__(self) -> None:
        self._buffer = ""
        self._live: Optional[Live] = None
        self._start_time = time.time()
        self._last_render = 0.0

    def start(self) -> None:
        self._buffer = ""
        self._start_time = time.time()
        self._last_render = 0.0
        self._live = Live(
            self._render(),
            console=console,
            refresh_per_second=4,
            vertical_overflow="visible",
        )
        self._live.__enter__()

    def on_token(self, token: str) -> None:
        self._buffer += token
        if self._live:
            now = time.time()
            if now - self._last_render >= self._UPDATE_INTERVAL:
                self._live.update(self._render())
                self._last_render = now

    def _render(self) -> Panel:
        elapsed = time.time() - self._start_time
        content = self._buffer or " "
        # Pre-process content for better markdown table rendering.
        # Use the pre-compiled class-level regex — avoids re-import per call.
        content_fixed = _TABLE_RE.sub(r"\1\n\n|", content)

        try:
            md = Markdown(content_fixed)
        except Exception:
            md = Text(content)

        return Panel(
            md,
            title=f"[secondary]🤖 Cowork[/secondary]  [dim_text]{elapsed:.1f}s[/dim_text]",
            border_style="secondary",
            padding=(1, 2),
            expand=True,
        )

    def stop(self) -> str:
        if self._live:
            # Final render to flush the last tokens
            self._live.update(self._render())
            self._live.__exit__(None, None, None)
            self._live = None
        return self._buffer


# ─── Thinking Spinner ─────────────────────────────────────────────────────────

class ThinkingSpinner:
    """Animated spinner shown while the agent is working."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, label: str = "Thinking") -> None:
        self.label = label
        self._status_lines: list[str] = []
        self._live: Optional[Live] = None
        self._start = time.time()
        self._last_status = ""

    def _render(self) -> Panel:
        elapsed = time.time() - self._start
        spinner_char = self.FRAMES[int(elapsed * 10) % len(self.FRAMES)]

        lines = [
            Text.from_markup(f"[primary]{spinner_char}[/primary] [bold_white]{self.label}...[/bold_white]  [dim_text]{elapsed:.1f}s[/dim_text]"),
        ]
        if self._last_status:
            lines.append(Text(""))
            lines.append(Text.from_markup(f"  [muted]{self._last_status}[/muted]"))

        # Show last 3 status lines
        recent = self._status_lines[-3:]
        for line in recent:
            lines.append(Text.from_markup(f"  [dim_text]  {line}[/dim_text]"))

        return Panel(
            Group(*lines),
            border_style="primary",
            padding=(0, 2),
        )

    def start(self) -> None:
        self._live = Live(
            self._render(),
            console=console,
            refresh_per_second=1,  # Explicit update() calls handle status changes; 1 Hz is enough for the timer counter
            transient=True,
        )
        self._live.__enter__()

    def update(self, status: str) -> None:
        self._last_status = status
        self._status_lines.append(status)
        if self._live:
            self._live.update(self._render())

    def stop(self) -> None:
        if self._live:
            self._live.__exit__(None, None, None)
            self._live = None

    def __enter__(self) -> "ThinkingSpinner":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


# ─── Response Renderer ────────────────────────────────────────────────────────

def render_response(content: str, elapsed: float, tool_calls: int = 0, step_count: int = 0) -> None:
    """Render the final agent response in a beautiful panel."""
    # Stats line
    stats_parts = [f"⏱️  {elapsed:.1f}s"]
    if tool_calls > 0:
        stats_parts.append(f"⚙️  {tool_calls} tool{'s' if tool_calls != 1 else ''}")
    if step_count > 0:
        stats_parts.append(f"🔄 {step_count} step{'s' if step_count != 1 else ''}")
    stats = "  [dim_text]" + "  ·  ".join(stats_parts) + "[/dim_text]"

    # Pre-process content for better markdown table rendering (reuse module-level compiled regex)
    content_fixed = _TABLE_RE.sub(r"\1\n\n|", content)

    try:
        body = Markdown(content_fixed)
    except Exception:
        body = Text(content)

    console.print()
    console.print(body)
    console.print(Text.from_markup(stats))
    console.print()
    
    # Push the LLM response text into the Autocompleter session words
    _get_super_completer().add_session_text(content)

def render_user_message(content: str) -> None:
    """Render the user's message."""
    console.print(Panel(
        Text(content, style="bold_white"),
        title="[primary]👤 You[/primary]",
        border_style="primary",
        padding=(0, 2),
    ))


# ─── Routing Display ──────────────────────────────────────────────────────────

def render_routing_info(categories: list[str], confidence: float, reasoning: str) -> None:
    """Show the meta-routing decision."""
    cat_displays = []
    for cat in categories:
        if cat in CATEGORY_STYLES:
            cat_displays.append(CATEGORY_STYLES[cat][0])
        else:
            cat_displays.append(f"[muted]{cat}[/muted]")

    cats_str = "  +  ".join(cat_displays)
    conf_bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="muted", justify="right", width=14)
    grid.add_column()
    grid.add_row("Domain", cats_str)
    grid.add_row("Confidence", f"[success]{conf_bar}[/success] [dim_text]{confidence:.0%}[/dim_text]")
    if reasoning:
        grid.add_row("Reasoning", f"[italic_muted]{reasoning[:80]}[/italic_muted]")

    console.print(Panel(
        grid,
        title="[phase2]🧭 Meta-Router Decision[/phase2]",
        border_style="router",
        padding=(0, 1),
    ))


def render_skill_info(name: str, score: float, tier: int, description: str = "", categories: list[str] = None) -> None:
    """Show the activated skill detail."""
    tier_star = "★" * tier + "☆" * (4 - tier)
    tier_color = "success" if tier >= 3 else "warning" if tier == 2 else "error"
    
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="muted", justify="right", width=14)
    grid.add_column()
    grid.add_row("Skill", f"[highlight]{name}[/highlight]")
    grid.add_row("Precision", f"[highlight]{score:.2f}[/highlight]")
    grid.add_row("Trust Tier", f"[{tier_color}]{tier_star}[/{tier_color}] [dim_text](Tier {tier})[/dim_text]")
    
    if categories:
        cats_styled = [f"[tool]{c.replace('_TOOLS', '')}[/tool]" for c in categories]
        grid.add_row("Capabilities", " + ".join(cats_styled))

    if description:
        grid.add_row("Description", f"[italic_muted]{description[:80].strip()}[/italic_muted]")

    console.print(Panel(
        grid,
        title="[phase3]🧩 Skill Activation[/phase3]",
        border_style="primary",
        padding=(0, 1),
    ))


def render_plan_info(plan: dict) -> None:
    """
    Render the Plan-then-Execute plan as a rich panel.
    Called after Phase 2.5 completes, before the REACT loop starts.
    """
    if not plan:
        return

    goal = plan.get("goal", "")
    complexity = plan.get("complexity", "?")
    steps = plan.get("steps", [])

    # If the planner decided it's a direct/simple answer, show a lean one-liner
    if not steps or (len(steps) == 1 and steps[0].get("tool") == "direct_answer"):
        console.print(
            f"  [dim_text]🗺️  Planner: direct answer — no multi-step plan needed[/dim_text]"
        )
        return

    complexity_color = {
        "simple": "success",
        "moderate": "accent",
        "complex": "error",
    }.get(complexity, "accent")

    # Build step tree
    tree = Tree(
        Text.from_markup(
            f"[accent]🗺️  Execution Plan[/accent]  "
            f"[dim_text]complexity=[/dim_text][{complexity_color}]{complexity}[/{complexity_color}]"
        )
    )
    for s in steps:
        tool_name = s.get("tool", "?")
        action = s.get("action", "")
        rationale = s.get("rationale", "")
        deps = s.get("depends_on", [])
        parallel = s.get("can_parallelize", False)

        tool_tag = f"[tool]{tool_name}[/tool]" if tool_name not in ("reasoning", "direct_answer") else f"[muted]{tool_name}[/muted]"
        dep_txt = f" [dim_text](after {deps})[/dim_text]" if deps else ""
        par_txt = " [secondary]‖[/secondary]" if parallel else ""

        branch = tree.add(
            Text.from_markup(
                f"[dim_text]{s.get('id','?')}.[/dim_text] {tool_tag} [bold_white]{action[:70]}[/bold_white]{dep_txt}{par_txt}"
            )
        )
        if rationale:
            branch.add(Text.from_markup(f"[italic_muted]↳ {rationale[:90]}[/italic_muted]"))

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="muted", justify="right", width=10)
    grid.add_column()
    grid.add_row("Goal", f"[bold_white]{goal[:100]}[/bold_white]")
    grid.add_row("Steps", f"[accent]{len(steps)}[/accent]")

    console.print(Panel(
        Group(grid, Rule(style="accent"), tree),
        title="[accent]🗺️  Phase 2.5 · Plan-then-Execute[/accent]",
        border_style="accent",
        padding=(0, 1),
    ))


# ─── Session List ─────────────────────────────────────────────────────────────

def render_session_list(sessions: list[dict]) -> None:
    """Render a table of available sessions."""
    if not sessions:
        console.print(Panel(
            "[muted]No sessions found. Start a new conversation![/muted]",
            title="[primary]📋 Sessions[/primary]",
            border_style="primary",
        ))
        return

    table = Table(
        title="📋 Recent Sessions",
        box=box.ROUNDED,
        border_style="primary",
        header_style="primary",
        show_lines=True,
    )
    table.add_column("#", style="muted", width=4, justify="right")
    table.add_column("Title", style="bold_white", min_width=20)
    table.add_column("Workspace Folder", style="accent", min_width=15)
    table.add_column("Messages", justify="center", style="highlight")
    table.add_column("Last Active", style="dim_text")
    table.add_column("Session ID", style="muted", width=10)

    for i, s in enumerate(sessions[:15], 1):
        updated = s.get("updated_at", "")[:16].replace("T", " ")
        table.add_row(
            str(i),
            s.get("title", "Untitled")[:40],
            s.get("slug", "—"),
            str(s.get("message_count", 0)),
            updated,
            s.get("session_id", "")[:8],
        )

    console.print(table)


# ─── Config Display ───────────────────────────────────────────────────────────

def render_config(config_data: dict) -> None:
    """Render current configuration in a table."""
    table = Table(
        title="⚙️  Configuration",
        box=box.ROUNDED,
        border_style="accent",
        header_style="accent",
        show_lines=False,
    )
    table.add_column("Setting", style="highlight", min_width=30)
    table.add_column("Value", style="text")

    for key, value in sorted(config_data.items()):
        if is_sensitive_key(key):
            display_val = "●●●●●●●●" if value else "[error]Not set[/error]"
        else:
            display_val = str(value)
        table.add_row(key, display_val)

    console.print(table)


# ─── Memory Display ───────────────────────────────────────────────────────────

def render_memory_status(triplet_count: int, summary: str, triplet_limit: int = 100) -> None:
    """Render Memoria status."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="muted", justify="right", width=16)
    grid.add_column()
    
    # Progress visualization for KG limit
    pct = (triplet_count / triplet_limit) if triplet_limit > 0 else 0
    bar_len = int(pct * 10)
    bar = "█" * min(10, bar_len) + "░" * max(0, 10 - bar_len)
    bar_color = "success" if pct < 0.7 else "warning" if pct < 0.9 else "error"
    
    grid.add_row("Knowledge Facts", f"[memory]{triplet_count}/{triplet_limit}[/memory] [{bar_color}]{bar}[/{bar_color}]")
    grid.add_row("Session Summary", f"[dim_text]{summary[:100] + '...' if len(summary) > 100 else summary or '(none yet)'}[/dim_text]")

    console.print(Panel(
        grid,
        title="[memory]🧠 Memoria Status[/memory]",
        border_style="memory",
        padding=(0, 1),
    ))


# ─── Job Dashboard ────────────────────────────────────────────────────────────

def render_job_dashboard(jobs: list[Any]) -> None:
    """Render the Sentinel job queue dashboard."""
    if not jobs:
        console.print("[muted]No recent jobs.[/muted]")
        return

    table = Table(
        title="🚦 Sentinel Job Queue",
        box=box.ROUNDED,
        border_style="sentinel",
        header_style="sentinel",
        show_lines=True,
    )
    table.add_column("Job ID", style="muted", width=10)
    table.add_column("Status", justify="center")
    table.add_column("Steps", justify="center", style="highlight")
    table.add_column("Tools", justify="center", style="tool")
    table.add_column("Categories", style="router")
    table.add_column("Created", style="dim_text")

    status_styles = {
        "completed": "[success]✅ done[/success]",
        "running":   "[warning]⚡ running[/warning]",
        "failed":    "[error]❌ failed[/error]",
        "pending":   "[muted]⏳ pending[/muted]",
        "cancelled": "[muted]🚫 cancelled[/muted]",
    }

    for job in jobs[:20]:
        status_display = status_styles.get(job.status, job.status)
        cats = ", ".join(job.categories[:2]) if job.categories else "—"
        created = job.created_at[:16].replace("T", " ") if job.created_at else "—"
        table.add_row(
            job.job_id[:8],
            status_display,
            str(job.steps),
            str(job.tool_calls),
            cats,
            created,
        )

    console.print(table)


# ─── Cron Dashboard ───────────────────────────────────────────────────────────

def render_cron_list(jobs: list[Any]) -> None:
    """Render the Cron job dashboard."""
    if not jobs:
        console.print(Panel(
            "[muted]No scheduled cron jobs. Tell the AI to schedule a task![/muted]",
            title="[sentinel]⏰ Cron Scheduler[/sentinel]",
            border_style="sentinel",
        ))
        return

    table = Table(
        title="⏰ Scheduled Cron Jobs",
        box=box.ROUNDED,
        border_style="sentinel",
        header_style="sentinel",
        show_lines=True,
    )
    table.add_column("Job ID", style="muted", width=10)
    table.add_column("Prompt Preview", style="highlight", min_width=28)
    table.add_column("Schedule", justify="center", style="accent")
    table.add_column("Next Run", justify="center", style="bold_white")
    table.add_column("Last Run", justify="center", style="dim_text")
    table.add_column("Status", justify="center")
    table.add_column("Runs", justify="center", style="muted")

    status_styles = {
        "enabled":  "[success]● active[/success]",
        "disabled": "[muted]○ disabled[/muted]",
        "running":  "[warning]⚡ running[/warning]",
        "failed":   "[error]❌ failed[/error]",
    }

    for job in jobs:
        status_display = status_styles.get(job.status, job.status)
        prompt = job.prompt[:48] + "…" if len(job.prompt) > 48 else job.prompt
        next_run = job.next_run[:16].replace("T", " ") if job.next_run else "—"
        last_run = job.last_run[:16].replace("T", " ") if getattr(job, "last_run", None) else "Never"
        schedule = f"{job.schedule_type}: {job.schedule_value}"

        table.add_row(
            job.job_id,
            prompt,
            schedule,
            next_run,
            last_run,
            status_display,
            str(job.run_count),
        )

    console.print(table)


def render_cron_result(job: Any) -> None:
    """Render the full details and last result of a cron job."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="highlight", justify="right", width=16)
    grid.add_column()
    grid.add_row("Job ID", job.job_id)
    grid.add_row("Prompt", job.prompt)
    grid.add_row("Schedule", f"{job.schedule_type} ({job.schedule_value})")
    grid.add_row("Last Run", job.last_run or "Never")
    grid.add_row("Next Run", job.next_run or "Finished")
    grid.add_row("Runs", str(job.run_count))
    grid.add_row("Session ID", job.session_id or "—")

    result_content = job.last_result or "*No result yet. Wait for the next run.*"
    try:
        res_md = Markdown(result_content)
    except Exception:
        res_md = Text(result_content)

    console.print(Panel(
        Group(grid, Rule(style="muted"), Text("Last Execution Result:", style="accent"), res_md),
        title=f"[sentinel]⏰ Cron Job: {job.job_id}[/sentinel]",
        border_style="sentinel",
        padding=(1, 2),
    ))


# ─── Memory Dashboard ──────────────────────────────────────────────────────────

def render_memory_dashboard(summary: str, triplets: list[dict], triplet_limit: int = 500) -> None:
    """Render a comprehensive view of the agent's memory."""
    
    # 1. Session Summary
    summary_panel = Panel(
        summary or "[muted](No session summary yet)[/muted]",
        title="[accent]📝 Session Context Summary[/accent]",
        border_style="accent",
        padding=(1, 2)
    )

    # 2. Knowledge Graph Table
    table = Table(
        box=box.ROUNDED,
        border_style="sentinel",
        header_style="sentinel",
        show_lines=True,
        expand=True
    )
    table.add_column("ID", style="muted", width=10)
    table.add_column("Subject", style="highlight")
    table.add_column("Predicate", style="accent")
    table.add_column("Object", style="bold_white")
    table.add_column("Added", style="dim_text", justify="right")

    for t in triplets[:30]: # Limit to 30 for display
        added = t.get("created_at", "")[:10]
        table.add_row(
            t["id"][:8],
            t["subject"],
            t["predicate"],
            t["object"],
            added
        )

    kg_panel = Panel(
        table if triplets else "[muted]No long-term persona facts found.[/muted]",
        title=f"[sentinel]🧠 Knowledge Graph ({len(triplets)}/{triplet_limit} facts)[/sentinel]",
        border_style="sentinel",
    )

    console.print(summary_panel)
    console.print(kg_panel)


def render_memory_search_results(query: str, results: list[dict]) -> None:
    """Render the results of a semantic memory search."""
    if not results:
        console.print(Panel(
            f"[muted]No memories found matching '[highlight]{query}[/highlight]'.[/muted]",
            title="[memory]🔍 Vector Search[/memory]",
            border_style="memory",
        ))
        return

    table = Table(
        box=box.ROUNDED,
        border_style="memory",
        header_style="memory",
        show_lines=True,
        expand=True
    )
    table.add_column("Rank", style="muted", width=6, justify="right")
    table.add_column("Fact (Subject → Predicate → Object)", style="bold_white")
    table.add_column("Score", justify="right")
    table.add_column("ID", style="muted", width=10)

    for i, t in enumerate(results[:15], 1):
        score = t.get("weight", 0.0)
        score_color = "success" if score > 0.7 else "warning" if score > 0.4 else "muted"
        
        fact = f"[highlight]{t['subject']}[/highlight] [accent]{t['predicate']}[/accent] [bold_white]{t['object']}[/bold_white]"
        
        table.add_row(
            str(i),
            fact,
            f"[{score_color}]{score:.2f}[/{score_color}]",
            t["id"][:8]
        )

    console.print(Panel(
        table,
        title=f"[memory]🔍 Vector Search: '{query}' ({len(results)} matches)[/memory]",
        border_style="memory",
    ))


# ─── Issue Dashboard ──────────────────────────────────────────────────────────

def render_issue_dashboard(count: int, issues: list[dict]) -> None:
    """Render a view of the agent's Issue Manager."""
    
    if not issues:
        console.print(Panel(
            "[muted]No issues recorded yet. When tools fail and get fixed, they'll appear here.[/muted]",
            title="[sentinel]🚨 Issue Manager Database[/sentinel]",
            border_style="sentinel"
        ))
        return

    table = Table(
        box=box.ROUNDED,
        border_style="sentinel",
        header_style="sentinel",
        show_lines=True,
        expand=True
    )
    table.add_column("ID", style="muted", width=10)
    table.add_column("Issue / Reason", style="warning")
    table.add_column("Solution", style="success")
    table.add_column("Recorded", style="dim_text", justify="right")

    for t in issues[:30]: # Limit display
        added = t.get("created_at", "")[:10]
        issue_reason = f"[bold_white]{t['issue']}[/bold_white]\n[dim_text]{t['reason']}[/dim_text]"
        table.add_row(
            t["id"][:8],
            issue_reason,
            t["solution"],
            added
        )

    console.print(Panel(
        table,
        title=f"[sentinel]🚨 Issue Manager Database ({count} total)[/sentinel]",
        border_style="sentinel",
    ))

def render_issue_search_results(query: str, results: list[dict]) -> None:
    """Render the results of an issue search."""
    if not results:
        console.print(Panel(
            f"[muted]No issues found matching '[highlight]{query}[/highlight]'.[/muted]",
            title="[sentinel]🔍 Issue Search[/sentinel]",
            border_style="sentinel",
        ))
        return

    table = Table(
        box=box.ROUNDED,
        border_style="sentinel",
        header_style="sentinel",
        show_lines=True,
        expand=True
    )
    table.add_column("Rank", style="muted", width=6, justify="right")
    table.add_column("Issue", style="warning")
    table.add_column("Solution", style="success")
    table.add_column("Score", justify="right")
    table.add_column("ID", style="muted", width=10)

    for i, t in enumerate(results[:15], 1):
        score = t.get("similarity", 0.0)
        score_color = "success" if score > 0.7 else "warning" if score > 0.4 else "muted"
        
        issue_text = f"[bold_white]{t['issue']}[/bold_white]\n[dim_text]{t['reason']}[/dim_text]"
        
        table.add_row(
            str(i),
            issue_text,
            t["solution"],
            f"[{score_color}]{score:.2f}[/{score_color}]",
            t["id"][:8]
        )

    console.print(Panel(
        table,
        title=f"[sentinel]🔍 Issue Search: '{query}' ({len(results)} matches)[/sentinel]",
        border_style="sentinel",
    ))


# ─── Token Usage Display ────────────────────────────────────────────────────────────

def render_token_usage(entries: list[dict], totals: dict) -> None:
    """Render a rich table of token usage per model/endpoint."""
    if not entries:
        console.print(Panel(
            "[muted]No token usage recorded yet. Start chatting to see stats![/muted]",
            title="[accent]📊 Token Usage[/accent]",
            border_style="accent",
        ))
        return

    table = Table(
        title="📊 Token Usage by Model / Endpoint",
        box=box.ROUNDED,
        border_style="accent",
        header_style="accent",
        show_lines=True,
    )
    table.add_column("Model",              style="highlight",  min_width=18)
    table.add_column("Endpoint",           style="dim_text",   min_width=22)
    table.add_column("Requests",           justify="right",    style="muted")
    table.add_column("Prompt ↑",           justify="right",    style="router")
    table.add_column("Completion ↓",       justify="right",    style="tool")
    table.add_column("Total",              justify="right",    style="bold_white")
    table.add_column("Last Used",          style="dim_text")

    grand_total = totals.get("total_tokens", 0)

    for entry in entries:
        total = entry.get("total_tokens", 0)
        pct = (total / grand_total * 100) if grand_total else 0
        bar_len = int(pct / 10)  # 0-10 blocks
        bar = "█" * bar_len + "░" * (10 - bar_len)
        last_seen = entry.get("last_seen", "")[:16].replace("T", " ")
        table.add_row(
            entry.get("model", "unknown"),
            entry.get("endpoint", ""),
            f"{entry.get('request_count', 0):,}",
            f"{entry.get('prompt_tokens', 0):,}",
            f"{entry.get('completion_tokens', 0):,}",
            f"{total:,}  [dim]{bar} {pct:.0f}%[/dim]",
            last_seen,
        )

    # Totals footer
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="muted", justify="right", width=18)
    grid.add_column()
    grid.add_row("Total Requests",    f"[bold_white]{totals.get('request_count', 0):,}[/bold_white]")
    grid.add_row("Total Prompt",      f"[router]{totals.get('prompt_tokens', 0):,}[/router] tokens")
    grid.add_row("Total Completion",  f"[tool]{totals.get('completion_tokens', 0):,}[/tool] tokens")
    grid.add_row("Grand Total",       f"[bold_white]{grand_total:,}[/bold_white] tokens")

    console.print(table)
    console.print(Panel(
        grid,
        title="[accent]Σ Cumulative Totals[/accent]",
        border_style="accent",
        padding=(0, 2),
    ))


# ─── AI Profile Display ────────────────────────────────────────────────────────────

def render_ai_profiles(profiles: list[dict]) -> None:
    """Render a table of saved AI profiles."""
    if not profiles:
        console.print(Panel(
            "[muted]No AI profiles saved yet.\n\n"
            "[dim_text]Use [highlight]/ai add <name> <endpoint> <model>[/highlight] to add one.[/dim_text]",
            title="[primary]🤖 AI Profiles[/primary]",
            border_style="primary",
        ))
        return

    table = Table(
        title="🤖 AI Profiles",
        box=box.ROUNDED,
        border_style="primary",
        header_style="primary",
        show_lines=True,
    )
    table.add_column("Active",       justify="center", width=6)
    table.add_column("Name",         style="highlight", min_width=12)
    table.add_column("Model",        style="bold_white", min_width=16)
    table.add_column("Endpoint",     style="dim_text",   min_width=24)
    table.add_column("API Key",      style="muted",      width=12)
    table.add_column("Description",  style="text")

    for p in profiles:
        active_mark = "[success]★ active[/success]" if p.get("active") else "[dim_text]○[/dim_text]"
        key_display = "●●●●●●●●" if p.get("api_key") else "[muted](shared)[/muted]"
        table.add_row(
            active_mark,
            p["name"],
            p["model"],
            p["endpoint"],
            key_display,
            p.get("description", "")[:40],
        )

    console.print(table)


def render_model_list(models: list[str], current_model: str) -> None:
    """Render a table of available AI models."""
    if not models:
        console.print(Panel(
            "[muted]No models found or endpoint doesn't support listing.[/muted]",
            title="[primary]🤖 AI Models[/primary]",
            border_style="primary",
        ))
        return

    table = Table(
        title="🤖 Available AI Models",
        box=box.ROUNDED,
        border_style="primary",
        header_style="primary",
        show_lines=False,
    )
    table.add_column("Status", justify="center", width=8)
    table.add_column("Model ID", style="highlight")

    for m in sorted(models):
        active = "[success]★ active[/success]" if m == current_model else "[dim_text]○[/dim_text]"
        table.add_row(active, m)

    console.print(table)
    console.print(f"  [dim_text]Use [highlight]/model <id>[/highlight] to switch models.[/dim_text]")


def render_tools_list(tools: list[dict]) -> None:
    """Render a table of all activated tools."""
    if not tools:
        console.print("[muted]No tools available.[/muted]")
        return

    table = Table(
        title="🛠️  Activated Tools",
        box=box.ROUNDED,
        border_style="tool",
        header_style="tool",
        show_lines=True,
    )
    table.add_column("Category", style="router", width=18)
    table.add_column("Tool Name", style="highlight", width=22)
    table.add_column("Description", style="text")

    # Group by category
    tools_sorted = sorted(tools, key=lambda x: (x["category"], x["function"]["name"]))
    
    for t in tools_sorted:
        func = t["function"]
        table.add_row(
            t["category"],
            func["name"],
            func["description"].split(".")[0] + ".",  # Show first sentence
        )

    console.print(table)
    console.print(f"  [dim_text]Total {len(tools)} tools activated across all domains.[/dim_text]")


def render_error(message: str, hint: str = "") -> None:
    content = f"[error]{message}[/error]"
    if hint:
        content += f"\n\n[muted]💡 Hint: {hint}[/muted]"
    console.print(Panel(content, title="[error]❌ Error[/error]", border_style="error", padding=(0, 2)))


def render_success(message: str) -> None:
    console.print(Panel(f"[success]{message}[/success]", border_style="success", padding=(0, 2)))


def render_warning(message: str) -> None:
    console.print(Panel(f"[warning]{message}[/warning]", border_style="warning", padding=(0, 2)))


def confirm_tool_call(tool_name: str, reason: str, args: dict) -> bool:
    """Prompt the user to approve a tool call."""
    from rich.syntax import Syntax
    import json

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="highlight", justify="right", width=14)
    grid.add_column()
    grid.add_row("Action", f"[bold_white]{tool_name}[/bold_white]")
    grid.add_row("Policy", f"[warning]{reason}[/warning]")
    
    args_json = json.dumps(args, indent=2)
    syntax = Syntax(args_json, "json", theme="monokai", background_color="default")
    
    panel = Panel(
        Group(
            grid,
            Text(""),
            Text("Arguments:", style="muted"),
            syntax,
            Text(""),
            Text("Allow this tool to execute?", style="bold_white"),
        ),
        title="[sentinel]🛡️ Firewall Confirmation[/sentinel]",
        border_style="sentinel",
        padding=(1, 2),
    )
    
    console.print()
    console.print(panel)
    
    return Confirm.ask("Proceed?", default=False, console=console)


def render_session_stats(stats: dict) -> None:
    """Render a comprehensive dashboard of current session statistics."""
    from rich.columns import Columns

    # 1. Session Info Card
    s_grid = Table.grid(padding=(0, 2))
    s_grid.add_column(style="highlight", justify="right", width=14)
    s_grid.add_column()
    s_grid.add_row("Session ID", stats["session_id"])
    s_grid.add_row("Title", stats["title"])
    s_grid.add_row("Created", stats["created_at"])
    s_grid.add_row("Messages", f"[bold_white]{stats['message_count']}[/bold_white]")
    
    s_panel = Panel(s_grid, title="[primary]🆔 Session[/primary]", border_style="primary")

    # 2. Memory Card
    m_grid = Table.grid(padding=(0, 2))
    m_grid.add_column(style="sentinel", justify="right", width=14)
    m_grid.add_column()
    m_grid.add_row("Knowledge", f"[bold_white]{stats['memory_triplets']}[/bold_white] facts")
    m_grid.add_row("Summary", "[success]active[/success]" if stats["has_summary"] else "[muted]none[/muted]")
    m_grid.add_row("User ID", stats["user_id"])
    
    m_panel = Panel(m_grid, title="[sentinel]🧠 Memory[/sentinel]", border_style="sentinel")

    # 3. Scratchpad Card
    sc_grid = Table.grid(padding=(0, 2))
    sc_grid.add_column(style="memory", justify="right", width=14)
    sc_grid.add_column()
    sc_grid.add_row("Items", f"[bold_white]{stats['scratchpad_items']}[/bold_white]")
    sc_grid.add_row("Total Size", f"{stats['scratchpad_chars']:,} chars")
    
    sc_panel = Panel(sc_grid, title="[memory]📝 Scratchpad[/memory]", border_style="memory")

    # 4. Workspace Card
    ws_panel = Panel(
        f"[dim_text]{stats['workspace_path']}[/dim_text]",
        title="[highlight]📂 Workspace[/highlight]",
        border_style="highlight"
    )

    # 5. Token Usage Card
    t_grid = Table.grid(padding=(0, 2))
    t_grid.add_column(style="accent", justify="right", width=14)
    t_grid.add_column()
    t_grid.add_row("Total Tokens", f"[bold_white]{stats['total_tokens']:,}[/bold_white]")
    t_grid.add_row("Requests", f"{stats['request_count']:,}")
    t_grid.add_row("Prompt", f"[router]{stats['prompt_tokens']:,}[/router]")
    t_grid.add_row("Completion", f"[tool]{stats['completion_tokens']:,}[/tool]")
    
    t_panel = Panel(t_grid, title="[accent]📊 Token Usage (Total)[/accent]", border_style="accent")

    # Layout
    console.print(Panel(
        Group(
            Columns([s_panel, m_panel, sc_panel], expand=True),
            ws_panel,
            t_panel
        ),
        title="[highlight]🚀 Cowork Session Statistics[/highlight]",
        border_style="highlight",
        padding=(1, 2)
    ))



# ─── Help Display ─────────────────────────────────────────────────────────────

def render_help() -> None:
    """Render the help panel with all commands."""
    commands = [
        ("/help",                          "Show this help message"),
        ("/new",                            "Start a new session"),
        ("/sessions",                       "List all sessions"),
        ("/sessions rm <index>",            "Delete a session by index"),
        ("/sessions retitle",               "Batch re-title all sessions via AI analysis"),
        ("/sessions search <q>",            "Regex search sessions (use --title/--content)"),
        ("/load <id>",                      "Load a session by ID or number"),
        ("/memory",                         "Show memory dashboard (summary + facts)"),
        ("/memory search <query>",           "Explicit vector search for persona facts"),
        ("/memory add <sub> <pred> <obj>",  "Manually insert a long-term knowledge fact"),
        ("/memory rm <id>",                 "Delete a memory fact by ID"),
        ("/memory compress",               "Consolidate Knowledge Graph / deduplicate"),
        ("/memory prune",                  "Remove non-durable (task/transient) memory facts"),
        ("/memory clear",                   "Clear all session and persona memory"),
        ("/vector <...>",                   "Alias for /memory"),
        ("/jobs",                           "Show Sentinel job dashboard"),
        ("/jobs clean",                     "Wipe all job history"),
        ("/jobs resume <id>",               "Resume a job by its ID prefix"),
        ("/issues",                         "Manage the Issue Manager database"),
        ("/issues list",                    "List recorded tool issues and solutions"),
        ("/issues search <query>",          "Search recorded issues"),
        ("/issues rm <id>",                 "Remove an issue by ID"),
        ("/config",                         "Show current configuration"),
        ("/config set <key> <value>",        "Update a configuration value"),
        ("/stats or /st",                   "Show session statistics (memory, tokens, etc)"),
        ("/tokens",                         "Show token usage per model/endpoint"),
        ("/tokens reset",                   "Reset all token usage counters"),
        ("/reset",                          "Delete all ~/.cowork/* data and exit"),
        ("/cron",                           "List all scheduled cron jobs"),
        ("/cron add <type> <time> <prompt>", "Add a new cron job (type: once|daily|weekly)"),
        ("/cron view <id>",                 "View details and last execution result"),
        ("/cron run <id>",                  "Force-run a cron job immediately"),
        ("/cron search <query>",            "Search cron jobs by prompt or schedule"),
        ("/cron rm <id>",                   "Remove a scheduled task"),
        ("/ai",                             "List saved AI profiles"),
        ("/ai add <name> <endpoint> <model>","Add a new AI profile"),
        ("/ai switch <name>",               "Switch to a saved AI profile"),
        ("/ai remove <name>",               "Remove a saved AI profile"),
        ("/ai save <name>",                 "Save current config as a profile"),
        ("/mm",                             "Show multi-modal service status"),
        ("/mm <service> <field> <value>",   "Configure vision/image/ASR/TTS services"),
        ("/model",                          "List available AI models on current endpoint"),
        ("/model <name>",                   "Switch to a specific AI model"),
        ("/open <path>",                    "Open a specific file locally (no AI)"),
        ("/workspace open",          "Open workspace folder path in terminal"),
        ("/workspace clean",         "Delete all sessions and workspace folders"),
        ("/scratchpad",                     "List scratchpad contents"),
        ("/scratchpad read <no>",           "Read one scratchpad item by number"),
        ("/tools",                          "List all activated tools"),
        ("/trace",                          "Show last job trace summary"),
        ("/trace llm",                     "Monitor LLM prompt composition (system/user)"),
        ("/trace full",                     "Render full readable trace events"),
        ("/trace clean",                    "Delete all saved trace files"),
        ("/trace raw",                      "Print raw JSON trace events"),
        ("/trace path",                     "Show trace file path"),
        ("/clear",                          "Clear the terminal"),
        ("/exit or /quit",                  "Exit Cowork"),
    ]

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Command", style="highlight", min_width=30)
    table.add_column("Description", style="text")

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    pills = Table.grid(padding=(0, 1))
    pills.add_column()
    pills.add_row("[accent]⚡ Action Pills[/accent]")
    pills.add_row("[dim_text]Type a message naturally or use /commands[/dim_text]")
    pills.add_row("[dim_text]Hashtags like #research, #task, or #coding route your intent[/dim_text]")

    console.print(Panel(
        Group(table, Rule(style="muted"), pills),
        title="[primary]📖 Cowork Help[/primary]",
        border_style="primary",
        padding=(1, 2),
    ))


# ─── Setup Wizard ─────────────────────────────────────────────────────────────

def run_setup_wizard(config: Any) -> bool:
    """Interactive first-time setup wizard."""
    console.print(Panel(
        "[warning]⚠️  Cowork is not configured yet.[/warning]\n\n"
        "[text]Let's set up your AI endpoint to get started.[/text]",
        title="[accent]🚀 First-Time Setup[/accent]",
        border_style="accent",
        padding=(1, 2),
    ))

    console.print()
    console.print("[muted]Press Enter to use the default value shown in brackets.[/muted]")
    console.print()

    endpoint = Prompt.ask(
        "[highlight]API Endpoint[/highlight]",
        default=config.get("api_endpoint", "https://api.openai.com/v1"),
        console=console,
    )
    api_key = Prompt.ask(
        "[highlight]API Key[/highlight]",
        password=True,
        console=console,
    )
    model = Prompt.ask(
        "[highlight]Model[/highlight]",
        default=config.get("model_text", "gpt-4o-mini"),
        console=console,
    )

    if not api_key:
        render_error("API key is required.")
        return False

    config.set("api_endpoint", endpoint)
    config.set("api_key", api_key)
    config.set("model_text", model)
    config.set("model_router", model)
    config.set("model_compress", model)

    render_success(f"✅ Configuration saved! Using model: {model}")
    return True


# ─── Slash Command Definitions (for autocomplete) ────────────────────────────

SLASH_COMMANDS: list[tuple[str, str]] = [
    ("/help",                    "Show all available commands"),
    ("/new",                     "Start a fresh session"),
    ("/sessions",                "List all saved sessions"),
    ("/sessions rm ",            "Delete a session by index  e.g. /sessions rm 5"),
    ("/sessions retitle",        "Batch re-title all sessions using AI analysis"),
    ("/sessions search ",        "Regex-based search across sessions"),
    ("/load ",                   "Load session by ID or number  e.g. /load 1"),
    ("/workspace",               "Show current session workspace folder"),
    ("/workspace list",          "List all workspace sessions"),
    ("/workspace search ",       "Search across sessions  e.g. /workspace search python"),
    ("/workspace open",          "Open workspace folder path in terminal"),
    ("/workspace clean",         "Delete all sessions and workspace folders"),
    ("/jobs",                    "Show Sentinel job queue dashboard"),
    ("/jobs clean",              "Wipe all job history"),
    ("/jobs resume ",            "Resume job by ID prefix  e.g. /jobs resume abc12"),
    ("/config",                  "Show current configuration"),
    ("/config set ",             "Set a config value  e.g. /config set stream false"),
    ("/stats",                   "Show session statistics and resource usage"),
    ("/st",                      "Show session statistics and resource usage"),
    ("/tokens",                  "Show token usage per model / endpoint"),
    ("/tokens reset",            "Reset all token usage counters"),
    ("/reset",                   "Delete all ~/.cowork/* data and exit"),
    ("/cron",                           "List all scheduled cron jobs"),
    ("/cron add ",                        "Add a job  e.g. /cron add daily 09:00 Send weather report"),
    ("/cron view ",                      "View cron job result  e.g. /cron view abc12345"),
    ("/cron run ",                        "Force-run a job now  e.g. /cron run abc12345"),
    ("/cron search ",                     "Search jobs  e.g. /cron search daily"),
    ("/cron rm ",                         "Remove a cron job  e.g. /cron rm abc12345"),
    ("/memory",                         "Show memory dashboard (context + facts)"),
    ("/memory search ",                  "Search knowledge facts  e.g. /memory search python"),
    ("/memory add ",                     "Manually add a fact  e.g. /memory add User likes pizza"),
    ("/memory rm ",                      "Delete a memory fact  e.g. /memory rm 12345678"),
    ("/memory compress",               "Consolidate KG (deduplicate/merge)"),
    ("/memory prune",                  "Remove non-durable memory facts"),
    ("/memory clear",                   "Wipe all persona/session memory"),
    ("/vector",                         "Alias for /memory (e.g. /vector search)"),
    ("/vector search ",                  "Explicit semantic search for facts"),
    ("/vector add ",                     "Manually insert a knowledge fact"),
    ("/issues",                  "List recently recorded tool issues"),
    ("/issues search ",          "Search past issues for hints  e.g. /issues search timeout"),
    ("/issues rm ",              "Delete an issue  e.g. /issues rm 12345"),
    ("/ai",                      "List saved AI profiles"),
    ("/ai add ",                 "Add AI profile  e.g. /ai add gpt4 https://api.openai.com/v1 gpt-4o"),
    ("/ai switch ",              "Switch to a profile  e.g. /ai switch gpt4"),
    ("/ai remove ",              "Remove a profile  e.g. /ai remove gpt4"),
    ("/ai save ",                "Save current config as profile  e.g. /ai save myprofile"),
    ("/model",                   "List available AI models on current endpoint"),
    ("/model <name>",            "Switch to a specific AI model"),
    ("/scratchpad",              "List scratchpad contents for this session"),
    ("/scratchpad read ",        "Read scratchpad item  e.g. /scratchpad read 2"),
    ("/tools",                   "List all active tools (built-in + configured)"),
    ("/trace",                   "Show execution trace summary of last job"),
    ("/trace llm",               "Monitor LLM prompt composition (system/user)"),
    ("/trace full",              "Render full readable trace events"),
    ("/trace clean",             "Wipe all trace history from disk"),
    ("/trace raw",               "Print raw JSON trace events"),
    ("/trace path",              "Show current trace file path"),
    ("/open ",                    "Open a workspace artifact file locally"),
    ("/clear",                   "Clear the terminal screen"),
    ("/exit",                    "Exit Cowork (also: /quit or /q)"),
    ("/quit",                    "Exit Cowork"),
]

HASHTAG_PILLS: list[tuple[str, str]] = [
    ("#research",  "Route to search and knowledge tools"),
    ("#task",      "Route to Kanban / task management"),
    ("#kanban",    "Route to Kanban board"),
    ("#calc",      "Route to math and calculation tools"),
    ("#math",      "Route to math and calculation tools"),
    ("#coding",    "Route to code tools (web/python/dev)"),
    ("#code",      "Route to code tools (web/python/dev)"),
    ("#web",       "Route to code tools (web/python/dev)"),
    ("#note",      "Route to notes and workspace tools"),
    ("#workspace", "Route to workspace file tools"),
]


# ─── Cowork Completer ─────────────────────────────────────────────────────────

from .autocompleter import SuperCompleter, HistoryDB
import os

_super_completer: Optional[SuperCompleter] = None
_history_db: Optional[HistoryDB] = None

def _get_super_completer() -> SuperCompleter:
    global _super_completer, _history_db
    if _super_completer is None:
        _super_completer = SuperCompleter(SLASH_COMMANDS, HASHTAG_PILLS)
        _history_db = _super_completer.db
    return _super_completer

# ─── prompt_toolkit Style ─────────────────────────────────────────────────────

PT_STYLE = PTStyle.from_dict({
    # Prompt itself
    "prompt":          "#7C3AED bold",
    "session-title":   "#4B5563",
    # Completion menu
    "completion-menu.completion":          "bg:#1E1B4B #E2E8F0",
    "completion-menu.completion.current":  "bg:#7C3AED #ffffff bold",
    "completion-menu.meta.completion":     "bg:#111827 #6B7280",
    "completion-menu.meta.completion.current": "bg:#5B21B6 #D1D5DB",
    "scrollbar.background":                "bg:#1E1B4B",
    "scrollbar.button":                    "bg:#7C3AED",
    # Auto-suggest ghost text
    "auto-suggest":    "#374151",
})


# ─── Persistent PromptSession (module-level singleton) ────────────────────────

_HISTORY_FILE = Path.home() / ".cowork" / "input_history"
_HISTORY_FILE.parent.mkdir(exist_ok=True)

_prompt_session: Optional[PromptSession] = None


def _get_prompt_session() -> PromptSession:
    """Return (or lazily create) the shared PromptSession with persistent history."""
    global _prompt_session
    if _prompt_session is None:
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.filters import has_completions, has_selection
        import re

        kb = KeyBindings()

        @kb.add('tab')
        def _(event):
            """Pressing Tab accepts the current completion."""
            b = event.app.current_buffer
            if b.complete_state:
                b.complete_state.current_completion
                b.apply_completion(b.complete_state.current_completion)
            else:
                # If no completions are visible, try to trigger them
                b.start_completion(select_first=True)

        @kb.add('right')
        def _(event):
            """Pressing Right arrow accepts one word of auto-suggestion or completion."""
            b = event.app.current_buffer
            
            # 1. Check if there's a completion menu open
            if b.complete_state and b.complete_state.current_completion:
                comp = b.complete_state.current_completion.text
                typed = b.text[b.complete_state.original_document.cursor_position:]
                remaining = comp[len(typed):]
                if remaining:
                    # extract next word
                    match = re.search(r'^\W*\w+', remaining)
                    chunk = match.group(0) if match else remaining
                    b.insert_text(chunk)
                return

            # 2. Check auto-suggest
            suggestion = b.suggestion
            if suggestion and suggestion.text:
                # Get the next "word" from the suggestion
                match = re.search(r'^\W*\w+', suggestion.text)
                chunk = match.group(0) if match else suggestion.text
                b.insert_text(chunk)
            else:
                # Default right arrow behavior (move cursor right)
                b.cursor_right()

        @kb.add('left')
        def _(event):
            """Pressing Left arrow goes back one word if cursor is at the end, else normal left."""
            b = event.app.current_buffer
            if b.cursor_position == len(b.text):
                # We are at the end, delete last word
                match = re.search(r'\w+\W*$', b.text)
                if match:
                    chunk = match.group(0)
                    b.delete_before_cursor(len(chunk))
                else:
                    b.cursor_left()
            else:
                b.cursor_left()


        _prompt_session = PromptSession(
            history=FileHistory(str(_HISTORY_FILE)),
            completer=_get_super_completer(),
            auto_suggest=AutoSuggestFromHistory(),
            style=PT_STYLE,
            complete_while_typing=True,
            enable_history_search=True,    # Ctrl+R incremental search
            mouse_support=False,
            wrap_lines=True,
            key_bindings=kb,
        )
    return _prompt_session


# ─── Input Prompt ─────────────────────────────────────────────────────────────

async def get_user_input(session_title: str = "New Session") -> str:
    """
    Get user input using prompt_toolkit for:
    - '/' autocomplete with command descriptions
    - Up/Down arrow history navigation
    - '#' hashtag pill suggestions
    - Ghost text auto-suggest from history
    """
    console.print()  # blank line before prompt

    # Build the prompt tokens (displayed left of cursor)
    title_short = session_title[:32]
    prompt_tokens = [
        ("class:prompt",        "❯ "),
        ("class:session-title", f"{title_short}  "),
    ]

    try:
        session = _get_prompt_session()
        # Use prompt_async to play nice with the existing asyncio loop
        user_input = await session.prompt_async(
            prompt_tokens,
            style=PT_STYLE,
        )
        user_text = user_input.strip()
        # Extract typed text for compound word completion
        if user_text:
            _get_super_completer().add_session_text(user_text)
        
        # Save to FTS history DB
        if _history_db and user_text and getattr(user_text, 'startswith', None) and not user_text.startswith("/"):
            _history_db.add_interaction(user_text, os.getcwd())
        return user_text
    except (KeyboardInterrupt, EOFError):
        return "/exit"
    except Exception:
        # Final fallback - shouldn't really happen with prompt_async
        return "/exit"
