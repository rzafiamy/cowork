"""
💻 Coding Tools
Project-root scoped tools for codebase listing, reading, searching, and writing.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import BaseTool
from ...workspace import WorkspaceSession, workspace_manager


def _ensure_dir(path: Path) -> Optional[Path]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:
        return None


def _project_root(scratchpad: Any = None) -> Path:
    configured = os.getenv("COWORK_PROJECT_ROOT", "").strip()
    if configured:
        root = Path(configured).expanduser().resolve()
        ensured = _ensure_dir(root)
        if ensured is not None:
            return ensured

    ws_root = _workspace_session_code_root(scratchpad)
    if ws_root is not None:
        ensured = _ensure_dir(ws_root)
        if ensured is not None:
            return ensured

    # Dedicated fallback under ~/.cowork instead of current working directory.
    fallback = Path.home() / ".cowork" / "workspace" / "_coding" / "artifacts" / "codebase"
    ensured = _ensure_dir(fallback)
    if ensured is not None:
        return ensured

    # Last-resort writable root for restricted environments.
    tmp_fallback = Path("/tmp") / "cowork" / "codebase"
    ensured = _ensure_dir(tmp_fallback)
    if ensured is not None:
        return ensured

    # Avoid surprising cwd writes by raising if no dedicated root is writable.
    raise OSError("No writable coding project root available.")


def _workspace_session_code_root(scratchpad: Any = None) -> Optional[Path]:
    if scratchpad is None:
        return None
    session_id = getattr(scratchpad, "session_id", None)
    if not session_id:
        return None
    try:
        for info in workspace_manager.list_all():
            if info.get("session_id") == session_id:
                ws = WorkspaceSession.load(info["slug"])
                if ws:
                    return ws.artifacts_path / "codebase"
    except Exception:
        return None
    return None


def _resolve_in_project(path: str, scratchpad: Any = None) -> Path:
    root = _project_root(scratchpad)
    raw = Path(path)
    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Path escapes project root.")
    return candidate


def _is_text_file(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(2048)
        return b"\x00" not in chunk
    except OSError:
        return False


class CodebaseListFilesTool(BaseTool):
    @property
    def name(self) -> str:
        return "codebase_list_files"

    @property
    def description(self) -> str:
        return (
            "List files under the project root. Useful before coding tasks to inspect structure. "
            "Returns paths relative to project root."
        )

    @property
    def category(self) -> str:
        return "CODING_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Relative directory under project root.", "default": "."},
                "max_depth": {"type": "integer", "description": "Maximum directory depth to traverse.", "default": 4},
                "max_results": {"type": "integer", "description": "Maximum number of files returned.", "default": 200},
            },
            "required": [],
        }

    def execute(self, directory: str = ".", max_depth: int = 4, max_results: int = 200) -> str:
        try:
            root = _project_root(self.scratchpad)
            start = _resolve_in_project(directory, self.scratchpad)
            if not start.exists():
                return f"❌ Directory not found: {directory}"
            if not start.is_dir():
                return f"❌ Not a directory: {directory}"

            max_depth = max(1, min(int(max_depth), 12))
            max_results = max(1, min(int(max_results), 1000))
            self._emit(f"💻 Listing codebase files in '{start}'...")

            lines = [f"📂 Project root: {root}", f"📁 Directory: {start.relative_to(root)}", ""]
            count = 0
            base_depth = len(start.parts)
            for p in sorted(start.rglob("*")):
                if not p.is_file():
                    continue
                depth = len(p.parts) - base_depth
                if depth > max_depth:
                    continue
                rel = p.relative_to(root)
                lines.append(f"- {rel}")
                count += 1
                if count >= max_results:
                    break

            if count == 0:
                lines.append("(no files found)")
            elif count >= max_results:
                lines.append(f"\n... truncated at {max_results} files")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Failed to list files: {e}"


class CodebaseReadFileTool(BaseTool):
    @property
    def name(self) -> str:
        return "codebase_read_file"

    @property
    def description(self) -> str:
        return (
            "Read a text file from the project root with optional line range. "
            "Use this for source inspection during coding tasks."
        )

    @property
    def category(self) -> str:
        return "CODING_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path under project root."},
                "start_line": {"type": "integer", "description": "1-based start line.", "default": 1},
                "end_line": {"type": "integer", "description": "1-based inclusive end line.", "default": 200},
            },
            "required": ["path"],
        }

    def execute(self, path: str, start_line: int = 1, end_line: int = 200) -> str:
        try:
            target = _resolve_in_project(path, self.scratchpad)
            if not target.exists():
                return f"❌ File not found: {path}"
            if not target.is_file():
                return f"❌ Not a file: {path}"
            if not _is_text_file(target):
                return f"❌ File appears binary and cannot be rendered safely: {path}"

            start = max(1, int(start_line))
            end = max(start, min(int(end_line), start + 1000))
            self._emit(f"💻 Reading file '{target.name}' lines {start}-{end}...")

            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = lines[start - 1:end]
            out = [f"📄 {path} (lines {start}-{min(end, len(lines))} of {len(lines)})", ""]
            for idx, line in enumerate(selected, start=start):
                out.append(f"{idx:>4}: {line}")
            return "\n".join(out)
        except Exception as e:
            return f"❌ Failed to read file: {e}"


class CodebaseSearchTextTool(BaseTool):
    @property
    def name(self) -> str:
        return "codebase_search_text"

    @property
    def description(self) -> str:
        return (
            "Search text/regex across project files. Returns compact matches with file path and line number."
        )

    @property
    def category(self) -> str:
        return "CODING_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text or regex pattern to search for."},
                "directory": {"type": "string", "description": "Relative directory under project root.", "default": "."},
                "use_regex": {"type": "boolean", "description": "Interpret query as regex.", "default": False},
                "max_results": {"type": "integer", "description": "Maximum number of matches to return.", "default": 80},
            },
            "required": ["query"],
        }

    def execute(
        self,
        query: str,
        directory: str = ".",
        use_regex: bool = False,
        max_results: int = 80,
    ) -> str:
        try:
            root = _project_root(self.scratchpad)
            start = _resolve_in_project(directory, self.scratchpad)
            if not start.exists() or not start.is_dir():
                return f"❌ Directory not found: {directory}"

            max_results = max(1, min(int(max_results), 500))
            self._emit(f"💻 Searching codebase for '{query}'...")

            matcher = re.compile(query) if use_regex else None
            matches: list[str] = []
            for file in start.rglob("*"):
                if not file.is_file() or not _is_text_file(file):
                    continue
                rel = file.relative_to(root)
                content = file.read_text(encoding="utf-8", errors="replace").splitlines()
                for ln, text in enumerate(content, start=1):
                    hit = bool(matcher.search(text)) if matcher else (query in text)
                    if hit:
                        snippet = text.strip()
                        if len(snippet) > 160:
                            snippet = snippet[:160] + "..."
                        matches.append(f"- {rel}:{ln} | {snippet}")
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break

            if not matches:
                return f"No matches found for '{query}'."
            return f"🔎 Matches for '{query}':\n\n" + "\n".join(matches)
        except re.error as e:
            return f"❌ Invalid regex: {e}"
        except Exception as e:
            return f"❌ Search failed: {e}"


class CodebaseWriteFileTool(BaseTool):
    @property
    def name(self) -> str:
        return "codebase_write_file"

    @property
    def description(self) -> str:
        return (
            "Write text content to a file under project root. Creates parent folders as needed. "
            "Use mode='append' to append; default mode='overwrite'."
        )

    @property
    def category(self) -> str:
        return "CODING_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path under project root."},
                "content": {"type": "string", "description": "File content to write."},
                "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
            },
            "required": ["path", "content"],
        }

    def execute(self, path: str, content: str, mode: str = "overwrite") -> str:
        try:
            root = _project_root(self.scratchpad)
            target = _resolve_in_project(path, self.scratchpad)
            target.parent.mkdir(parents=True, exist_ok=True)
            write_mode = "a" if mode == "append" else "w"
            self._emit(f"💻 Writing file '{path}' ({mode})...")
            with open(target, write_mode, encoding="utf-8") as f:
                f.write(content)
            size = target.stat().st_size
            rel = target.relative_to(root) if target != root else Path(".")
            return (
                f"✅ File written: {rel}\n"
                f"• Mode: {mode}\n"
                f"• Root: {root}\n"
                f"• Size: {size:,} bytes"
            )
        except Exception as e:
            return f"❌ Failed to write file: {e}"


class CodebaseGrepTool(BaseTool):
    @property
    def name(self) -> str:
        return "codebase_grep"

    @property
    def description(self) -> str:
        return (
            "Run grep-style search across project files. Uses ripgrep (rg) when available, "
            "falls back to grep. Returns file:line and matched text."
        )

    @property
    def category(self) -> str:
        return "CODING_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Pattern to search for."},
                "directory": {"type": "string", "description": "Relative directory under project root.", "default": "."},
                "ignore_case": {"type": "boolean", "description": "Case-insensitive match.", "default": True},
                "use_regex": {"type": "boolean", "description": "Treat pattern as regex.", "default": True},
                "max_results": {"type": "integer", "description": "Maximum number of lines returned.", "default": 120},
            },
            "required": ["pattern"],
        }

    def execute(
        self,
        pattern: str,
        directory: str = ".",
        ignore_case: bool = True,
        use_regex: bool = True,
        max_results: int = 120,
    ) -> str:
        try:
            root = _project_root(self.scratchpad)
            start = _resolve_in_project(directory, self.scratchpad)
            if not start.exists() or not start.is_dir():
                return f"❌ Directory not found: {directory}"

            max_results = max(1, min(int(max_results), 500))
            self._emit(f"💻 Running grep in '{start.relative_to(root)}'...")

            if shutil.which("rg"):
                cmd = ["rg", "-n", "--no-heading", "--color", "never", "-m", str(max_results)]
                if ignore_case:
                    cmd.append("-i")
                if not use_regex:
                    cmd.append("-F")
                cmd.append(pattern)
                cmd.append(str(start))
            elif shutil.which("grep"):
                cmd = ["grep", "-R", "-n", "-m", str(max_results)]
                if ignore_case:
                    cmd.append("-i")
                if not use_regex:
                    cmd.append("-F")
                cmd.append(pattern)
                cmd.append(str(start))
            else:
                return "❌ Neither 'rg' nor 'grep' is available on this system."

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(root),
                timeout=20,
            )
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()

            if not stdout:
                if proc.returncode == 1:
                    return f"No matches found for pattern: {pattern}"
                return f"❌ grep command failed: {stderr or 'unknown error'}"

            lines = stdout.splitlines()[:max_results]
            rel_lines = []
            for ln in lines:
                if ln.startswith(str(root) + os.sep):
                    rel_lines.append(ln[len(str(root)) + 1 :])
                else:
                    rel_lines.append(ln)
            return "🔎 grep results:\n\n" + "\n".join(rel_lines)
        except subprocess.TimeoutExpired:
            return "❌ grep timed out."
        except Exception as e:
            return f"❌ grep failed: {e}"
