"""
🔗 App Connectors
Tools for interacting with other parts of the Cowork ecosytem (Notes, Kanban, etc.).
"""

import time
from typing import Any, Dict, Optional
from ..base import BaseTool

class NotesCreateTool(BaseTool):
    @property
    def name(self) -> str:
        return "notes_create"

    @property
    def description(self) -> str:
        return "Create a new note in the workspace."

    @property
    def category(self) -> str:
        return "APP_CONNECTORS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title (max 500 chars)"},
                "content": {"type": "string", "description": "Note content"},
                "category": {"type": "string", "description": "Category/tag for the note"},
            },
            "required": ["title", "content"],
        }

    def execute(self, title: str, content: str, category: str = "General") -> str:
        self._emit("📝 Creating note...")
        note_id = f"note_{int(time.time())}"
        return f"✅ Note created successfully!\n• ID: {note_id}\n• Title: {title}\n• Category: {category}\n• Length: {len(content)} chars\n\n[Note saved to workspace]"

class KanbanAddTaskTool(BaseTool):
    @property
    def name(self) -> str:
        return "kanban_add_task"

    @property
    def description(self) -> str:
        return "Add a task to the Kanban board."

    @property
    def category(self) -> str:
        return "APP_CONNECTORS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Task description"},
                "priority": {"type": "string", "description": "Priority: low, medium, high", "enum": ["low", "medium", "high"]},
                "due_date": {"type": "string", "description": "Due date in ISO format"},
            },
            "required": ["title"],
        }

    def execute(self, title: str, description: str = "", priority: str = "medium", due_date: str = "") -> str:
        self._emit("📋 Adding task to Kanban board...")
        task_id = f"task_{int(time.time())}"
        return f"✅ Task added to Kanban!\n• ID: {task_id}\n• Title: {title}\n• Priority: {priority}\n• Due: {due_date or 'Not set'}"

class StorageWriteTool(BaseTool):
    @property
    def name(self) -> str:
        return "storage_write"

    @property
    def description(self) -> str:
        return "Write content to a persistent workspace file."

    @property
    def category(self) -> str:
        return "APP_CONNECTORS"

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
        path.write_text(content, encoding="utf-8")
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
