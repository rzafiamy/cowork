"""
💻 Terminal UI Layer
Beautiful Rich-based interface for the Cowork CLI.
Handles all rendering: panels, spinners, live streaming, traces, dashboards.
"""

import asyncio
import time
from contextlib import contextmanager
from datetime import datetime
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

class StreamingRenderer:
    """
    Renders streaming LLM output token-by-token with a live panel.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._live: Optional[Live] = None
        self._start_time = time.time()

    def start(self) -> None:
        self._buffer = ""
        self._start_time = time.time()
        self._live = Live(
            self._render(),
            console=console,
            refresh_per_second=15,
            vertical_overflow="visible",
        )
        self._live.__enter__()

    def on_token(self, token: str) -> None:
        self._buffer += token
        if self._live:
            self._live.update(self._render())

    def _render(self) -> Panel:
        elapsed = time.time() - self._start_time
        content = self._buffer or " "
        try:
            md = Markdown(content)
        except Exception:
            md = Text(content)
        return Panel(
            md,
            title=f"[secondary]🤖 Cowork[/secondary]  [dim_text]{elapsed:.1f}s[/dim_text]",
            border_style="secondary",
            padding=(1, 2),
        )

    def stop(self) -> str:
        if self._live:
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
            refresh_per_second=10,
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

    try:
        body = Markdown(content)
    except Exception:
        body = Text(content)

    console.print()
    console.print(Panel(
        Group(body, Text(""), Text.from_markup(stats)),
        title="[secondary]🤖 Cowork[/secondary]",
        border_style="secondary",
        padding=(1, 2),
    ))
    console.print()


def render_user_message(content: str) -> None:
    """Render the user's message."""
    console.print(Panel(
        Text(content, style="text"),
        title="[highlight]👤 You[/highlight]",
        border_style="highlight",
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
    table.add_column("Messages", justify="center", style="highlight")
    table.add_column("Last Active", style="dim_text")
    table.add_column("Session ID", style="muted", width=10)

    for i, s in enumerate(sessions[:15], 1):
        updated = s.get("updated_at", "")[:16].replace("T", " ")
        table.add_row(
            str(i),
            s.get("title", "Untitled")[:40],
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

    sensitive_keys = {"api_key"}
    for key, value in sorted(config_data.items()):
        if key in sensitive_keys:
            display_val = "●●●●●●●●" if value else "[error]Not set[/error]"
        else:
            display_val = str(value)
        table.add_row(key, display_val)

    console.print(table)


# ─── Memory Display ───────────────────────────────────────────────────────────

def render_memory_status(triplet_count: int, summary: str) -> None:
    """Render Memoria status."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="muted", justify="right", width=16)
    grid.add_column()
    grid.add_row("Knowledge Facts", f"[memory]{triplet_count}[/memory] triplets in graph")
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


# ─── Error Display ────────────────────────────────────────────────────────────

def render_error(message: str, hint: str = "") -> None:
    content = f"[error]{message}[/error]"
    if hint:
        content += f"\n\n[muted]💡 Hint: {hint}[/muted]"
    console.print(Panel(content, title="[error]❌ Error[/error]", border_style="error", padding=(0, 2)))


def render_success(message: str) -> None:
    console.print(Panel(f"[success]{message}[/success]", border_style="success", padding=(0, 2)))


def render_warning(message: str) -> None:
    console.print(Panel(f"[warning]{message}[/warning]", border_style="warning", padding=(0, 2)))


# ─── Help Display ─────────────────────────────────────────────────────────────

def render_help() -> None:
    """Render the help panel with all commands."""
    commands = [
        ("/help", "Show this help message"),
        ("/new", "Start a new session"),
        ("/sessions", "List all sessions"),
        ("/load <id>", "Load a session by ID or number"),
        ("/memory", "Show Memoria status"),
        ("/memory clear", "Clear all memory for current user"),
        ("/jobs", "Show Sentinel job dashboard"),
        ("/config", "Show current configuration"),
        ("/config set <key> <value>", "Update a configuration value"),
        ("/scratchpad", "List scratchpad contents"),
        ("/trace", "Show last job trace"),
        ("/clear", "Clear the terminal"),
        ("/exit or /quit", "Exit Cowork"),
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
    pills.add_row("[dim_text]Hashtags like #research or #task route your intent[/dim_text]")

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


# ─── Input Prompt ─────────────────────────────────────────────────────────────

def get_user_input(session_title: str = "New Session") -> str:
    """Get user input with a styled prompt."""
    console.print()
    try:
        user_input = Prompt.ask(
            f"[primary]❯[/primary] [dim_text]{session_title[:30]}[/dim_text]",
            console=console,
        )
        return user_input.strip()
    except (KeyboardInterrupt, EOFError):
        return "/exit"
