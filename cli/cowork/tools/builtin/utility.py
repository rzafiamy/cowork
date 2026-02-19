"""
🛠️ Utility Tools
Basic mathematical and temporal functions.
"""

import math
from typing import Any, Dict, Optional
from ..base import BaseTool

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
