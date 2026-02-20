"""
🛠️ Utility Tools
Basic mathematical and temporal functions.
"""

import math
import re
import unicodedata
from typing import Any, Dict, Optional
from ..base import BaseTool


def sanitize_for_audio(text: str) -> str:
    """
    Convert markdown-ish content into cleaner plain text for TTS.
    Mirrors the sanitization pipeline requested by the user.
    """
    sanitized = text or ""
    sanitized = re.sub(r"(\*\*|__)(.*?)\1", r"\2", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"(\*|_)(.*?)\1", r"\2", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"`{1,3}(.*?)`{1,3}", r"\1", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"~~(.*?)~~", r"\1", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"(?m)^#{1,6}\s*(.*)$", r"\1", sanitized)
    sanitized = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"!\[.*?\]\(.*?\)", "", sanitized, flags=re.DOTALL)
    sanitized = re.sub(r"(?m)^\s*>\s*(.*)$", r"\1", sanitized)
    sanitized = re.sub(r"(?m)^\s*[-*+]\s*(.*)$", r"\1", sanitized)
    sanitized = re.sub(r"\n{2,}", ". ", sanitized)
    sanitized = sanitized.replace("\n", " ")

    allowed_punct = set(".,!?;:'\"(){}[]-")
    filtered_chars = []
    for ch in sanitized:
        cat = unicodedata.category(ch)
        if ch.isspace() or ch in allowed_punct or cat.startswith("L") or cat.startswith("N"):
            filtered_chars.append(ch)
    return "".join(filtered_chars).strip()


class CalcTool(BaseTool):
    @property
    def name(self) -> str:
        return "calc"

    @property
    def description(self) -> str:
        return "Evaluate a mathematical expression. Supports +, -, *, /, **, sqrt, log, etc."

    @property
    def category(self) -> str:
        return "DATA_AND_UTILITY"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression to evaluate, e.g. '2 ** 10 + sqrt(144)'"},
            },
            "required": ["expression"],
        }

    def execute(self, expression: str) -> str:
        self._emit("🔢 Evaluating mathematical expression...")
        safe_globals = {
            "__builtins__": {},
            "sqrt": math.sqrt, "log": math.log, "log2": math.log2, "log10": math.log10,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "pi": math.pi, "e": math.e, "abs": abs, "round": round,
            "pow": pow, "min": min, "max": max,
        }
        try:
            result = eval(expression, safe_globals)  # noqa: S307
            return f"Result: {result}"
        except Exception as ex:
            return f"Calculation error: {ex}"

class GetTimeTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_time"

    @property
    def description(self) -> str:
        return "Get the current date and time, optionally for a specific timezone."

    @property
    def category(self) -> str:
        return "DATA_AND_UTILITY"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "description": "Timezone name, e.g. 'UTC', 'US/Eastern'"},
            },
            "required": [],
        }

    def execute(self, timezone: Optional[str] = None) -> str:
        self._emit("⏰ Fetching current time...")
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            ZoneInfo = None

        now = datetime.now().astimezone()
        
        if timezone and timezone.upper() != "LOCAL":
            if timezone.upper() == "UTC":
                from datetime import timezone as dt_timezone
                now = datetime.now(dt_timezone.utc)
            elif ZoneInfo:
                try:
                    now = datetime.now(ZoneInfo(timezone))
                except Exception:
                    return f"❌ Error: Invalid or unknown timezone '{timezone}'."
            else:
                return f"❌ Error: Timezone support requires Python 3.9+ or zoneinfo backport."

        return (
            f"Current time ({timezone or 'Local'}): {now.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
            f"ISO 8601: {now.isoformat()}\n"
            f"Unix timestamp: {int(now.timestamp())}"
        )

class GenDiagramTool(BaseTool):
    @property
    def name(self) -> str:
        return "gen_diagram"

    @property
    def description(self) -> str:
        return "Generate a Mermaid.js diagram from a description."

    @property
    def category(self) -> str:
        return "DATA_AND_UTILITY"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "diagram_type": {"type": "string", "description": "Type: flowchart, sequenceDiagram, erDiagram, gantt, pie"},
                "description": {"type": "string", "description": "Natural language description of the diagram"},
            },
            "required": ["diagram_type", "description"],
        }

    def execute(self, diagram_type: str, description: str) -> str:
        self._emit(f"📐 Generating {diagram_type} diagram...")
        templates = {
            "flowchart": f"```mermaid\nflowchart TD\n    A[Start] --> B{{Decision}}\n    B -- Yes --> C[Action]\n    B -- No --> D[End]\n    C --> D\n```\n\n*Diagram for: {description}*",
            "sequenceDiagram": f"```mermaid\nsequenceDiagram\n    participant A as Actor A\n    participant B as Actor B\n    A->>B: Request\n    B-->>A: Response\n```\n\n*Sequence for: {description}*",
            "pie": f"```mermaid\npie title Distribution\n    \"Category A\" : 40\n    \"Category B\" : 35\n    \"Category C\" : 25\n```\n\n*Pie chart for: {description}*",
            "gantt": f"```mermaid\ngantt\n    title Project Timeline\n    dateFormat YYYY-MM-DD\n    section Phase 1\n    Task A :a1, 2024-01-01, 7d\n    Task B :a2, after a1, 5d\n```\n\n*Gantt for: {description}*",
        }
        return templates.get(diagram_type, f"```mermaid\n{diagram_type}\n    %% {description}\n```")
