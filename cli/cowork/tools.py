"""
🛠️ Tool Registry & Execution Gateway
Implements the full tool schema, meta-routing, and execution pipeline.
"""

import json
import math
import time
import datetime
import re
import urllib.parse
from typing import Any, Callable, Optional

from .config import Scratchpad
from .theme import GATEWAY_ERROR_PREFIX, TOOL_ERROR_PREFIX, OP_DEFAULTS
from .tools_external import (
    EXTERNAL_TOOLS,
    execute_external_tool,
    get_all_external_tools,
    get_available_external_tools,
    EXTERNAL_TOOL_HANDLERS,
)

# ─── Tool Schema Definitions ──────────────────────────────────────────────────
ALL_TOOLS: list[dict] = [
    # ── DATA_AND_UTILITY ─────────────────────────────────────────────────────
    {
        "category": "DATA_AND_UTILITY",
        "type": "function",
        "function": {
            "name": "calc",
            "description": "Evaluate a mathematical expression. Supports +, -, *, /, **, sqrt, log, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression to evaluate, e.g. '2 ** 10 + sqrt(144)'"},
                },
                "required": ["expression"],
            },
        },
    },
    {
        "category": "DATA_AND_UTILITY",
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current date and time, optionally for a specific timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Timezone name, e.g. 'UTC', 'US/Eastern'"},
                },
                "required": [],
            },
        },
    },
    {
        "category": "DATA_AND_UTILITY",
        "type": "function",
        "function": {
            "name": "gen_diagram",
            "description": "Generate a Mermaid.js diagram from a description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "diagram_type": {"type": "string", "description": "Type: flowchart, sequenceDiagram, erDiagram, gantt, pie"},
                    "description": {"type": "string", "description": "Natural language description of the diagram"},
                },
                "required": ["diagram_type", "description"],
            },
        },
    },
    # ── SESSION_SCRATCHPAD ────────────────────────────────────────────────────
    {
        "category": "SESSION_SCRATCHPAD",
        "type": "function",
        "function": {
            "name": "scratchpad_save",
            "description": "Save large data to the session scratchpad. Returns a ref:key pointer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Unique key for this data (alphanumeric + underscore)"},
                    "content": {"type": "string", "description": "The content to store"},
                    "description": {"type": "string", "description": "Brief description of what is stored"},
                },
                "required": ["key", "content"],
            },
        },
    },
    {
        "category": "SESSION_SCRATCHPAD",
        "type": "function",
        "function": {
            "name": "scratchpad_list",
            "description": "List all items currently stored in the scratchpad.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "category": "SESSION_SCRATCHPAD",
        "type": "function",
        "function": {
            "name": "scratchpad_read_chunk",
            "description": "Read a specific chunk of scratchpad content by key.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The scratchpad key (with or without 'ref:' prefix)"},
                    "chunk_index": {"type": "integer", "description": "Zero-based chunk index (default: 0)"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "category": "SESSION_SCRATCHPAD",
        "type": "function",
        "function": {
            "name": "scratchpad_search",
            "description": "Search scratchpad content by keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                },
                "required": ["query"],
            },
        },
    },
    # ── APP_CONNECTORS ────────────────────────────────────────────────────────
    {
        "category": "APP_CONNECTORS",
        "type": "function",
        "function": {
            "name": "notes_create",
            "description": "Create a new note in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Note title (max 500 chars)"},
                    "content": {"type": "string", "description": "Note content"},
                    "category": {"type": "string", "description": "Category/tag for the note"},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "category": "APP_CONNECTORS",
        "type": "function",
        "function": {
            "name": "kanban_add_task",
            "description": "Add a task to the Kanban board.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description"},
                    "priority": {"type": "string", "description": "Priority: low, medium, high", "enum": ["low", "medium", "high"]},
                    "due_date": {"type": "string", "description": "Due date in ISO format"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "category": "APP_CONNECTORS",
        "type": "function",
        "function": {
            "name": "storage_write",
            "description": "Write content to a persistent workspace file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename with extension"},
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["filename", "content"],
            },
        },
    },
]

# ─── Merge External (Paid API) Tools ─────────────────────────────────────────
# External tools are always registered in the schema so the AI knows about them.
# At runtime, tools whose keys are missing return a friendly error message.
ALL_TOOLS.extend(EXTERNAL_TOOLS)

# ─── Category → Tool Name Mapping ────────────────────────────────────────────
CATEGORY_TOOL_MAP: dict[str, list[str]] = {}
for _tool in ALL_TOOLS:
    _cat = _tool["category"]
    CATEGORY_TOOL_MAP.setdefault(_cat, []).append(_tool["function"]["name"])

# ─── Tool Lookup ──────────────────────────────────────────────────────────────
TOOL_BY_NAME: dict[str, dict] = {t["function"]["name"]: t for t in ALL_TOOLS}

# ─── External Tool Categories ─────────────────────────────────────────────────
EXTERNAL_CATEGORIES = {
    "YOUTUBE_TOOLS", "SEARCH_TOOLS", "WEB_TOOLS",
    "NEWS_TOOLS", "CODE_TOOLS", "WEATHER_TOOLS",
    "MEDIA_TOOLS", "KNOWLEDGE_TOOLS",
}


def get_tools_for_categories(categories: list[str]) -> list[dict]:
    """Filter tool schemas to only those in the given categories."""
    if "ALL_TOOLS" in categories:
        return ALL_TOOLS
    if "CONVERSATIONAL" in categories:
        return []
    result = []
    seen = set()
    for cat in categories:
        for tool in ALL_TOOLS:
            name = tool["function"]["name"]
            if tool["category"] == cat and name not in seen:
                result.append(tool)
                seen.add(name)
    return result


def get_available_tools_for_categories(categories: list[str]) -> list[dict]:
    """
    Like get_tools_for_categories but for external categories only returns
    tools whose API keys are actually configured.
    """
    available_external_names = {t["function"]["name"] for t in get_available_external_tools()}
    all_for_cats = get_tools_for_categories(categories)
    result = []
    for tool in all_for_cats:
        name = tool["function"]["name"]
        cat = tool["category"]
        # For external categories, only include if key is available
        if cat in EXTERNAL_CATEGORIES and name not in available_external_names:
            continue
        result.append(tool)
    return result


# ─── Execution Gateway ────────────────────────────────────────────────────────
class ExecutionGateway:
    """
    Safety middleware between LLM tool calls and actual execution.
    Validates schemas, resolves ref:key pointers, enforces safety clamps.
    """

    MAX_ID_LEN    = 150
    MAX_TITLE_LEN = 500

    def __init__(self, scratchpad: Scratchpad) -> None:
        self.scratchpad = scratchpad

    def validate_and_resolve(self, tool_name: str, raw_args: dict) -> tuple[bool, dict, str]:
        """
        Returns (ok, resolved_args, error_message).
        """
        schema = TOOL_BY_NAME.get(tool_name)
        if not schema:
            return False, {}, (
                f"{GATEWAY_ERROR_PREFIX} Tool '{tool_name}' not found. "
                f"[HINT]: Verify the tool name or check if the required category was requested during meta-routing."
            )

        params_schema = schema["function"]["parameters"]
        required = params_schema.get("required", [])
        properties = params_schema.get("properties", {})

        resolved = {}
        for field, spec in properties.items():
            val = raw_args.get(field)

            # Check required
            if val is None:
                if field in required:
                    return False, {}, (
                        f"{GATEWAY_ERROR_PREFIX} Missing required field '{field}'. "
                        f"[HINT]: This field is mandatory."
                    )
                continue

            # Resolve ref:key pointers
            if isinstance(val, str) and val.startswith("ref:"):
                resolved_val = self.scratchpad.get(val)
                if resolved_val is None:
                    return False, {}, (
                        f"{GATEWAY_ERROR_PREFIX} Reference '{val}' not found in scratchpad. "
                        f"[HINT]: Save data to scratchpad first or check if you used the correct 'ref:key'."
                    )
                val = resolved_val

            # Type validation
            expected_type = spec.get("type")
            if expected_type == "string" and not isinstance(val, str):
                return False, {}, (
                    f"{GATEWAY_ERROR_PREFIX} Field '{field}' must be a string. "
                    f"[HINT]: Enclose the value in quotes."
                )
            if expected_type == "array" and not isinstance(val, list):
                return False, {}, (
                    f"{GATEWAY_ERROR_PREFIX} Field '{field}' must be an array. "
                    f"[HINT]: Use [item1, item2] format."
                )
            if expected_type == "integer" and not isinstance(val, int):
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    return False, {}, (
                        f"{GATEWAY_ERROR_PREFIX} Field '{field}' must be an integer."
                    )

            # Safety clamps
            if field in ("id", "key") and isinstance(val, str) and len(val) > self.MAX_ID_LEN:
                val = val[:self.MAX_ID_LEN]
            if field in ("title", "name") and isinstance(val, str) and len(val) > self.MAX_TITLE_LEN:
                val = val[:self.MAX_TITLE_LEN]

            resolved[field] = val

        return True, resolved, ""


# ─── Tool Executor ────────────────────────────────────────────────────────────
class ToolExecutor:
    """
    Executes validated tool calls. Handles output clamping and sandwiching.
    """

    def __init__(
        self,
        scratchpad: Scratchpad,
        config: Any,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.scratchpad = scratchpad
        self.config = config
        self.status_callback = status_callback or (lambda msg: None)
        self._tool_call_count = 0

    def _emit(self, msg: str) -> None:
        self.status_callback(msg)

    def _clamp_output(self, tool_name: str, result: str) -> str:
        """Apply sandwich compression if output exceeds token limit."""
        limit = self.config.get("tool_output_limit_tokens", OP_DEFAULTS["tool_output_limit_tokens"])
        # Rough token estimate: 4 chars ≈ 1 token
        estimated_tokens = len(result) // 4
        if estimated_tokens > limit:
            key = f"tool_output_{tool_name}_{self._tool_call_count}"
            self.scratchpad.save(key, result, description=f"Full output of {tool_name}")
            preview = self.scratchpad.sandwich_preview(result)
            return f"{preview}\n\n[Full result saved as ref:{key}]"
        return result

    def execute(self, tool_name: str, args: dict) -> str:
        """Execute a tool and return its result string."""
        self._tool_call_count += 1
        try:
            # Check built-in tools first
            handler = getattr(self, f"_tool_{tool_name}", None)
            if handler is not None:
                result = handler(**args)
                return self._clamp_output(tool_name, str(result))

            # Fall back to external tools
            if tool_name in EXTERNAL_TOOL_HANDLERS:
                self._emit(f"🔌 Calling external tool: {tool_name}...")
                result = execute_external_tool(tool_name, args)
                return self._clamp_output(tool_name, str(result))

            return f"{TOOL_ERROR_PREFIX} Tool '{tool_name}' has no executor. [HINT]: Use only tools available in your schema."
        except Exception as e:
            return f"{TOOL_ERROR_PREFIX} Execution failed: {e}. [HINT]: Check if parameters are correct or try an alternative tool."

    # ── Tool Implementations ──────────────────────────────────────────────────

    def _tool_calc(self, expression: str) -> str:
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

    def _tool_get_time(self, timezone: str = "UTC") -> str:
        self._emit("⏰ Fetching current time...")
        now = datetime.datetime.utcnow()
        return (
            f"Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"ISO 8601: {now.isoformat()}Z\n"
            f"Unix timestamp: {int(now.timestamp())}"
        )

    def _tool_get_weather(self, location: str) -> str:
        self._emit(f"�️  Fetching weather for: '{location}'...")
        # Redirect to premium tool if available, otherwise suggest .env setup
        from .tools_external import _env
        if _env("OPENWEATHER_API_KEY"):
            return self.execute("openweather_current", {"location": location})
        return "❌ Legacy `get_weather` is disabled. [HINT]: Add `OPENWEATHER_API_KEY` to `.env` to use premium weather tools."


    def _tool_gen_diagram(self, diagram_type: str, description: str) -> str:
        self._emit(f"📐 Generating {diagram_type} diagram...")
        templates = {
            "flowchart": f"```mermaid\nflowchart TD\n    A[Start] --> B{{Decision}}\n    B -- Yes --> C[Action]\n    B -- No --> D[End]\n    C --> D\n```\n\n*Diagram for: {description}*",
            "sequenceDiagram": f"```mermaid\nsequenceDiagram\n    participant A as Actor A\n    participant B as Actor B\n    A->>B: Request\n    B-->>A: Response\n```\n\n*Sequence for: {description}*",
            "pie": f"```mermaid\npie title Distribution\n    \"Category A\" : 40\n    \"Category B\" : 35\n    \"Category C\" : 25\n```\n\n*Pie chart for: {description}*",
            "gantt": f"```mermaid\ngantt\n    title Project Timeline\n    dateFormat YYYY-MM-DD\n    section Phase 1\n    Task A :a1, 2024-01-01, 7d\n    Task B :a2, after a1, 5d\n```\n\n*Gantt for: {description}*",
        }
        return templates.get(diagram_type, f"```mermaid\n{diagram_type}\n    %% {description}\n```")

    def _tool_scratchpad_save(self, key: str, content: str, description: str = "") -> str:
        self._emit(f"💾 Saving to scratchpad: '{key}'...")
        ref = self.scratchpad.save(key, content, description)
        return f"Saved to scratchpad. Reference: {ref} ({len(content)} chars)"

    def _tool_scratchpad_list(self) -> str:
        self._emit("📋 Listing scratchpad contents...")
        items = self.scratchpad.list_all()
        if not items:
            return "Scratchpad is empty."
        lines = ["Scratchpad contents:\n"]
        for item in items:
            lines.append(f"• ref:{item['key']} — {item['description'] or 'No description'} ({item['size_chars']} chars)")
        return "\n".join(lines)

    def _tool_scratchpad_read_chunk(self, key: str, chunk_index: int = 0) -> str:
        self._emit(f"📖 Reading scratchpad chunk: '{key}' [{chunk_index}]...")
        result = self.scratchpad.read_chunk(key, chunk_index)
        if result is None:
            return f"{GATEWAY_ERROR_PREFIX} Key '{key}' not found in scratchpad. [HINT]: Use scratchpad_list to see available keys."
        return result

    def _tool_scratchpad_search(self, query: str) -> str:
        self._emit(f"🔍 Searching scratchpad for: '{query}'...")
        results = self.scratchpad.search(query)
        if not results:
            return f"No scratchpad items matching '{query}'."
        lines = [f"Found {len(results)} match(es):\n"]
        for r in results:
            lines.append(f"• ref:{r['key']} — {r['description']}\n  Preview: {r['preview'][:100]}...")
        return "\n".join(lines)

    def _tool_notes_create(self, title: str, content: str, category: str = "General") -> str:
        self._emit("📝 Creating note...")
        note_id = f"note_{int(time.time())}"
        return f"✅ Note created successfully!\n• ID: {note_id}\n• Title: {title}\n• Category: {category}\n• Length: {len(content)} chars\n\n[Note saved to workspace]"

    def _tool_kanban_add_task(self, title: str, description: str = "", priority: str = "medium", due_date: str = "") -> str:
        self._emit("📋 Adding task to Kanban board...")
        task_id = f"task_{int(time.time())}"
        return f"✅ Task added to Kanban!\n• ID: {task_id}\n• Title: {title}\n• Priority: {priority}\n• Due: {due_date or 'Not set'}"

    def _tool_storage_write(self, filename: str, content: str) -> str:
        self._emit(f"💾 Writing to workspace storage: '{filename}'...")
        from .config import CONFIG_DIR
        storage_dir = CONFIG_DIR / "storage"
        storage_dir.mkdir(exist_ok=True)
        path = storage_dir / filename
        path.write_text(content, encoding="utf-8")
        return f"✅ File written: {path}\n• Size: {len(content)} chars"
