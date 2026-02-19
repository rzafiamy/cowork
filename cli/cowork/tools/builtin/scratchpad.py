"""
💾 Scratchpad Tools
Tools for managing session-specific scratchpad data.
"""

from typing import Any, Dict, Optional
from ..base import BaseTool

class ScratchpadSaveTool(BaseTool):
    @property
    def name(self) -> str:
        return "scratchpad_save"

    @property
    def description(self) -> str:
        return "Save large data to the session scratchpad. Returns a ref:key pointer."

    @property
    def category(self) -> str:
        return "SESSION_SCRATCHPAD"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Unique key for this data (alphanumeric + underscore)"},
                "content": {"type": "string", "description": "The content to store"},
                "description": {"type": "string", "description": "Brief description of what is stored"},
            },
            "required": ["key", "content"],
        }

    def execute(self, key: str, content: str, description: str = "") -> str:
        self._emit(f"💾 Saving to scratchpad: '{key}'...")
        if not self.scratchpad:
            return "❌ Error: Scratchpad not initialized."
        ref = self.scratchpad.save(key, content, description)
        return f"Saved to scratchpad. Reference: {ref} ({len(content)} chars)"

class ScratchpadListTool(BaseTool):
    @property
    def name(self) -> str:
        return "scratchpad_list"

    @property
    def description(self) -> str:
        return "List all items currently stored in the scratchpad."

    @property
    def category(self) -> str:
        return "SESSION_SCRATCHPAD"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def execute(self) -> str:
        self._emit("📋 Listing scratchpad contents...")
        if not self.scratchpad:
            return "❌ Error: Scratchpad not initialized."
        items = self.scratchpad.list_all()
        if not items:
            return "Scratchpad is empty."
        lines = ["Scratchpad contents:\n"]
        for item in items:
            lines.append(f"• ref:{item['key']} — {item['description'] or 'No description'} ({item['size_chars']} chars)")
        return "\n".join(lines)

class ScratchpadReadChunkTool(BaseTool):
    @property
    def name(self) -> str:
        return "scratchpad_read_chunk"

    @property
    def description(self) -> str:
        return "Read a specific chunk of scratchpad content by key."

    @property
    def category(self) -> str:
        return "SESSION_SCRATCHPAD"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The scratchpad key (with or without 'ref:' prefix)"},
                "chunk_index": {"type": "integer", "description": "Zero-based chunk index (default: 0)"},
            },
            "required": ["key"],
        }

    def execute(self, key: str, chunk_index: int = 0) -> str:
        self._emit(f"📖 Reading scratchpad chunk: '{key}' [{chunk_index}]...")
        if not self.scratchpad:
            return "❌ Error: Scratchpad not initialized."
        result = self.scratchpad.read_chunk(key, chunk_index)
        if result is None:
            return f"⚠️ Key '{key}' not found in scratchpad. [HINT]: Use scratchpad_list to see available keys."
        return result

class ScratchpadSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "scratchpad_search"

    @property
    def description(self) -> str:
        return "Search scratchpad content by keyword."

    @property
    def category(self) -> str:
        return "SESSION_SCRATCHPAD"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
            },
            "required": ["query"],
        }

    def execute(self, query: str) -> str:
        self._emit(f"🔍 Searching scratchpad for: '{query}'...")
        if not self.scratchpad:
            return "❌ Error: Scratchpad not initialized."
        results = self.scratchpad.search(query)
        if not results:
            return f"No scratchpad items matching '{query}'."
        lines = [f"Found {len(results)} match(es):\n"]
        for r in results:
            lines.append(f"• ref:{r['key']} — {r['description']}\n  Preview: {r['preview'][:100]}...")
        return "\n".join(lines)
