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


class ScratchpadUpdateGoalTool(BaseTool):
    """
    Dedicated tool for maintaining a structured task goal anchor.
    Saves/updates the canonical `task_goal` scratchpad entry, which the AI
    reads at the start of every follow-up turn to avoid losing context.
    """

    @property
    def name(self) -> str:
        return "scratchpad_update_goal"

    @property
    def description(self) -> str:
        return (
            "Save or update the structured task goal anchor (key=task_goal). "
            "Use this at the START of any multi-step task and AFTER each refinement turn "
            "to track the current state, remaining steps, and user preferences. "
            "The AI reads this at the beginning of every follow-up to stay oriented."
        )

    @property
    def category(self) -> str:
        return "SESSION_SCRATCHPAD"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "One-line description of the user's final objective",
                },
                "scope": {
                    "type": "string",
                    "description": "Key constraints — e.g. '10 slides, business audience, dark theme'",
                },
                "current_state": {
                    "type": "string",
                    "description": "What has been produced so far — e.g. 'slides 1-10 created, slide 3 needs more detail'",
                },
                "next_steps": {
                    "type": "string",
                    "description": "What still needs to be done to fulfil the goal",
                },
                "user_preferences": {
                    "type": "string",
                    "description": "Style, tone, format, or other preferences stated by the user",
                },
            },
            "required": ["goal", "current_state", "next_steps"],
        }

    def execute(
        self,
        goal: str,
        current_state: str,
        next_steps: str,
        scope: str = "",
        user_preferences: str = "",
    ) -> str:
        self._emit("🎯 Updating task goal anchor...")
        if not self.scratchpad:
            return "❌ Error: Scratchpad not initialized."

        content = (
            f"GOAL: {goal}\n"
            f"SCOPE: {scope or 'not specified'}\n"
            f"CURRENT_STATE: {current_state}\n"
            f"NEXT_STEPS: {next_steps}\n"
            f"USER_PREFERENCES: {user_preferences or 'none specified'}"
        )
        ref = self.scratchpad.save(
            key="task_goal",
            content=content,
            description=f"Task goal: {goal[:60]}{'...' if len(goal) > 60 else ''}",
        )
        return (
            f"✅ Task goal anchor saved as {ref}. "
            f"The AI will read this at the start of every follow-up turn to stay oriented."
        )

class ScratchpadForkTool(BaseTool):
    @property
    def name(self) -> str:
        return "scratchpad_fork"

    @property
    def description(self) -> str:
        return "Duplicate an existing scratchpad entry to a new key. Useful for non-destructive editing or maintaining a base draft."

    @property
    def category(self) -> str:
        return "SESSION_SCRATCHPAD"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_key": {"type": "string", "description": "The existing scratchpad key (with or without 'ref:' prefix)"},
                "dest_key": {"type": "string", "description": "The new key to save the duplicate as (alphanumeric + underscore)"},
            },
            "required": ["source_key", "dest_key"],
        }

    def execute(self, source_key: str, dest_key: str) -> str:
        self._emit(f"🔀 Forking scratchpad entry: '{source_key}' to '{dest_key}'...")
        if not self.scratchpad:
            return "❌ Error: Scratchpad not initialized."
            
        content = self.scratchpad.get(source_key)
        if content is None:
             return f"⚠️ Source key '{source_key}' not found in scratchpad."
             
        # Look up original description
        original_desc = "Forked entry"
        items = self.scratchpad.list_all()
        clean_source = source_key.replace("ref:", "")
        for item in items:
            if item["key"] == clean_source:
                original_desc = item.get("description", "Forked entry")
                break
                
        ref = self.scratchpad.save(dest_key, content, f"{original_desc} (forked)")
        return f"✅ Forked scratchpad entry. New memory reference: {ref} ({len(content)} chars)"

class ScratchpadGetOutlineTool(BaseTool):
    @property
    def name(self) -> str:
        return "scratchpad_get_outline"

    @property
    def description(self) -> str:
        return "Get a structural outline (table of contents) of a scratchpad entry with line numbers. Use this to navigate large documents before editing specific lines."

    @property
    def category(self) -> str:
        return "SESSION_SCRATCHPAD"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The scratchpad key (with or without 'ref:' prefix)"},
            },
            "required": ["key"],
        }

    def execute(self, key: str) -> str:
        self._emit(f"📑 Generating outline for: '{key}'...")
        if not self.scratchpad:
            return "❌ Error: Scratchpad not initialized."
            
        content = self.scratchpad.get(key)
        if content is None:
             return f"⚠️ Key '{key}' not found in scratchpad."

        lines = content.split('\n')
        outline = []
        
        # Simple heuristic: Look for Markdown headers or JSON top-level keys
        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()
            if stripped.startswith('#'):
                outline.append(f"Line {line_num:4d} | {stripped[:60]}")
            elif stripped.startswith('"') and '":' in stripped and len(stripped) < 40:
                # Naive JSON key detection
                outline.append(f"Line {line_num:4d} | {stripped}")
                
        total_lines = len(lines)
        if not outline:
            return f"Document '{key}' has {total_lines} lines.\nNo semantic headings found. You may need to read chunks to navigate."
            
        return f"Outline for '{key}' ({total_lines} total lines):\n" + "\n".join(outline)

class ScratchpadEditLinesTool(BaseTool):
    @property
    def name(self) -> str:
        return "scratchpad_edit_lines"

    @property
    def description(self) -> str:
        return "Replace a specific range of lines in a scratchpad entry. Use scratchpad_get_outline first to find the correct line numbers."

    @property
    def category(self) -> str:
        return "SESSION_SCRATCHPAD"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The scratchpad key (with or without 'ref:' prefix)"},
                "start_line": {"type": "integer", "description": "Starting line number to replace (1-indexed, inclusive)"},
                "end_line": {"type": "integer", "description": "Ending line number to replace (1-indexed, inclusive)"},
                "new_content": {"type": "string", "description": "The new content to insert in place of the specified lines"},
            },
            "required": ["key", "start_line", "end_line", "new_content"],
        }

    def execute(self, key: str, start_line: int, end_line: int, new_content: str) -> str:
        self._emit(f"✂️ Editing lines {start_line}-{end_line} in '{key}'...")
        if not self.scratchpad:
            return "❌ Error: Scratchpad not initialized."
            
        content = self.scratchpad.get(key)
        if content is None:
             return f"⚠️ Key '{key}' not found in scratchpad."

        lines = content.split('\n')
        total_lines = len(lines)
        
        if start_line < 1 or end_line < start_line:
            return f"❌ Error: Invalid line range {start_line}-{end_line}. Lines are 1-indexed."
            
        if start_line > total_lines:
            return f"❌ Error: start_line {start_line} is beyond the document length ({total_lines} lines)."
            
        # Convert to 0-indexed for Python list slicing
        start_idx = start_line - 1
        end_idx = min(end_line, total_lines)
        
        # Replace the slice
        prefix = lines[:start_idx]
        suffix = lines[end_idx:]
        
        new_lines = new_content.split('\n')
        modified_lines = prefix + new_lines + suffix
        modified_content = '\n'.join(modified_lines)
        
        # Keep original description
        original_desc = "Edited entry"
        items = self.scratchpad.list_all()
        clean_key = key.replace("ref:", "")
        for item in items:
            if item["key"] == clean_key:
                original_desc = item.get("description", "Edited entry")
                break
                
        # Overwrite
        ref = self.scratchpad.save(clean_key, modified_content, original_desc)
        return f"✅ Successfully replaced lines {start_line}-{end_line}. New document size: {len(modified_lines)} lines."

class ScratchpadAppendTool(BaseTool):
    @property
    def name(self) -> str:
        return "scratchpad_append"

    @property
    def description(self) -> str:
        return "Add new content to the very end of a scratchpad entry."

    @property
    def category(self) -> str:
        return "SESSION_SCRATCHPAD"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The scratchpad key (with or without 'ref:' prefix)"},
                "new_content": {"type": "string", "description": "The content to append to the end of the document"},
            },
            "required": ["key", "new_content"],
        }

    def execute(self, key: str, new_content: str) -> str:
        self._emit(f"➕ Appending to '{key}'...")
        if not self.scratchpad:
            return "❌ Error: Scratchpad not initialized."
            
        content = self.scratchpad.get(key)
        if content is None:
             return f"⚠️ Key '{key}' not found in scratchpad."
             
        modified_content = content
        if not modified_content.endswith('\n') and not new_content.startswith('\n'):
            modified_content += '\n'
        modified_content += new_content
        
        # Keep original description
        original_desc = "Appended entry"
        items = self.scratchpad.list_all()
        clean_key = key.replace("ref:", "")
        for item in items:
            if item["key"] == clean_key:
                original_desc = item.get("description", "Appended entry")
                break
                
        # Overwrite
        ref = self.scratchpad.save(clean_key, modified_content, original_desc)
        return f"✅ Successfully appended content. New document size: {len(modified_content.splitlines())} lines."
