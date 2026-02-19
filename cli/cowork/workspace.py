"""
🗂️ Workspace Manager — Filesystem-as-Scratchpad
Manages sessions as human-readable titled folders in the project workspace/.

Each session lives at:
    workspace/<slug-title>/
        session.json        ← session metadata + messages
        context.md          ← running context/notes (agent-writable)
        scratchpad/         ← per-session large data blobs
        notes/              ← structured notes created during the session
        artifacts/          ← any files produced by the agent

This makes the filesystem a first-class, inspectable scratchpad:
  - Titles are human-readable (not UUIDs)
  - You can open any session folder in your editor
  - The agent can read/write files directly via workspace tools
  - Sessions persist across restarts and are easy to grep/search
"""

import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ─── Workspace Root Discovery ─────────────────────────────────────────────────

def _find_workspace_root() -> Path:
    """
    Returns ~/.cowork/workspace as the primary workspace root.
    """
    root = Path.home() / ".cowork" / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root


WORKSPACE_ROOT: Path = _find_workspace_root()


# ─── Slug Utilities ───────────────────────────────────────────────────────────

def _slugify(title: str, max_len: int = 48) -> str:
    """Convert a title to a safe, readable directory name."""
    # Lowercase, replace spaces/special chars with hyphens
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)          # remove non-word chars
    slug = re.sub(r"[\s_]+", "-", slug)            # spaces → hyphens
    slug = re.sub(r"-+", "-", slug)                # collapse multiple hyphens
    slug = slug.strip("-")
    return slug[:max_len] or "session"


def _unique_slug(title: str, existing: set[str]) -> str:
    """Ensure the slug is unique within existing slugs."""
    base = _slugify(title)
    slug = base
    counter = 2
    while slug in existing:
        slug = f"{base}-{counter}"
        counter += 1
    return slug


# ─── Workspace Session ────────────────────────────────────────────────────────

class WorkspaceSession:
    """
    A session backed by a human-readable folder in workspace/.

    Directory layout:
        workspace/<slug>/
            session.json        ← metadata + full message history
            context.md          ← free-form context/notes (agent can edit)
            scratchpad/         ← large data blobs (key → .txt files)
            notes/              ← structured notes
            artifacts/          ← produced files (code, reports, etc.)
    """

    META_FILE      = "session.json"
    CONTEXT_FILE   = "context.md"
    SCRATCHPAD_DIR = "scratchpad"
    NOTES_DIR      = "notes"
    ARTIFACTS_DIR  = "artifacts"

    def __init__(
        self,
        slug: str,
        session_id: str,
        title: str = "New Session",
        created_at: Optional[str] = None,
    ) -> None:
        self.slug       = slug
        self.session_id = session_id
        self.title      = title
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = self.created_at
        self.messages:  list[dict] = []
        self.summary:   str = ""
        self.triplets:  list[dict] = []
        self.metadata:  dict = {}

        self._dir = WORKSPACE_ROOT / slug
        self._ensure_dirs()

    # ── Directory Setup ───────────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / self.SCRATCHPAD_DIR).mkdir(exist_ok=True)
        (self._dir / self.NOTES_DIR).mkdir(exist_ok=True)
        (self._dir / self.ARTIFACTS_DIR).mkdir(exist_ok=True)

    @property
    def path(self) -> Path:
        return self._dir

    @property
    def context_path(self) -> Path:
        return self._dir / self.CONTEXT_FILE

    @property
    def scratchpad_path(self) -> Path:
        return self._dir / self.SCRATCHPAD_DIR

    @property
    def notes_path(self) -> Path:
        return self._dir / self.NOTES_DIR

    @property
    def artifacts_path(self) -> Path:
        return self._dir / self.ARTIFACTS_DIR

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "slug":       self.slug,
            "title":      self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages":   self.messages,
            "summary":    self.summary,
            "triplets":   self.triplets,
            "metadata":   self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceSession":
        ws = cls(
            slug=data["slug"],
            session_id=data["session_id"],
            title=data.get("title", "Untitled"),
            created_at=data.get("created_at"),
        )
        ws.updated_at = data.get("updated_at", ws.created_at)
        ws.messages   = data.get("messages", [])
        ws.summary    = data.get("summary", "")
        ws.triplets   = data.get("triplets", [])
        ws.metadata   = data.get("metadata", {})
        return ws

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist session metadata + messages to session.json."""
        self.updated_at = datetime.utcnow().isoformat()
        meta_path = self._dir / self.META_FILE
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, slug: str) -> Optional["WorkspaceSession"]:
        """Load a session from its slug directory."""
        path = WORKSPACE_ROOT / slug / "session.json"
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception:
            return None

    # ── Messages ──────────────────────────────────────────────────────────────

    def add_message(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        self.messages.append({
            "role":      role,
            "content":   content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata":  metadata or {},
        })
        self.updated_at = datetime.utcnow().isoformat()

    def get_chat_messages(self) -> list[dict]:
        """Return messages in OpenAI chat format."""
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    # ── Context File ──────────────────────────────────────────────────────────

    def read_context(self) -> str:
        """Read the free-form context.md file."""
        if self.context_path.exists():
            return self.context_path.read_text(encoding="utf-8")
        return ""

    def write_context(self, content: str, append: bool = False) -> None:
        """Write or append to context.md."""
        if append and self.context_path.exists():
            existing = self.context_path.read_text(encoding="utf-8")
            content = existing + "\n\n" + content
        self.context_path.write_text(content, encoding="utf-8")

    # ── Scratchpad (within workspace folder) ──────────────────────────────────

    def scratchpad_save(self, key: str, content: str, description: str = "") -> str:
        """Save a blob to the session's scratchpad folder. Returns ref:key."""
        safe_key = re.sub(r"[^\w-]", "_", key)
        blob_path = self.scratchpad_path / f"{safe_key}.txt"
        blob_path.write_text(content, encoding="utf-8")
        # Update index
        index_path = self.scratchpad_path / "_index.json"
        index: dict = {}
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text())
            except Exception:
                pass
        index[safe_key] = {
            "key":         safe_key,
            "description": description,
            "size_chars":  len(content),
            "saved_at":    datetime.utcnow().isoformat(),
            "path":        str(blob_path),
        }
        index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        return f"ref:{safe_key}"

    def scratchpad_get(self, key: str) -> Optional[str]:
        """Retrieve a scratchpad blob by key."""
        safe_key = key.replace("ref:", "").strip()
        blob_path = self.scratchpad_path / f"{safe_key}.txt"
        if blob_path.exists():
            return blob_path.read_text(encoding="utf-8")
        return None

    def scratchpad_list(self) -> list[dict]:
        """List all scratchpad blobs."""
        index_path = self.scratchpad_path / "_index.json"
        if not index_path.exists():
            return []
        try:
            return list(json.loads(index_path.read_text()).values())
        except Exception:
            return []

    # ── Notes ─────────────────────────────────────────────────────────────────

    def save_note(self, title: str, content: str, category: str = "General") -> str:
        """Save a structured note to the notes/ folder."""
        safe_title = _slugify(title)[:40]
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{safe_title}.md"
        note_path = self.notes_path / filename
        header = f"# {title}\n\n**Category:** {category}  \n**Created:** {datetime.utcnow().isoformat()}\n\n---\n\n"
        note_path.write_text(header + content, encoding="utf-8")
        return str(note_path)

    # ── Artifacts ─────────────────────────────────────────────────────────────

    def write_artifact(self, filename: str, content: str) -> str:
        """Write a file to the artifacts/ folder."""
        # Sanitize filename
        safe_name = Path(filename).name  # strip any path traversal
        artifact_path = self.artifacts_path / safe_name
        artifact_path.write_text(content, encoding="utf-8")
        return str(artifact_path)

    def list_artifacts(self) -> list[dict]:
        """List all artifact files."""
        results = []
        for p in sorted(self.artifacts_path.iterdir()):
            if p.is_file():
                results.append({
                    "filename": p.name,
                    "size_bytes": p.stat().st_size,
                    "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                    "path": str(p),
                })
        return results


# ─── Workspace Manager ────────────────────────────────────────────────────────

class WorkspaceManager:
    """
    Manages all workspace sessions.
    Sessions are stored as human-readable slug folders under WORKSPACE_ROOT.
    """

    def __init__(self) -> None:
        WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    def _existing_slugs(self) -> set[str]:
        return {p.name for p in WORKSPACE_ROOT.iterdir() if p.is_dir() and not p.name.startswith(".")}

    def create(self, title: str = "New Session") -> WorkspaceSession:
        """Create a new workspace session with a human-readable slug."""
        import uuid
        existing = self._existing_slugs()
        slug = _unique_slug(title, existing)
        session_id = str(uuid.uuid4())
        ws = WorkspaceSession(slug=slug, session_id=session_id, title=title)
        # Write initial context.md
        ws.write_context(
            f"# {title}\n\n"
            f"**Session ID:** `{session_id}`  \n"
            f"**Created:** {ws.created_at}  \n"
            f"**Workspace:** `workspace/{slug}/`\n\n"
            f"---\n\n"
            f"*This file is your session's living context. The agent can read and update it.*\n"
        )
        ws.save()
        return ws

    def load(self, slug_or_id: str) -> Optional[WorkspaceSession]:
        """Load a session by slug or session_id prefix."""
        # Try direct slug first
        ws = WorkspaceSession.load(slug_or_id)
        if ws:
            return ws
        # Try matching by session_id prefix
        for slug in self._existing_slugs():
            ws = WorkspaceSession.load(slug)
            if ws and ws.session_id.startswith(slug_or_id):
                return ws
        return None

    def list_all(self) -> list[dict]:
        """List all workspace sessions, sorted by last modified."""
        sessions = []
        for slug in self._existing_slugs():
            meta_path = WORKSPACE_ROOT / slug / "session.json"
            if not meta_path.exists():
                continue
            try:
                with open(meta_path, encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append({
                    "slug":          data.get("slug", slug),
                    "session_id":    data.get("session_id", ""),
                    "title":         data.get("title", "Untitled"),
                    "created_at":    data.get("created_at", ""),
                    "updated_at":    data.get("updated_at", ""),
                    "message_count": len(data.get("messages", [])),
                    "path":          str(WORKSPACE_ROOT / slug),
                })
            except Exception:
                pass
        return sorted(sessions, key=lambda s: s.get("updated_at", ""), reverse=True)

    def rename(self, slug: str, new_title: str) -> Optional[WorkspaceSession]:
        """Rename a session (updates title + renames folder if slug changes)."""
        ws = WorkspaceSession.load(slug)
        if not ws:
            return None
        existing = self._existing_slugs() - {slug}
        new_slug = _unique_slug(new_title, existing)
        ws.title = new_title
        if new_slug != slug:
            new_path = WORKSPACE_ROOT / new_slug
            shutil.move(str(ws.path), str(new_path))
            ws.slug = new_slug
            ws._dir = new_path
        ws.save()
        return ws

    def delete(self, slug: str) -> bool:
        """Delete a workspace session folder."""
        path = WORKSPACE_ROOT / slug
        if path.exists():
            shutil.rmtree(path)
            return True
        return False

    def clear_all(self) -> int:
        """Delete all workspace session folders. Returns count of deleted sessions."""
        count = 0
        for slug in self._existing_slugs():
            if self.delete(slug):
                count += 1
        return count

    def search(self, query: str) -> list[dict]:
        """Full-text search across all session context files and notes."""
        query_lower = query.lower()
        results = []
        for slug in self._existing_slugs():
            ws = WorkspaceSession.load(slug)
            if not ws:
                continue
            hits = []
            # Search context.md
            ctx = ws.read_context()
            if query_lower in ctx.lower():
                hits.append("context.md")
            # Search notes
            for note_path in ws.notes_path.glob("*.md"):
                if query_lower in note_path.read_text(encoding="utf-8", errors="ignore").lower():
                    hits.append(f"notes/{note_path.name}")
            # Search scratchpad
            for blob_path in ws.scratchpad_path.glob("*.txt"):
                if query_lower in blob_path.read_text(encoding="utf-8", errors="ignore").lower():
                    hits.append(f"scratchpad/{blob_path.name}")
            if hits:
                results.append({
                    "slug":    slug,
                    "title":   ws.title,
                    "matches": hits,
                    "path":    str(ws.path),
                })
        return results


# ─── Singleton ────────────────────────────────────────────────────────────────
workspace_manager = WorkspaceManager()
