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
    "SOCIAL_TOOLS",
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
    available_external_names = {t["function"]["name"] for t in get_available_external_tools()}
    all_for_cats = get_tools_for_categories(categories)
    result = []
    for tool in all_for_cats:
        name = tool["function"]["name"]
        cat = tool["category"]
        if cat in EXTERNAL_CATEGORIES and name not in available_external_names:
            continue
        result.append(tool)
    return result


def get_all_available_tools() -> List[Dict[str, Any]]:
    """Return all tools that are currently active (built-in + configured external)."""
    available_external_names = {t["function"]["name"] for t in get_available_external_tools()}
    result = []
    for tool in ALL_TOOLS:
        name = tool["function"]["name"]
        cat = tool["category"]
        if cat in EXTERNAL_CATEGORIES:
            if name in available_external_names:
                result.append(tool)
        else:
            result.append(tool)
    return result


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

            resolved[field] = val

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
