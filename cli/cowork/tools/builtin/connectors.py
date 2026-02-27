"""
🔗 App Connectors
Tools for interacting with other parts of the Cowork ecosystem (Storage, Weather, etc.).
Note: Notes and Kanban have been migrated to Supabase-backed skills.
"""

import time
from typing import Any, Dict, Optional
from ..base import BaseTool

class StorageWriteTool(BaseTool):
    @property
    def name(self) -> str:
        return "storage_write"

    @property
    def description(self) -> str:
        return "Write content to a persistent workspace file."

    @property
    def category(self) -> str:
        return "WORKSPACE_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename with extension"},
                "content": {"type": "string", "description": "File content"},
            },
            "required": ["filename", "content"],
        }

    def execute(self, filename: str, content: str) -> str:
        from pathlib import Path
        from ...workspace import workspace_manager, WORKSPACE_ROOT

        safe_filename = Path(filename).name
        self._emit(f"💾 Writing to workspace storage: '{safe_filename}'...")
        path = None
        if self.scratchpad:
            ws = workspace_manager.get_by_session_id(self.scratchpad.session_id)
            if ws:
                path = ws.artifacts_path / safe_filename
        if path is None:
            fallback_dir = WORKSPACE_ROOT / "artifacts"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            path = fallback_dir / safe_filename
        from ...acl import file_manager
        file_manager.write_text(path, content, reason="storage_write tool")
        return f"✅ File written: {path}\n• Size: {len(content)} chars"

class GetWeatherTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Fetch current weather for a location."

    @property
    def category(self) -> str:
        # Note: the original category was DATA_AND_UTILITY but in tools.py it was handled specially.
        return "DATA_AND_UTILITY"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City and country, e.g. 'Paris, FR'"},
            },
            "required": ["location"],
        }

    def execute(self, location: str) -> str:
        self._emit(f"🌤️ Fetching weather for: '{location}'...")
        from ..external.implementations import openweather_current, _env
        if _env("OPENWEATHER_API_KEY"):
            return openweather_current(location=location)
        return "❌ Legacy `get_weather` is disabled. [HINT]: Add `OPENWEATHER_API_KEY` to `.env` to use premium weather tools."
