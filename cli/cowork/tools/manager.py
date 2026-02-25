"""
🛠️ Tool Manager & Execution Gateway
This file acts as the primary interface for the tool system.
"""

import re
from typing import Any, Callable, Optional, Dict, List

from ..config import Scratchpad
from ..theme import GATEWAY_ERROR_PREFIX, TOOL_ERROR_PREFIX, OP_DEFAULTS
from .external.implementations import (
    get_available_external_tools,
    EXTERNAL_TOOLS,
)
from .registry import registry

# Populate schemas and maps from the registry
ALL_TOOLS: List[Dict[str, Any]] = registry.get_schemas()

CATEGORY_TOOL_MAP: Dict[str, List[str]] = {}
for _tool in ALL_TOOLS:
    _cat = _tool["category"]
    CATEGORY_TOOL_MAP.setdefault(_cat, []).append(_tool["function"]["name"])

TOOL_BY_NAME: Dict[str, Dict[str, Any]] = {t["function"]["name"]: t for t in ALL_TOOLS}

EXTERNAL_CATEGORIES = {
    "YOUTUBE_TOOLS", "SEARCH_TOOLS", "WEB_TOOLS",
    "NEWS_TOOLS", "WEATHER_TOOLS",
    "MEDIA_TOOLS", "KNOWLEDGE_TOOLS",
    "COMMUNICATION_TOOLS", "GOOGLE_TOOLS",
    "SOCIAL_TOOLS", "NEXTCLOUD_TOOLS", "GIT_TOOLS",
    "SUPABASE_TOOLS",
}

SPECIAL_CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    "CONVERSATIONAL": "Simple chat, explanation, and opinion turns that do not need tools.",
    "CONVERSATIONAL_ONLY": "Direct-answer mode with no tool schema construction.",
    "ALL_TOOLS": "Ambiguous tasks where broad tool availability is required.",
}

def get_tools_for_categories(categories: List[str]) -> List[Dict[str, Any]]:
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


def get_available_tools_for_categories(categories: List[str]) -> List[Dict[str, Any]]:
    """
    Like get_tools_for_categories but for external categories only returns
    tools whose API keys are actually configured.
    """
    external_names = {t["function"]["name"] for t in EXTERNAL_TOOLS}
    available_external_names = {t["function"]["name"] for t in get_available_external_tools()}
    all_for_cats = get_tools_for_categories(categories)
    result = []
    for tool in all_for_cats:
        name = tool["function"]["name"]
        cat = tool["category"]
        if cat in EXTERNAL_CATEGORIES and name in external_names and name not in available_external_names:
            continue
        result.append(tool)
    return result


def get_all_available_tools() -> List[Dict[str, Any]]:
    """Return all tools that are currently active (built-in + configured external)."""
    external_names = {t["function"]["name"] for t in EXTERNAL_TOOLS}
    available_external_names = {t["function"]["name"] for t in get_available_external_tools()}
    result = []
    for tool in ALL_TOOLS:
        name = tool["function"]["name"]
        cat = tool["category"]
        if cat in EXTERNAL_CATEGORIES and name in external_names:
            if name in available_external_names:
                result.append(tool)
        else:
            result.append(tool)
    return result


def get_category_descriptions(available_only: bool = True) -> Dict[str, str]:
    """
    Build category descriptions dynamically from the tool registry.
    This avoids hardcoding stale category prompt text.
    """
    tools = get_all_available_tools() if available_only else ALL_TOOLS
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for tool in tools:
        cat = str(tool.get("category", "")).strip()
        if not cat:
            continue
        by_cat.setdefault(cat, []).append(tool)

    out: Dict[str, str] = {}
    for cat, items in by_cat.items():
        names = [str(t.get("function", {}).get("name", "")) for t in items]
        names = [n for n in names if n]
        preview = ", ".join(names[:4]) + ("..." if len(names) > 4 else "")
        out[cat] = f"{len(items)} tool(s): {preview}" if preview else f"{len(items)} tool(s)"

    out.update(SPECIAL_CATEGORY_DESCRIPTIONS)
    return out


class ExecutionGateway:
    """
    Safety middleware between LLM tool calls and actual execution.
    Validates schemas, resolves ref:key pointers, enforces safety clamps.
    """
    MAX_ID_LEN    = 150
    MAX_TITLE_LEN = 500
    _EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
    _SLACK_CHANNEL_RE = re.compile(r"^(#[a-z0-9._\-]+|[CGD][A-Z0-9]{8,})$", re.IGNORECASE)
    _TELEGRAM_CHAT_RE = re.compile(r"^(@[A-Za-z0-9_]{5,}|-?[0-9]{5,})$")
    _PLACEHOLDERS = ("example.com", "example.org", "your-email", "foo@bar", "john@doe", "recipient@email.com")

    def __init__(self, scratchpad: Scratchpad) -> None:
        self.scratchpad = scratchpad

    def _looks_placeholder(self, value: str) -> bool:
        v = str(value or "").strip().lower()
        return any(p in v for p in self._PLACEHOLDERS)

    def _validate_communication_destination(self, tool_name: str, args: dict) -> tuple[bool, str]:
        if tool_name in ("smtp_send_email", "gmail_send_email"):
            recipient = str(args.get("recipient", "")).strip()
            if not recipient:
                return False, f"{GATEWAY_ERROR_PREFIX} Missing recipient. Ask user to provide the exact address."
            if self._looks_placeholder(recipient) or not self._EMAIL_RE.match(recipient):
                return False, (
                    f"{GATEWAY_ERROR_PREFIX} Invalid/placeholder recipient '{recipient}'. "
                    "Ask user to confirm the exact email address."
                )
        elif tool_name == "slack_send_message":
            channel = str(args.get("channel", "")).strip()
            if not channel:
                return False, f"{GATEWAY_ERROR_PREFIX} Missing Slack channel. Ask user to provide it."
            if self._looks_placeholder(channel) or not self._SLACK_CHANNEL_RE.match(channel):
                return False, (
                    f"{GATEWAY_ERROR_PREFIX} Invalid/placeholder Slack channel '{channel}'. "
                    "Use #channel or C/G/D channel ID and ask user to confirm."
                )
        elif tool_name == "telegram_send_message":
            chat_id = str(args.get("chat_id", "")).strip()
            if not chat_id:
                return False, f"{GATEWAY_ERROR_PREFIX} Missing Telegram chat_id. Ask user to provide it."
            if self._looks_placeholder(chat_id) or not self._TELEGRAM_CHAT_RE.match(chat_id):
                return False, (
                    f"{GATEWAY_ERROR_PREFIX} Invalid/placeholder Telegram chat_id '{chat_id}'. "
                    "Expected @username or numeric ID; ask user to confirm."
                )
        return True, ""

    def validate_and_resolve(self, tool_name: str, raw_args: dict) -> tuple[bool, dict, str]:
        if not isinstance(raw_args, dict):
            return False, {}, (
                f"{GATEWAY_ERROR_PREFIX} Tool arguments must be a JSON object."
            )

        schema = TOOL_BY_NAME.get(tool_name)
        if not schema:
            return False, {}, (
                f"{GATEWAY_ERROR_PREFIX} Tool '{tool_name}' not found. "
                f"[HINT]: Verify the tool name or check if the required category was requested during meta-routing."
            )

        params_schema = schema["function"]["parameters"]
        required = params_schema.get("required", [])
        properties = params_schema.get("properties", {})
        allowed_fields = set(properties.keys())
        unknown_fields = [k for k in raw_args.keys() if k not in allowed_fields]
        if unknown_fields:
            expected = ", ".join(sorted(allowed_fields)) if allowed_fields else "(no fields)"
            return False, {}, (
                f"{GATEWAY_ERROR_PREFIX} Unknown field(s): {', '.join(unknown_fields)}. "
                f"[HINT]: Expected fields: {expected}."
            )

        resolved = {}
        for field, spec in properties.items():
            val = raw_args.get(field)
            if val is None:
                if field in required:
                    return False, {}, (f"{GATEWAY_ERROR_PREFIX} Missing required field '{field}'.")
                continue

            if isinstance(val, str) and val.startswith("ref:"):
                resolved_val = self.scratchpad.get(val)
                if resolved_val is None:
                    return False, {}, (f"{GATEWAY_ERROR_PREFIX} Reference '{val}' not found.")
                val = resolved_val

            expected_type = spec.get("type")
            if expected_type == "string" and not isinstance(val, str):
                return False, {}, (f"{GATEWAY_ERROR_PREFIX} Field '{field}' must be a string.")
            if expected_type == "array" and not isinstance(val, list):
                return False, {}, (f"{GATEWAY_ERROR_PREFIX} Field '{field}' must be an array.")
            if expected_type == "integer" and not isinstance(val, int):
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    return False, {}, (f"{GATEWAY_ERROR_PREFIX} Field '{field}' must be an integer.")

            if field in ("id", "key") and isinstance(val, str) and len(val) > self.MAX_ID_LEN:
                val = val[:self.MAX_ID_LEN]
            if field in ("title", "name") and isinstance(val, str) and len(val) > self.MAX_TITLE_LEN:
                val = val[:self.MAX_TITLE_LEN]
            if isinstance(val, str) and field in required and not val.strip():
                return False, {}, (f"{GATEWAY_ERROR_PREFIX} Field '{field}' cannot be empty.")

            resolved[field] = val

        ok_dest, err_dest = self._validate_communication_destination(tool_name, resolved)
        if not ok_dest:
            return False, {}, err_dest

        return True, resolved, ""


class ToolExecutor:
    """
    Executes validated tool calls by dispatching to the modular tool system.
    """
    def __init__(
        self,
        scratchpad: Scratchpad,
        config: Any,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.scratchpad = scratchpad
        self.config = config
        self.status_cb = status_callback
        self._tool_call_count = 0
        self._tools = registry.create_instances(
            status_callback=status_callback,
            scratchpad=scratchpad,
            config=config
        )

    def _clamp_output(self, tool_name: str, result: str) -> str:
        if re.search(r"\[Full result saved as ref:[^\]]+\]", result or ""):
            return result

        limit = self.config.get("tool_output_limit_tokens", OP_DEFAULTS["tool_output_limit_tokens"])
        estimated_tokens = len(result) // 4
        if estimated_tokens > limit:
            key = f"tool_output_{tool_name}_{self._tool_call_count}"
            self.scratchpad.save(key, result, description=f"Full output of {tool_name}")
            preview = self.scratchpad.sandwich_preview(result)
            return f"{preview}\n\n[Full result saved as ref:{key}]"
        return result

    def execute(self, tool_name: str, args: dict, clamp_output: bool = True) -> str:
        self._tool_call_count += 1
        tool = self._tools.get(tool_name)
        if not tool:
            return f"{TOOL_ERROR_PREFIX} Tool '{tool_name}' has no executor."
        
        try:
            result = tool.execute(**args)
            out = str(result)
            return self._clamp_output(tool_name, out) if clamp_output else out
        except Exception as e:
            return f"{TOOL_ERROR_PREFIX} Execution failed: {e}."
