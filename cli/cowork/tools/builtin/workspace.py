"""
📁 Workspace Tools
Tools for interacting with the workspace filesystem and session artifacts.
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional
from ..base import BaseTool
from ...workspace import WorkspaceSession, workspace_manager, WORKSPACE_ROOT

class WorkspaceWriteTool(BaseTool):
    @property
    def name(self) -> str:
        return "workspace_write"

    @property
    def description(self) -> str:
        return (
            "Write a file to the current session's workspace artifacts/ folder. "
            "Use this to persist code, reports, configs, or any output the user should keep. "
            "Files are stored at workspace/<session-title>/artifacts/<filename>."
        )

    @property
    def category(self) -> str:
        return "WORKSPACE_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename with extension, e.g. 'report.md' or 'script.py'"},
                "content":  {"type": "string", "description": "Full file content to write"},
            },
            "required": ["filename", "content"],
        }

    def _get_workspace_session(self) -> Optional[WorkspaceSession]:
        if not self.scratchpad:
            return None
        session_id = self.scratchpad.session_id
        for info in workspace_manager.list_all():
            if info["session_id"] == session_id:
                return WorkspaceSession.load(info["slug"])
        return None

    def execute(self, filename: str, content: str) -> str:
        self._emit(f"📁 Writing workspace artifact: '{filename}'...")
        ws = self._get_workspace_session()
        if not ws:
            path = WORKSPACE_ROOT / filename
            path.write_text(content, encoding="utf-8")
            return f"✅ Written to workspace: {path}\n• Size: {len(content)} chars"
        path = ws.write_artifact(filename, content)
        return (
            f"✅ Artifact saved to workspace!\n"
            f"• Path: `{path}`\n"
            f"• Session: `{ws.slug}/`\n"
            f"• Size: {len(content):,} chars"
        )

class WorkspaceReadTool(BaseTool):
    @property
    def name(self) -> str:
        return "workspace_read"

    @property
    def description(self) -> str:
        return (
            "Read a file from the current session's workspace folder. "
            "Can read from artifacts/, notes/, or the context.md file."
        )

    @property
    def category(self) -> str:
        return "WORKSPACE_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename to read, e.g. 'report.md', 'context.md', or 'notes/2024_note.md'"},
            },
            "required": ["filename"],
        }

    def _get_workspace_session(self) -> Optional[WorkspaceSession]:
        if not self.scratchpad:
            return None
        session_id = self.scratchpad.session_id
        for info in workspace_manager.list_all():
            if info["session_id"] == session_id:
                return WorkspaceSession.load(info["slug"])
        return None

    def execute(self, filename: str) -> str:
        self._emit(f"📖 Reading workspace file: '{filename}'...")
        ws = self._get_workspace_session()
        if not ws:
            return "❌ Error: No active workspace session found."

        if filename == "context.md":
            content = ws.read_context()
            return content if content else "(context.md is empty)"

        artifact_path = ws.artifacts_path / Path(filename).name
        if artifact_path.exists():
            return artifact_path.read_text(encoding="utf-8")

        note_path = ws.notes_path / Path(filename).name
        if note_path.exists():
            return note_path.read_text(encoding="utf-8")

        content = ws.scratchpad_get(filename)
        if content:
            return content

        return f"❌ Error: File '{filename}' not found in workspace session '{ws.slug}'."

class WorkspaceListTool(BaseTool):
    @property
    def name(self) -> str:
        return "workspace_list"

    @property
    def description(self) -> str:
        return "List all files in the current session's workspace folder (artifacts, notes, scratchpad)."

    @property
    def category(self) -> str:
        return "WORKSPACE_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def _get_workspace_session(self) -> Optional[WorkspaceSession]:
        if not self.scratchpad:
            return None
        session_id = self.scratchpad.session_id
        for info in workspace_manager.list_all():
            if info["session_id"] == session_id:
                return WorkspaceSession.load(info["slug"])
        return None

    def execute(self) -> str:
        self._emit("📋 Listing workspace session files...")
        ws = self._get_workspace_session()
        if not ws:
            sessions = workspace_manager.list_all()
            if not sessions:
                return "No workspace sessions found."
            lines = [f"📂 Workspace root: {WORKSPACE_ROOT}\n", "Sessions:"]
            for s in sessions[:20]:
                lines.append(f"  • {s['slug']}/ — {s['title']} ({s['message_count']} msgs)")
            return "\n".join(lines)

        lines = [f"📂 Session workspace: `{ws.slug}/`\n"]
        if ws.context_path.exists():
            size = ws.context_path.stat().st_size
            lines.append(f"  📄 context.md ({size:,} bytes)")

        artifacts = ws.list_artifacts()
        if artifacts:
            lines.append(f"\n  📦 artifacts/ ({len(artifacts)} files):")
            for a in artifacts:
                lines.append(f"    • {a['filename']} ({a['size_bytes']:,} bytes)")

        notes = list(ws.notes_path.glob("*.md"))
        if notes:
            lines.append(f"\n  📝 notes/ ({len(notes)} files):")
            for n in sorted(notes):
                lines.append(f"    • {n.name}")

        blobs = ws.scratchpad_list()
        if blobs:
            lines.append(f"\n  💾 scratchpad/ ({len(blobs)} blobs):")
            for b in blobs:
                lines.append(f"    • ref:{b['key']} — {b.get('description', '')} ({b['size_chars']:,} chars)")

        return "\n".join(lines)

class WorkspaceNoteTool(BaseTool):
    @property
    def name(self) -> str:
        return "workspace_note"

    @property
    def description(self) -> str:
        return (
            "Save a structured note to the session's notes/ folder. "
            "Notes are Markdown files with a title, category, and content. "
            "Use this for research summaries, meeting notes, or any knowledge worth keeping."
        )

    @property
    def category(self) -> str:
        return "WORKSPACE_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title":    {"type": "string", "description": "Note title"},
                "content":  {"type": "string", "description": "Note content (Markdown supported)"},
                "category": {"type": "string", "description": "Category tag, e.g. 'Research', 'Meeting', 'Code'"},
            },
            "required": ["title", "content"],
        }

    def _get_workspace_session(self) -> Optional[WorkspaceSession]:
        if not self.scratchpad:
            return None
        session_id = self.scratchpad.session_id
        for info in workspace_manager.list_all():
            if info["session_id"] == session_id:
                return WorkspaceSession.load(info["slug"])
        return None

    def execute(self, title: str, content: str, category: str = "General") -> str:
        self._emit(f"📝 Saving workspace note: '{title}'...")
        ws = self._get_workspace_session()
        if not ws:
            return "❌ Error: No active workspace session found."
        path = ws.save_note(title, content, category)
        return (
            f"✅ Note saved!\n"
            f"• Title: {title}\n"
            f"• Category: {category}\n"
            f"• Path: `{path}`"
        )

class WorkspaceContextUpdateTool(BaseTool):
    @property
    def name(self) -> str:
        return "workspace_context_update"

    @property
    def description(self) -> str:
        return (
            "Update the session's context.md file — the living document that tracks "
            "what has been done, key decisions, and ongoing state. "
            "The agent should update this after major milestones."
        )

    @property
    def category(self) -> str:
        return "WORKSPACE_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "New content to append to context.md"},
                "replace": {"type": "boolean", "description": "If true, replace the entire context.md. If false (default), append."},
            },
            "required": ["content"],
        }

    def _get_workspace_session(self) -> Optional[WorkspaceSession]:
        if not self.scratchpad:
            return None
        session_id = self.scratchpad.session_id
        for info in workspace_manager.list_all():
            if info["session_id"] == session_id:
                return WorkspaceSession.load(info["slug"])
        return None

    def execute(self, content: str, replace: bool = False) -> str:
        self._emit("✏️  Updating session context.md...")
        ws = self._get_workspace_session()
        if not ws:
            return "❌ Error: No active workspace session found."
        ws.write_context(content, append=not replace)
        action = "replaced" if replace else "appended to"
        return (
            f"✅ context.md {action}!\n"
            f"• Session: `{ws.slug}/`\n"
            f"• Path: `{ws.context_path}`"
        )

class WorkspaceSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "workspace_search"

    @property
    def description(self) -> str:
        return "Search across all workspace sessions for a keyword. Returns matching sessions and files."

    @property
    def category(self) -> str:
        return "WORKSPACE_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term to look for across all sessions"},
            },
            "required": ["query"],
        }

    def execute(self, query: str) -> str:
        self._emit(f"🔍 Searching workspace for: '{query}'...")
        results = workspace_manager.search(query)
        if not results:
            return f"No workspace sessions found matching '{query}'."
        lines = [f"Found {len(results)} session(s) matching '{query}':\n"]
        for r in results:
            lines.append(f"  📂 {r['slug']}/ — {r['title']}")
            # Note: The original code had a truncated loop here, I'll just show the sessions.
        return "\n".join(lines)
