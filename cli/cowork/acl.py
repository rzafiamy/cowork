"""
🛡️ File Access Control Layer
Centralizes read/write guards for the workspace filesystem, similar to the firewall
that governs tool execution. Rules are loaded from ~/.cowork/acl.yaml and each
access attempt (read/write) is logged so it can be traced alongside tool calls.

Every filesystem I/O inside Cowork MUST go through FileManager (the singleton
`file_manager`). This guarantees:
  • ACL rules are always enforced – no bypasses, no surprises.
  • Every read/write is traced in acl.log for auditability.
  • The policy (default allow/block) is respected consistently.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
from contextvars import ContextVar

import yaml

from .paths import CONFIG_DIR, ACL_FILE, ACL_LOG_FILE

logger = logging.getLogger("cowork.acl")


# ─── Enums & Constants ────────────────────────────────────────────────────────

class FileAccessType(str, Enum):
    READ = "read"
    WRITE = "write"


class FileAccessAction(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    AUDIT = "audit"

# ─── Default Policy ───────────────────────────────────────────────────────────
DEFAULT_POLICY = {
    "default_read": FileAccessAction.ALLOW,
    "default_write": FileAccessAction.ALLOW,
}
ACCESS_ANY = "any"
VALID_ACCESS = {ACCESS_ANY, "read", "write"}

# Context variable to track the current session ID for logging
current_session_id = ContextVar[Optional[str]]("current_session_id", default=None)


# ─── Exceptions ───────────────────────────────────────────────────────────────

class FileAccessDenied(PermissionError):
    def __init__(self, path: Path, access: FileAccessType, rule: Optional[ACLRule] = None):
        reason = rule.description if rule and rule.description else "no matching rule"
        msg = (
            f"{access.name} access denied for {path} — action=block, {reason}"
        )
        super().__init__(msg)


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class ACLRule:
    pattern: str
    normalized_pattern: str
    access: str
    action: FileAccessAction
    description: str


# ─── Access Control Manager ───────────────────────────────────────────────────

class AccessControlManager:
    """Loads ACL rules and verifies every guarded file operation."""

    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir
        self.path = config_dir / "acl.yaml"
        self.log_path = config_dir / "acl.log"
        self.last_load_error: str = ""
        self._rules: list[ACLRule] = []
        self._policy = DEFAULT_POLICY.copy()
        self._trace_cb: Callable[[str, dict[str, Any]], None] = lambda *_: None
        self._load()

    def _load(self) -> None:
        """Load ACL rules from YAML, creating a safe default if needed."""
        self.last_load_error = ""
        if not self.path.exists():
            self._create_default()

        try:
            with open(self.path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.exception("Failed to parse acl.yaml")
            self.last_load_error = f"ACL parse failed: {exc}"
            self._rules = []
            self._policy = DEFAULT_POLICY.copy()
            return

        if not isinstance(data, dict):
            self.last_load_error = "Top-level ACL document must be a mapping"
            self._rules = []
            self._policy = DEFAULT_POLICY.copy()
            return

        policy = data.get("policy", {})
        self._policy = {
            "default_read": self._normalize_action(policy.get("default_read")) or FileAccessAction.ALLOW,
            "default_write": self._normalize_action(policy.get("default_write")) or FileAccessAction.ALLOW,
        }

        rules = data.get("rules", [])
        if not isinstance(rules, list):
            self.last_load_error = "Field 'rules' must be a list"
            self._rules = []
            return

        parsed: list[ACLRule] = []
        for entry in rules:
            if not isinstance(entry, dict):
                continue
            pattern = str(entry.get("pattern", "*")).strip() or "*"
            access = str(entry.get("access", ACCESS_ANY)).strip().lower()
            if access not in VALID_ACCESS:
                access = ACCESS_ANY
            action = self._normalize_action(entry.get("action")) or FileAccessAction.ALLOW
            description = str(entry.get("description", "")).strip()
            normalized_pattern = self._normalize_pattern(pattern)
            parsed.append(
                ACLRule(
                    pattern=pattern,
                    normalized_pattern=normalized_pattern,
                    access=access,
                    action=action,
                    description=description,
                )
            )

        self._rules = parsed

    def _create_default(self) -> None:
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            default = """# 🗝️ Cowork File Access Control (ACL)
# Defines guardrails for reads/writes inside the cowork storage.
# Every file operation by every tool goes through this file.

policy:
  default_read: allow
  default_write: allow

rules:
  - access: read
    pattern: ~/.cowork/workspace/**
    action: allow
    description: Allow reading inside the workspace.

  - access: write
    pattern: ~/.cowork/workspace/**
    action: allow
    description: Allow writing artifacts and scratchpad data.

# Add additional rules to protect sensitive files:
# - pattern: ~/.cowork/config.json
#   access: write
#   action: block
#   description: Protect config file from agent writes.
"""
            self.path.write_text(default, encoding="utf-8")
        except OSError:
            logger.exception("Failed to write default acl.yaml")

    def _normalize_action(self, value: Any) -> Optional[FileAccessAction]:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in FileAccessAction._value2member_map_:
            return FileAccessAction(normalized)
        return None

    def _normalize_pattern(self, pattern: str) -> str:
        """
        Normalise an ACL pattern into a form suitable for fnmatch.

        Rules:
          1. If the pattern starts with '~', expand the home-dir prefix.
          2. If the result is an absolute path, normalise it.
          3. If the pattern starts with a glob metachar ('*', '?', '[')
             it is a pure glob — leave it as-is after normalising separators.
          4. Otherwise, treat it as a path relative to config_dir.
        """
        expanded = os.path.expanduser(pattern)

        # Pure-glob shortcut: don't anchor to config_dir.
        if expanded.startswith(("*", "?", "[")):
            return expanded.replace(os.sep, "/")

        if os.path.isabs(expanded):
            return os.path.normpath(expanded).replace(os.sep, "/")

        # Relative, non-glob → anchor to config_dir
        anchored = str((self.config_dir / expanded).resolve(strict=False))
        return os.path.normpath(anchored).replace(os.sep, "/")

    def _normalize_path(self, path: Path) -> str:
        try:
            resolved = path.expanduser().resolve(strict=False)
        except Exception:
            resolved = path.expanduser()
        normalized = os.path.normpath(str(resolved)).replace(os.sep, "/")
        return normalized

    def _default_action(self, access: FileAccessType) -> FileAccessAction:
        key = "default_read" if access == FileAccessType.READ else "default_write"
        return self._policy.get(key, FileAccessAction.ALLOW)

    def _match_rule(self, norm_path: str, access: FileAccessType) -> Optional[ACLRule]:
        for rule in self._rules:
            if rule.access != ACCESS_ANY and rule.access != access.value:
                continue
            if fnmatch.fnmatch(norm_path, rule.normalized_pattern):
                return rule
        return None

    def set_trace_callback(self, callback: Optional[Callable[[str, dict[str, Any]], None]]) -> None:
        self._trace_cb = callback or (lambda *_: None)

    def _log_event(self, event: str, data: dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": current_session_id.get(),
            "event": event,
            "data": data,
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("Failed to write ACL log")
        try:
            self._trace_cb(event, data)
        except Exception:
            logger.debug("ACL trace callback failed", exc_info=True)

    def check_access(self, path: Path, access: FileAccessType, *, reason: str = "") -> None:
        """Check ACL rules for *path* + *access* and raise FileAccessDenied if blocked."""
        norm_path = self._normalize_path(path)
        rule = self._match_rule(norm_path, access)
        action = rule.action if rule else self._default_action(access)
        entry = {
            "path": norm_path,
            "access": access.value,
            "action": action.value,
            "rule": rule.description if rule else "default",
            "reason": reason,
        }
        if action == FileAccessAction.BLOCK:
            self._log_event("acl_block", entry)
            raise FileAccessDenied(path, access, rule)
        if action == FileAccessAction.AUDIT:
            self._log_event("acl_audit", entry)
        else:
            self._log_event("acl_allow", entry)


# ─── Singleton ACL Manager ────────────────────────────────────────────────────

ACCESS_CONTROL = AccessControlManager()


# ─── Low-level ACL guards (kept for backward compatibility) ───────────────────

def guard_read(path: Path | str, *, reason: str = "") -> str:
    """Read a text file after ACL check. Raises FileAccessDenied if blocked."""
    path_obj = Path(path)
    ACCESS_CONTROL.check_access(path_obj, FileAccessType.READ, reason=reason)
    return path_obj.read_text(encoding="utf-8")


def guard_write(path: Path | str, content: str, *, reason: str = "") -> None:
    """Write a text file after ACL check. Raises FileAccessDenied if blocked."""
    path_obj = Path(path)
    ACCESS_CONTROL.check_access(path_obj, FileAccessType.WRITE, reason=reason)
    path_obj.write_text(content, encoding="utf-8")


def guard_append(path: Path | str, content: str, *, reason: str = "") -> None:
    """Append to a text file after ACL check. Raises FileAccessDenied if blocked."""
    path_obj = Path(path)
    ACCESS_CONTROL.check_access(path_obj, FileAccessType.WRITE, reason=reason)
    with path_obj.open("a", encoding="utf-8") as f:
        f.write(content)


# ─── FileManager — The Single Gateway for ALL File I/O ───────────────────────

class FileManager:
    """
    🗂️ Centralized File Manager (ACL-enforced)

    All Cowork file operations MUST go through this class.
    It guarantees that every read / write / append / bytes write is:
      1. ACL-checked before the operation.
      2. Logged in acl.log for full auditability.
      3. Error-safe (parent directories are created when needed).

    Usage
    -----
    From anywhere in the codebase::

        from .acl import file_manager

        # Text reads
        text = file_manager.read_text(path)

        # Text writes (overwrites)
        file_manager.write_text(path, content)

        # Text appends
        file_manager.append_text(path, extra)

        # Binary writes (e.g. PDF, images)
        file_manager.write_bytes(path, raw_bytes)

        # Binary reads
        raw = file_manager.read_bytes(path)

        # JSON helpers
        data = file_manager.read_json(path)
        file_manager.write_json(path, data)

        # Directory creation (audited as write on the parent)
        file_manager.makedirs(path)
    """

    def __init__(self, acl: AccessControlManager) -> None:
        self._acl = acl

    def check_access(self, path: Path | str, access: FileAccessType, *, reason: str = "") -> None:
        """Perform a manual ACL check."""
        self._acl.check_access(Path(path), access, reason=reason)

    # ── Text operations ───────────────────────────────────────────────────────

    def read_text(self, path: Path | str, *, reason: str = "", errors: str = "strict") -> str:
        """Read a UTF-8 text file after ACL check."""
        p = Path(path)
        self._acl.check_access(p, FileAccessType.READ, reason=reason)
        return p.read_text(encoding="utf-8", errors=errors)

    def write_text(self, path: Path | str, content: str, *, reason: str = "", mkdir: bool = True) -> None:
        """Overwrite a UTF-8 text file after ACL check. Creates parent dirs by default."""
        p = Path(path)
        self._acl.check_access(p, FileAccessType.WRITE, reason=reason)
        if mkdir:
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def append_text(self, path: Path | str, content: str, *, reason: str = "", mkdir: bool = True) -> None:
        """Append UTF-8 text to a file after ACL check. Creates parent dirs by default."""
        p = Path(path)
        self._acl.check_access(p, FileAccessType.WRITE, reason=reason)
        if mkdir:
            p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)

    # ── Binary operations ─────────────────────────────────────────────────────

    def read_bytes(self, path: Path | str, *, reason: str = "") -> bytes:
        """Read raw bytes from a file after ACL check."""
        p = Path(path)
        self._acl.check_access(p, FileAccessType.READ, reason=reason)
        return p.read_bytes()

    def write_bytes(self, path: Path | str, data: bytes, *, reason: str = "", mkdir: bool = True) -> None:
        """Write raw bytes to a file after ACL check. Creates parent dirs by default."""
        p = Path(path)
        self._acl.check_access(p, FileAccessType.WRITE, reason=reason)
        if mkdir:
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    # ── JSON helpers ──────────────────────────────────────────────────────────

    def read_json(self, path: Path | str, *, reason: str = "") -> Any:
        """Read and parse a JSON file after ACL check."""
        text = self.read_text(path, reason=reason)
        return json.loads(text)

    def write_json(self, path: Path | str, data: Any, *, reason: str = "", indent: int = 2, mkdir: bool = True) -> None:
        """Serialise *data* as JSON and write to *path* after ACL check."""
        text = json.dumps(data, indent=indent, ensure_ascii=False)
        self.write_text(path, text, reason=reason, mkdir=mkdir)

    # ── Directory helpers ─────────────────────────────────────────────────────

    def makedirs(self, path: Path | str, *, reason: str = "") -> None:
        """Create a directory tree after an ACL write-check on the path."""
        p = Path(path)
        self._acl.check_access(p, FileAccessType.WRITE, reason=reason or "makedirs")
        p.mkdir(parents=True, exist_ok=True)

    # ── Existence / metadata (no ACL check — pure stat) ──────────────────────

    def exists(self, path: Path | str) -> bool:
        return Path(path).exists()

    def is_file(self, path: Path | str) -> bool:
        return Path(path).is_file()

    def is_dir(self, path: Path | str) -> bool:
        return Path(path).is_dir()

    def unlink(self, path: Path | str, *, reason: str = "") -> None:
        """Delete a file after ACL check."""
        p = Path(path)
        self._acl.check_access(p, FileAccessType.WRITE, reason=reason or "unlink")
        p.unlink(missing_ok=True)

    def rmtree(self, path: Path | str, *, reason: str = "") -> None:
        """Delete a directory tree after ACL check."""
        import shutil
        p = Path(path)
        self._acl.check_access(p, FileAccessType.WRITE, reason=reason or "rmtree")
        shutil.rmtree(p, ignore_errors=True)

    def move(self, src: Path | str, dst: Path | str, *, reason: str = "") -> None:
        """Move/rename a file or directory after ACL check on both source and destination."""
        import shutil
        s = Path(src)
        d = Path(dst)
        self._acl.check_access(s, FileAccessType.WRITE, reason=f"{reason or 'move'} (src)")
        self._acl.check_access(d, FileAccessType.WRITE, reason=f"{reason or 'move'} (dst)")
        shutil.move(str(s), str(d))

    def listdir(self, path: Path | str, *, reason: str = "") -> list[str]:
        """List directory contents after ACL check."""
        p = Path(path)
        self._acl.check_access(p, FileAccessType.READ, reason=reason or "listdir")
        return os.listdir(p)

    def glob(self, path: Path | str, pattern: str, *, reason: str = "") -> list[Path]:
        """Glob directory contents after ACL check."""
        p = Path(path)
        self._acl.check_access(p, FileAccessType.READ, reason=reason or "glob")
        return list(p.glob(pattern))


# ─── Singleton FileManager ────────────────────────────────────────────────────

file_manager = FileManager(ACCESS_CONTROL)
