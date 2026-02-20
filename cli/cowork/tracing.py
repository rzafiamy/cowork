"""
🧾 Workflow Trace Logging
Persists detailed per-turn agent traces for debugging and maintenance.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class WorkflowTraceLogger:
    """Writes structured JSONL workflow events for a single agent turn."""

    def __init__(
        self,
        *,
        enabled: bool,
        session_id: str,
        job_id: str,
        workspace_path: Optional[Path] = None,
    ) -> None:
        self.enabled = enabled
        self.session_id = session_id
        self.job_id = job_id
        self.start_time = time.time()
        self.file_path: Optional[Path] = None

        if not self.enabled:
            return

        if workspace_path:
            root = workspace_path / "traces"
        else:
            root = Path.home() / ".cowork" / "traces" / session_id
        root.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.file_path = root / f"{stamp}_{job_id}.jsonl"
        self.log(
            "trace_started",
            {
                "session_id": session_id,
                "job_id": job_id,
                "trace_file": str(self.file_path),
            },
        )

    def _fallback_path(self) -> Path:
        root = Path.home() / ".cowork" / "traces" / self.session_id
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return root / f"{stamp}_{self.job_id}.jsonl"

    def _ensure_writable_path(self) -> Optional[Path]:
        if not self.file_path:
            return None
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            return self.file_path
        except OSError:
            try:
                self.file_path = self._fallback_path()
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                return self.file_path
            except OSError:
                return None

    def _sanitize(self, value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            if isinstance(value, dict):
                return {str(k): self._sanitize(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [self._sanitize(v) for v in value]
            return str(value)

    def log(self, event: str, data: Optional[dict[str, Any]] = None) -> None:
        if not self.enabled or not self.file_path:
            return
        path = self._ensure_writable_path()
        if not path:
            return
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": int((time.time() - self.start_time) * 1000),
            "event": event,
            "data": self._sanitize(data or {}),
        }
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            try:
                self.file_path = self._fallback_path()
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                return

    def close(self, summary: Optional[dict[str, Any]] = None) -> None:
        try:
            self.log("trace_finished", summary or {})
        except Exception:
            return


def load_trace_events(path: Path) -> list[dict[str, Any]]:
    """Load JSONL trace events from disk."""
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                events.append({
                    "timestamp": "",
                    "elapsed_ms": 0,
                    "event": "malformed_line",
                    "data": {"raw": line},
                })
    return events


def find_latest_trace_file(session_id: Optional[str] = None) -> Optional[Path]:
    """Find latest trace file from session scope or global traces."""
    roots: list[Path] = []
    if session_id:
        roots.append(Path.home() / ".cowork" / "traces" / session_id)
    roots.append(Path.home() / ".cowork" / "traces")
    roots.append(Path.home() / ".cowork" / "workspace")

    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.name == "workspace":
            candidates.extend(root.glob("*/traces/*.jsonl"))
        else:
            candidates.extend(root.rglob("*.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def format_trace_text(
    events: list[dict[str, Any]],
    *,
    full: bool = False,
    max_value_chars: int = 4000,
) -> str:
    """Format trace events into a readable text timeline."""
    lines: list[str] = []
    lines.append("=== TRACE TIMELINE ===")
    lines.append(f"events: {len(events)}")
    lines.append("")

    for idx, e in enumerate(events, start=1):
        event = e.get("event", "unknown")
        elapsed = e.get("elapsed_ms", 0)
        ts = e.get("timestamp", "")
        data = e.get("data", {})
        lines.append(f"[{idx}] +{elapsed}ms  {event}")
        lines.append(f"    time: {ts}")
        if full:
            payload = json.dumps(data, indent=2, ensure_ascii=False)
            if len(payload) > max_value_chars:
                payload = payload[:max_value_chars] + "\n... [truncated]"
            indented = "\n".join(f"    {ln}" for ln in payload.splitlines())
            lines.append("    data:")
            lines.append(indented)
        else:
            keys = list(data.keys())[:8] if isinstance(data, dict) else []
            lines.append(f"    keys: {', '.join(keys) if keys else '(none)'}")
        lines.append("")
    return "\n".join(lines)


def _event_theme(event: str) -> tuple[str, str]:
    """Return (icon, style) for an event name."""
    if event.startswith("trace_"):
        return "🧾", "primary"
    if event.startswith("turn_"):
        return "🧠", "secondary"
    if event.startswith("router_"):
        return "🧭", "router"
    if event.startswith("memory_"):
        return "🧠", "memory"
    if event.startswith("tool_"):
        return "🛠️", "tool"
    if event.startswith("llm_"):
        return "🤖", "highlight"
    if event.startswith("context_compression"):
        return "🗜️", "compress"
    if "error" in event:
        return "❌", "error"
    if event == "final_answer":
        return "✅", "success"
    return "•", "muted"


def _shorten(value: Any, max_chars: int) -> str:
    if isinstance(value, (dict, list)):
        txt = json.dumps(value, ensure_ascii=False)
    else:
        txt = str(value)
    if len(txt) <= max_chars:
        return txt
    return txt[:max_chars] + "…"


def render_trace_timeline(
    events: list[dict[str, Any]],
    *,
    full: bool = False,
    max_value_chars: int = 4000,
    trace_file: Optional[str] = None,
):
    """
    Build a rich, colorized trace timeline renderable.
    Keeps output readable for long traces while preserving inspectability.
    """
    from rich import box
    from rich.console import Group
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text

    total_events = len(events)
    total_ms = max((int(e.get("elapsed_ms", 0)) for e in events), default=0)

    by_family: dict[str, int] = {
        "turn": 0,
        "router": 0,
        "llm": 0,
        "tool": 0,
        "memory": 0,
        "trace": 0,
        "other": 0,
    }
    for e in events:
        name = str(e.get("event", "unknown"))
        if name.startswith("turn_"):
            by_family["turn"] += 1
        elif name.startswith("router_"):
            by_family["router"] += 1
        elif name.startswith("llm_"):
            by_family["llm"] += 1
        elif name.startswith("tool_"):
            by_family["tool"] += 1
        elif name.startswith("memory_"):
            by_family["memory"] += 1
        elif name.startswith("trace_"):
            by_family["trace"] += 1
        else:
            by_family["other"] += 1

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="muted", justify="right")
    summary.add_column()
    summary.add_row("Events", f"[highlight]{total_events}[/highlight]")
    summary.add_row("Elapsed", f"[highlight]{total_ms} ms[/highlight]")
    if trace_file:
        summary.add_row("Trace File", f"[dim_text]{trace_file}[/dim_text]")
    summary.add_row(
        "Families",
        (
            f"[secondary]turn {by_family['turn']}[/secondary] · "
            f"[router]router {by_family['router']}[/router] · "
            f"[highlight]llm {by_family['llm']}[/highlight] · "
            f"[tool]tool {by_family['tool']}[/tool] · "
            f"[memory]memory {by_family['memory']}[/memory]"
        ),
    )

    header = Panel(summary, title="🧾 Trace Summary", border_style="primary", padding=(0, 1))

    event_panels = []
    for idx, e in enumerate(events, start=1):
        event = str(e.get("event", "unknown"))
        elapsed = int(e.get("elapsed_ms", 0))
        ts = str(e.get("timestamp", ""))
        data = e.get("data", {})
        icon, style = _event_theme(event)

        meta = Table.grid(padding=(0, 2))
        meta.add_column(style="muted")
        meta.add_column()
        meta.add_row("Time", ts or "(unknown)")
        meta.add_row("Elapsed", f"+{elapsed}ms")

        renderables = [meta]
        if full:
            if isinstance(data, dict) and data:
                kv = Table(box=box.MINIMAL, show_header=True, header_style="bold", expand=True)
                kv.add_column("Key", style="accent", no_wrap=True, width=28)
                kv.add_column("Value", style="text")
                for k, v in data.items():
                    if isinstance(v, (dict, list)):
                        shown = _shorten(v, min(max_value_chars, 2000))
                    else:
                        shown = _shorten(v, min(max_value_chars, 1200))
                    kv.add_row(str(k), shown)
                renderables.append(kv)

                raw_json = json.dumps(data, indent=2, ensure_ascii=False)
                if len(raw_json) > max_value_chars:
                    raw_json = raw_json[:max_value_chars] + "\n... [truncated]"
                renderables.append(
                    Panel(
                        Syntax(raw_json, "json", theme="monokai", background_color="default"),
                        title="Raw Payload",
                        border_style="dim",
                        padding=(0, 1),
                    )
                )
            else:
                renderables.append(Text("No payload data.", style="dim"))
        else:
            keys = list(data.keys())[:10] if isinstance(data, dict) else []
            key_text = ", ".join(keys) if keys else "(none)"
            renderables.append(Text(f"Keys: {key_text}", style="dim"))

        event_panels.append(
            Panel(
                Group(*renderables),
                title=f"{icon} [{style}]#{idx} {event}[/{style}]",
                border_style=style,
                padding=(0, 1),
                expand=True,
            )
        )

    return Group(header, *event_panels)
