"""
💾 Configuration & Persistence Layer
Handles .env loading, config file (TOML-like JSON), and session state.
"""

import json
import os
import re
import uuid
import fnmatch
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from .paths import (
    CONFIG_DIR, CONFIG_FILE, SESSIONS_DIR, SCRATCHPAD_DIR,
    WORKSPACE_ROOT, JOBS_FILE, TOKENS_FILE, AI_PROFILES_FILE, FIREWALL_FILE
)
from .acl import file_manager

def _ensure_dirs() -> None:
    CONFIG_DIR.mkdir(exist_ok=True)
    SESSIONS_DIR.mkdir(exist_ok=True)
    SCRATCHPAD_DIR.mkdir(exist_ok=True)
    WORKSPACE_ROOT.mkdir(exist_ok=True)

_ensure_dirs()

# ─── Default Config ───────────────────────────────────────────────────────────
DEFAULT_CONFIG: dict[str, Any] = {
    "api_endpoint":               "https://api.openai.com/v1",
    "api_key":                    "",
    "model_text":                 "gpt-4o-mini",
    "model_router":               "gpt-4o-mini",
    "model_compress":             "gpt-4o-mini",
    "embedding_model":            "text-embedding-3-small",
    "user_input_limit_tokens":    2000,
    "context_limit_tokens":       6000,
    "tool_output_limit_tokens":   1500,
    "max_steps":                  15,
    "max_tool_calls_per_step":    5,
    "max_total_tool_calls":       30,
    "idle_threshold_seconds":     900,
    "max_concurrent_jobs":        10,
    "decay_rate":                 0.02,
    "top_k_memories":             5,
    "memory_min_similarity":      0.2,
    "memory_min_weight":          0.015,
    "memory_topic_overlap_min":   1,
    "memory_high_similarity_bypass": 0.55,
    "memory_kg_limit_triplets":   100,
    "temperature_router":         0.0,
    "temperature_compress":       0.1,
    "temperature_agent":          0.4,
    "temperature_chat":           0.7,
    "request_delay_ms":           0,
    "max_retries":                5,
    "retry_base_delay":           2.0,
    "search_freshness":           "1wk",
    "auto_save_important_refs":   True,
    # ── Skills Runtime (Progressive Disclosure) ──────────────────────────────
    "skills_enabled":             True,
    "skills_paths":               [],
    "skills_router_min_score":    0.22,
    "skills_allow_category_expansion": False,
    "skills_max_metadata_skills": 64,
    "skills_instruction_max_chars": 20000,
    "skills_max_resources_per_activation": 3,
    "skills_resource_max_chars":  10000,
    "stream":                     True,
    "show_trace":                 False,
    "theme":                      "dark",
    # ── Multi-Modal Services ──────────────────────────────────────────────────
    # Vision / Image analysis
    "mm_vision_endpoint":         "",
    "mm_vision_model":            "",
    # Image generation
    "mm_image_endpoint":          "",
    "mm_image_model":             "",
    # Speech-to-Text (ASR / Whisper)
    "mm_asr_endpoint":            "",
    "mm_asr_model":               "",
    # Text-to-Speech (TTS)
    "mm_tts_endpoint":            "",
    "mm_tts_model":               "",
    "mm_tts_voice":               "",
}

SENSITIVE_KEYS = {
    "api_key",
    "YOUTUBE_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_SEARCH_ENGINE_ID",
    "GOOGLE_CREDENTIALS_FILE",
    "GOOGLE_OAUTH_CREDENTIALS_JSON",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_PROJECT_ID",
    "GOOGLE_OAUTH_REDIRECT_URI",
    "GOOGLE_TOKEN_FILE",
    "GOOGLE_TOKEN_JSON",
    "SERPAPI_KEY",
    "BRAVE_SEARCH_API_KEY",
    "FIRECRAWL_API_KEY",
    "NEWSAPI_KEY",
    "GITHUB_TOKEN",
    "OPENWEATHER_API_KEY",
    "TMDB_API_KEY",
    "TWITTER_BEARER_TOKEN",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASS",
    "TELEGRAM_BOT_TOKEN",
    "SLACK_BOT_TOKEN",
    # Multi-Modal service tokens
    "mm_vision_token",
    "mm_image_token",
    "mm_asr_token",
    "mm_tts_token",
}
_SENSITIVE_KEYS_CASEFOLD = {k.casefold() for k in SENSITIVE_KEYS}


def is_sensitive_key(key: str) -> bool:
    """Case-insensitive sensitive-key check used across config/display paths."""
    return key.casefold() in _SENSITIVE_KEYS_CASEFOLD

# ─── Config Manager ───────────────────────────────────────────────────────────
class ConfigManager:
    """Manages persistent configuration stored in ~/.cowork/config.json."""

    def __init__(self) -> None:
        load_dotenv()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if file_manager.exists(CONFIG_FILE):
            try:
                self._data = file_manager.read_json(CONFIG_FILE, reason="config load")

                # 🛡️ CLEANUP: Immediately purge and persist if sensitive keys leaked into config.json
                had_sensitive = any(is_sensitive_key(k) for k in self._data)
                if had_sensitive:
                    self._data = {k: v for k, v in self._data.items() if not is_sensitive_key(k)}
                    with open(CONFIG_FILE, "w") as f:
                        json.dump(self._data, f, indent=2)
                        
            except (json.JSONDecodeError, OSError):
                self._data = {}

        # Merge defaults (don't overwrite existing)
        for k, v in DEFAULT_CONFIG.items():
            self._data.setdefault(k, v)

        # Override from environment (Prioritize .env)
        if os.getenv("OPENAI_API_KEY"):
            self._data["api_key"] = os.getenv("OPENAI_API_KEY", "")
        if os.getenv("COWORK_API_ENDPOINT"):
            self._data["api_endpoint"] = os.getenv("COWORK_API_ENDPOINT", "")
        if os.getenv("COWORK_MODEL"):
            self._data["model_text"] = os.getenv("COWORK_MODEL", "")

        # ── Multi-Modal (MM) service overrides from environment ──
        for k in self._data:
            if k.startswith("mm_"):
                # Check both lowercase (config name) and uppercase (env convention)
                val = os.getenv(k) or os.getenv(k.upper())
                if val:
                    self._data[k] = val

        # ── External Tool API Keys (loaded from .env, kept in memory only) ──
        for _k in SENSITIVE_KEYS:
            if _k == "api_key": continue # Already handled or specifically mapped
            val = os.getenv(_k) or os.getenv(_k.upper())
            if val:
                self._data[_k] = val

    def save(self) -> None:
        """Saves configuration to disk, filtering out sensitive credentials."""
        # 🛡️ Filter sensitive keys before writing to file
        safe_data = {k: v for k, v in self._data.items() if not is_sensitive_key(k)}
        
        file_manager.write_json(CONFIG_FILE, safe_data, reason="config save")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    @property
    def api_key(self) -> str:
        return self._data.get("api_key", "")

    @property
    def api_endpoint(self) -> str:
        return self._data.get("api_endpoint", "https://api.openai.com/v1")

    @property
    def model_text(self) -> str:
        return self._data.get("model_text", "gpt-4o-mini")

    @property
    def model_router(self) -> str:
        return self._data.get("model_router", "gpt-4o-mini")

    @property
    def model_compress(self) -> str:
        return self._data.get("model_compress", "gpt-4o-mini")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_endpoint)


# ─── Session Manager ──────────────────────────────────────────────────────────
class Session:
    """Represents a single conversation session."""

    def __init__(self, session_id: Optional[str] = None, title: str = "Untitled Session") -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.title = title
        self.workspace_slug: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.messages: list[dict] = []
        self.summary: str = ""
        self.triplets: list[dict] = []
        self.metadata: dict = {}

    def add_message(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        })
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "workspace_slug": self.workspace_slug,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": self.messages,
            "summary": self.summary,
            "triplets": self.triplets,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        s = cls(session_id=data["session_id"], title=data.get("title", "Untitled"))
        s.workspace_slug = data.get("workspace_slug")
        s.created_at = data.get("created_at", s.created_at)
        s.updated_at = data.get("updated_at", s.updated_at)
        s.messages = data.get("messages", [])
        s.summary = data.get("summary", "")
        s.triplets = data.get("triplets", [])
        s.metadata = data.get("metadata", {})
        return s

    def save(self) -> None:
        path = SESSIONS_DIR / f"{self.session_id}.json"
        file_manager.write_json(path, self.to_dict(), reason="session save")

    @classmethod
    def load(cls, session_id: str) -> Optional["Session"]:
        path = SESSIONS_DIR / f"{session_id}.json"
        if not file_manager.exists(path):
            return None
        data = file_manager.read_json(path, reason="session load")
        return cls.from_dict(data)

    @classmethod
    def list_all(cls) -> list[dict]:
        """List all saved sessions with their titles and workspace slugs."""
        # Pre-scan workspace for session_id -> slug mapping
        slug_map = {}
        if WORKSPACE_ROOT.exists():
            for d in WORKSPACE_ROOT.iterdir():
                if d.is_dir() and not d.name.startswith("."):
                    meta_file = d / "session.json"
                    if meta_file.exists():
                        try:
                            with open(meta_file, encoding="utf-8") as f:
                                meta_data = json.load(f)
                            sid = meta_data.get("session_id")
                            if sid:
                                slug_map[sid] = d.name
                        except Exception:
                            pass

        sessions = []
        for p in sorted(SESSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(p) as f:
                    data = json.load(f)
                sid = data["session_id"]
                sessions.append({
                    "session_id": sid,
                    "title": data.get("title", "Untitled"),
                    "slug": slug_map.get(sid, data.get("workspace_slug", "")),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception:
                pass
        return sessions

    def get_chat_messages(self) -> list[dict]:
        """Return messages in OpenAI chat format (role + content only)."""
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def delete(self) -> bool:
        """Permanently delete this session file and its linked workspace."""
        path = SESSIONS_DIR / f"{self.session_id}.json"
        res = False
        if path.exists():
            path.unlink()
            res = True
        
        # Cascade delete workspace folder
        if self.workspace_slug:
            ws_path = WORKSPACE_ROOT / self.workspace_slug
            if ws_path.exists():
                import shutil
                shutil.rmtree(ws_path)
        else:
            # Fallback: find by session_id in workspace folders
            if WORKSPACE_ROOT.exists():
                import shutil
                for d in WORKSPACE_ROOT.iterdir():
                    if d.is_dir() and not d.name.startswith("."):
                        meta_file = d / "session.json"
                        if meta_file.exists():
                            try:
                                with open(meta_file, encoding="utf-8") as f:
                                    meta_data = json.load(f)
                                if meta_data.get("session_id") == self.session_id:
                                    shutil.rmtree(d)
                                    break
                            except Exception:
                                pass
        return res

    def get_sandwich_content(self, max_chars: int = 1200) -> str:
        """Return a sandwich of session messages (start and end)."""
        if not self.messages:
            return ""
        
        # Combine all messages into a single string
        lines = []
        for m in self.messages:
            content = str(m.get("content", ""))
            lines.append(f"{m.get('role', 'user')}: {content}")
        
        full_text = "\n".join(lines)
        if len(full_text) <= max_chars:
            return full_text
        
        half = max_chars // 2
        return f"{full_text[:half]}\n\n... [SANDWICHED] ...\n\n{full_text[-half:]}"

    def match(self, pattern: str, fields: Optional[list[str]] = None) -> bool:
        """
        Check if the session matches the given regex pattern in specified fields.
        If fields is None, checks title, summary, and all message contents.
        """
        import re
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return False

        if fields is None:
            fields = ["title", "summary", "content"]

        if "title" in fields and regex.search(self.title):
            return True
        
        if "summary" in fields and regex.search(self.summary):
            return True
        
        if "content" in fields:
            for m in self.messages:
                content = str(m.get("content", ""))
                if regex.search(content):
                    return True
        
        if "triplets" in fields:
            for t in self.triplets:
                t_str = f"{t.get('subject', '')} {t.get('predicate', '')} {t.get('object', '')}"
                if regex.search(t_str):
                    return True

        if "id" in fields and regex.search(self.session_id):
            return True

        return False

    @classmethod
    def clean_empty(cls) -> int:
        """Permanently delete all sessions with zero messages and their workspaces. Returns count of deleted."""
        count = 0
        for p in SESSIONS_DIR.glob("*.json"):
            try:
                with open(p) as f:
                    data = json.load(f)
                if not data.get("messages") or len(data.get("messages", [])) == 0:
                    # Load and use the instance delete() to trigger cascade
                    s = cls.from_dict(data)
                    s.delete()
                    count += 1
            except Exception:
                pass
        return count


# ─── Scratchpad ───────────────────────────────────────────────────────────────
class Scratchpad:
    """
    Pass-by-Reference memory system.
    Stores large payloads on disk, returns lightweight ref:key pointers.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._dir = SCRATCHPAD_DIR / session_id
        # Prefer per-session workspace scratchpad when available.
        try:
            from .workspace import workspace_manager
            ws = workspace_manager.get_by_session_id(session_id)
            if ws:
                self._dir = ws.scratchpad_path
        except Exception:
            pass
        self._dir.mkdir(exist_ok=True)
        self._index: dict[str, dict] = {}
        self._load_index()

    def _index_path(self) -> Path:
        return self._dir / "_index.json"

    def _load_index(self) -> None:
        p = self._index_path()
        if file_manager.exists(p):
            self._index = file_manager.read_json(p, reason="scratchpad index load")

    def _save_index(self) -> None:
        file_manager.write_json(self._index_path(), self._index, reason="scratchpad index save")

    def save(self, key: str, content: str, description: str = "") -> str:
        """Save content, return ref:key pointer."""
        from pathlib import Path
        safe_key = Path(key).name
        ref_key = f"ref:{safe_key}"
        path = self._dir / f"{safe_key}.txt"
        file_manager.write_text(path, content, reason=f"scratchpad save key={safe_key}")
        self._index[safe_key] = {
            "key": safe_key,
            "description": description,
            "size_chars": len(content),
            "saved_at": datetime.now().isoformat(),
            "path": str(path),
        }
        self._save_index()
        return ref_key

    def get(self, key: str) -> Optional[str]:
        """Retrieve full content by key."""
        from pathlib import Path
        clean_key = Path(key.replace("ref:", "")).name
        path = self._dir / f"{clean_key}.txt"
        if file_manager.exists(path):
            return file_manager.read_text(path, reason=f"scratchpad get key={clean_key}")
        return None

    def read_chunk(self, key: str, chunk_index: int = 0, chunk_size: int = 2000) -> Optional[str]:
        """Read a specific chunk of stored content."""
        content = self.get(key)
        if content is None:
            return None
        start = chunk_index * chunk_size
        end = start + chunk_size
        chunk = content[start:end]
        total_chunks = (len(content) + chunk_size - 1) // chunk_size
        return f"[Chunk {chunk_index + 1}/{total_chunks}]\n{chunk}"

    def list_all(self) -> list[dict]:
        return list(self._index.values())

    def search(self, query: str) -> list[dict]:
        """Simple text search across stored items."""
        results = []
        query_lower = query.lower()
        for key, meta in self._index.items():
            content = self.get(key) or ""
            if query_lower in content.lower() or query_lower in meta.get("description", "").lower():
                results.append({**meta, "preview": content[:200]})
        return results

    def resolve_refs(self, text: str) -> str:
        """Replace ref:key patterns in text with actual content."""
        import re
        def replacer(m: re.Match) -> str:
            key = m.group(1)
            content = self.get(key)
            return content if content else m.group(0)
        return re.sub(r"ref:(\w+)", replacer, text)

    def sandwich_preview(self, content: str, head_pct: float = 0.2, tail_pct: float = 0.2) -> str:
        """Generate a sandwich preview of large content."""
        n = len(content)
        head_end = int(n * head_pct)
        tail_start = int(n * (1 - tail_pct))
        head = content[:head_end]
        tail = content[tail_start:]
        return f"{head}\n\n... ✂️ [Content Offloaded to Scratchpad] ...\n\n{tail}"

    def purge(self) -> None:
        """Remove all scratchpad data for this session."""
        import shutil
        shutil.rmtree(self._dir, ignore_errors=True)
        self._dir.mkdir(exist_ok=True)
        self._index = {}


# ─── Job Manager ─────────────────────────────────────────────────────────────
class JobStatus:
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class AgentJob:
    """Represents a single agent execution job."""

    def __init__(self, job_id: Optional[str] = None, session_id: str = "", prompt: str = "") -> None:
        self.job_id = job_id or str(uuid.uuid4())[:8]
        self.session_id = session_id
        self.prompt = prompt
        self.status = JobStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.steps: int = 0
        self.tool_calls: int = 0
        self.categories: list[str] = []
        self.tool_calls_list: list[dict] = []
        self.trace_path: str = ""
        self.skill_name: Optional[str] = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "AgentJob":
        j = cls()
        j.__dict__.update(data)
        return j


class JobManager:
    """
    The Sentinel: Manages concurrent agent jobs with persistence.
    Enforces the 10-job global concurrency limit.
    """

    def __init__(self, max_jobs: int = 10) -> None:
        self.max_jobs = max_jobs
        self._jobs: dict[str, AgentJob] = {}
        self._load()

    def _load(self) -> None:
        if JOBS_FILE.exists():
            try:
                with open(JOBS_FILE) as f:
                    data = json.load(f)
                for jd in data.values():
                    j = AgentJob.from_dict(jd)
                    # Mark ghost jobs as failed
                    if j.status == JobStatus.RUNNING:
                        j.status = JobStatus.FAILED
                        j.error = "Ghost job: process was interrupted"
                    self._jobs[j.job_id] = j
            except Exception:
                self._jobs = {}

    def _save(self) -> None:
        with open(JOBS_FILE, "w") as f:
            json.dump({k: v.to_dict() for k, v in self._jobs.items()}, f, indent=2)

    def active_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING)

    def can_start(self) -> bool:
        return self.active_count() < self.max_jobs

    def register(self, job: AgentJob) -> bool:
        if not self.can_start():
            return False
        self._jobs[job.job_id] = job
        self._save()
        return True

    def start(self, job_id: str) -> None:
        if job_id in self._jobs:
            self._jobs[job_id].status = JobStatus.RUNNING
            self._jobs[job_id].started_at = datetime.now().isoformat()
            self._save()

    def complete(self, job_id: str, result: str) -> None:
        if job_id in self._jobs:
            j = self._jobs[job_id]
            j.status = JobStatus.COMPLETED
            j.result = result
            j.completed_at = datetime.now().isoformat()
            self._save()

    def fail(self, job_id: str, error: str) -> None:
        if job_id in self._jobs:
            j = self._jobs[job_id]
            j.status = JobStatus.FAILED
            j.error = error
            j.completed_at = datetime.now().isoformat()
            self._save()

    def get_ghost_jobs(self) -> list[AgentJob]:
        return [j for j in self._jobs.values() if j.status == JobStatus.FAILED and "Ghost job" in (j.error or "")]

    def list_recent(self, limit: int = 20) -> list[AgentJob]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def cleanup_completed(self, keep: int = 50) -> None:
        completed = [j for j in self._jobs.values() if j.status in (JobStatus.COMPLETED, JobStatus.FAILED)]
        completed.sort(key=lambda j: j.created_at, reverse=True)
        to_remove = completed[keep:]
        for j in to_remove:
            del self._jobs[j.job_id]
        self._save()

    def clear_all(self) -> None:
        """Wipe all jobs from history."""
        self._jobs = {}
        self._save()

    def get_job(self, job_id: str) -> Optional[AgentJob]:
        """Retrieve a job by its full or partial ID."""
        if job_id in self._jobs:
            return self._jobs[job_id]
        # Partial match
        matches = [j for j in self._jobs.values() if j.job_id.startswith(job_id)]
        return matches[0] if len(matches) == 1 else None


# ─── Token Tracker ────────────────────────────────────────────────────────────

class TokenTracker:
    """
    Tracks cumulative token usage per (endpoint, model) pair.
    Persists to ~/.cowork/tokens.json.
    """

    def finish(self) -> None:
        self.end_time = time.time()
        # Extract all tool calls from steps for easy persistence
        self.all_tool_calls_executed = []
        for s in self.steps:
            if s["type"] == "tool_calls" and "tools" in s:
                # 'tools' in trace.steps is just names, but we want more
                pass
            if s["type"] == "tool_execution_result":
                self.all_tool_calls_executed.append({
                    "name": s["name"],
                    "args": s["args"],
                    "status": "success" if "[TOOL ERROR]" not in s["result"] else "error"
                })
    def __init__(self) -> None:
        self._data: dict[str, dict] = {}  # key: "endpoint|model"
        self._load()

    def _load(self) -> None:
        if TOKENS_FILE.exists():
            try:
                with open(TOKENS_FILE) as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        try:
            with open(TOKENS_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass

    def _key(self, endpoint: str, model: str) -> str:
        return f"{endpoint.rstrip('/')}|{model}"

    def record(self, endpoint: str, model: str, usage: dict) -> None:
        """
        Record token usage from an API response's usage dict.
        usage = {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        """
        if not usage:
            return
        key = self._key(endpoint, model)
        if key not in self._data:
            self._data[key] = {
                "endpoint": endpoint.rstrip("/"),
                "model": model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "request_count": 0,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            }
        entry = self._data[key]
        entry["prompt_tokens"]     += usage.get("prompt_tokens", 0)
        entry["completion_tokens"] += usage.get("completion_tokens", 0)
        entry["total_tokens"]      += usage.get("total_tokens", 0)
        entry["request_count"]     += 1
        entry["last_seen"]          = datetime.now().isoformat()
        self._save()

    def get_all(self) -> list[dict]:
        """Return all tracked entries sorted by total tokens descending."""
        return sorted(self._data.values(), key=lambda x: x["total_tokens"], reverse=True)

    def get_totals(self) -> dict:
        """Return aggregate totals across all models."""
        totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "request_count": 0}
        for entry in self._data.values():
            for k in totals:
                totals[k] += entry.get(k, 0)
        return totals

    def reset(self) -> None:
        """Clear all token usage stats."""
        self._data = {}
        self._save()


# ─── AI Profile Manager ───────────────────────────────────────────────────────

class AIProfile:
    """Represents a named AI endpoint + model configuration."""

    def __init__(
        self,
        name: str,
        endpoint: str,
        model: str,
        api_key: str = "",
        description: str = "",
    ) -> None:
        self.name = name
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.description = description
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "model": self.model,
            "api_key": self.api_key,
            "description": self.description,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AIProfile":
        p = cls(
            name=data["name"],
            endpoint=data["endpoint"],
            model=data["model"],
            api_key=data.get("api_key", ""),
            description=data.get("description", ""),
        )
        p.created_at = data.get("created_at", p.created_at)
        return p


class AIProfileManager:
    """
    Manages multiple named AI profiles (endpoint + model + key).
    Persists to ~/.cowork/ai_profiles.json.
    Supports add, remove, list, and switch operations.
    """

    def __init__(self, config: "ConfigManager") -> None:
        self.config = config
        self._profiles: dict[str, AIProfile] = {}
        self._active: Optional[str] = None
        self._load()

    def _load(self) -> None:
        if AI_PROFILES_FILE.exists():
            try:
                with open(AI_PROFILES_FILE) as f:
                    raw = json.load(f)
                self._profiles = {
                    name: AIProfile.from_dict(data)
                    for name, data in raw.get("profiles", {}).items()
                }
                self._active = raw.get("active")
            except (json.JSONDecodeError, OSError, KeyError):
                self._profiles = {}
                self._active = None

    def _save(self) -> None:
        try:
            with open(AI_PROFILES_FILE, "w") as f:
                json.dump({
                    "profiles": {name: p.to_dict() for name, p in self._profiles.items()},
                    "active": self._active,
                }, f, indent=2)
        except OSError:
            pass

    def add(
        self,
        name: str,
        endpoint: str,
        model: str,
        api_key: str = "",
        description: str = "",
    ) -> AIProfile:
        """Add or update a named profile."""
        profile = AIProfile(name=name, endpoint=endpoint, model=model, api_key=api_key, description=description)
        self._profiles[name] = profile
        self._save()
        return profile

    def remove(self, name: str) -> bool:
        """Remove a profile by name. Returns True if removed."""
        if name in self._profiles:
            del self._profiles[name]
            if self._active == name:
                self._active = None
            self._save()
            return True
        return False

    def switch(self, name: str) -> Optional[AIProfile]:
        """
        Switch to a named profile. Updates the live ConfigManager.
        Returns the profile if found, else None.
        """
        if name not in self._profiles:
            return None
        profile = self._profiles[name]
        self._active = name
        self._save()
        # Apply to live config
        self.config.set("api_endpoint", profile.endpoint)
        self.config.set("model_text", profile.model)
        self.config.set("model_router", profile.model)
        self.config.set("model_compress", profile.model)
        if profile.api_key:
            self.config.set("api_key", profile.api_key)
        return profile

    def list_all(self) -> list[dict]:
        """Return all profiles as dicts, marking the active one."""
        result = []
        for name, p in self._profiles.items():
            d = p.to_dict()
            d["active"] = (name == self._active)
            result.append(d)
        return sorted(result, key=lambda x: x["name"])

    def get_active(self) -> Optional[AIProfile]:
        if self._active and self._active in self._profiles:
            return self._profiles[self._active]
        return None

    def snapshot_current(self, config: "ConfigManager", name: str = "default") -> AIProfile:
        """Save the current config as a named profile."""
        return self.add(
            name=name,
            endpoint=config.api_endpoint,
            model=config.model_text,
            api_key=config.api_key,
            description="Saved from current config",
        )


# ─── Firewall Manager ─────────────────────────────────────────────────────────

class FirewallAction:
    ALLOW   = "allow"
    BLOCK   = "block"
    ASK     = "ask"
    ANALYZE = "analyze"  # Potential future use for AI scrutiny


class FirewallManager:
    """
    The Cowork Firewall: Protects the system from malicious or unexpected tool calls.
    Loads rules from ~/.cowork/firewall.yaml.
    """

    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self.config_dir = config_dir
        self.path = config_dir / "firewall.yaml"
        self._rules: dict[str, Any] = {}
        self.last_load_error: str = ""
        self._load()

    def _load(self) -> None:
        """Load rules from YAML. Create default if missing."""
        self.last_load_error = ""
        if not self.path.exists():
            self._create_default()
        
        try:
            with open(self.path, "r") as f:
                self._rules = yaml.safe_load(f) or {}
            if not isinstance(self._rules, dict):
                self.last_load_error = "Top-level YAML document must be an object/map."
                self._rules = {"policy": {"default_action": "ask"}}
                return

            # Basic shape validation so malformed structures fail fast.
            tools = self._rules.get("tools", [])
            blacklist = self._rules.get("blacklist", [])
            whitelist = self._rules.get("whitelist", None)
            policy = self._rules.get("policy", {})
            if not isinstance(tools, list):
                self.last_load_error = "Field 'tools' must be a list."
            elif not isinstance(blacklist, list):
                self.last_load_error = "Field 'blacklist' must be a list."
            elif whitelist is not None and not isinstance(whitelist, list):
                self.last_load_error = "Field 'whitelist' must be a list when set."
            elif policy is not None and not isinstance(policy, dict):
                self.last_load_error = "Field 'policy' must be an object/map."

            if self.last_load_error:
                self._rules = {"policy": {"default_action": "ask"}}
                return
        except Exception as e:
            # Fail-closed on invalid firewall config
            self.last_load_error = f"YAML parse error in firewall.yaml: {e}"
            self._rules = {"policy": {"default_action": "ask"}}

    def is_integrity_ok(self) -> tuple[bool, str]:
        """Return whether firewall file loaded cleanly and passed basic schema checks."""
        if self.last_load_error:
            return False, self.last_load_error
        return True, ""

    def _normalize_action(self, action: Any) -> str:
        """Normalize firewall action; unknown values fail-closed to 'ask'."""
        a = str(action or "").strip().lower()
        if a in {FirewallAction.ALLOW, FirewallAction.BLOCK, FirewallAction.ASK, FirewallAction.ANALYZE}:
            return a
        return FirewallAction.ASK

    def _create_default(self) -> None:
        """Initialize firewall.yaml with safe defaults."""
        default_content = """# 🛡️  Cowork Tool Firewall
# Controls which tools run automatically and which require user confirmation.
# Actions: allow | ask | block
# Patterns: exact name OR fnmatch wildcard (e.g. "git_*", "*_send_*")

policy:
  default_action: allow   # Change to "ask" for maximum safety

tools:

  # ── 📧 Email / Messaging (irreversible external side-effects) ─────────────
  - name: gmail_send_email
    action: ask
    description: "Confirm before sending email via Gmail"

  - name: smtp_send_email
    action: ask
    description: "Confirm before sending email via SMTP"
    rules:
      - field: recipient
        regex: "^.*@(gmail\\.com|outlook\\.com|yahoo\\.com|hotmail\\.com)$"
        action: ask
        description: "Always confirm for common public mail providers"

  - name: telegram_send_message
    action: ask
    description: "Confirm before sending Telegram message"

  - name: slack_send_message
    action: ask
    description: "Confirm before posting to Slack"

  - name: whatsapp_send_message
    action: ask
    description: "Confirm before sending WhatsApp message"

  - name: twitter_post_tweet
    action: ask
    description: "Confirm before posting a public tweet"

  # ── 💻 Shell / Code Execution (highest risk — can run any command) ────────
  - name: codebase_bash
    action: ask
    description: "Confirm before executing shell commands on the system"

  # ── 📁 File System Writes (can overwrite / destroy data) ─────────────────
  - name: codebase_write_file
    action: ask
    description: "Confirm before writing/overwriting a file in the codebase"

  - name: workspace_write
    action: ask
    description: "Confirm before writing a file to the workspace"

  - name: storage_write
    action: ask
    description: "Confirm before writing to local storage paths"

  # ── 🔀 Git Mutations (modify or publish repository state) ─────────────────
  - name: git_push
    action: ask
    description: "Confirm before pushing commits to a remote repository"

  - name: git_commit
    action: ask
    description: "Confirm before creating a commit"

  - name: git_clone
    action: ask
    description: "Confirm before cloning a repository (bandwidth + disk)"

  # ── 📥 Downloads (bandwidth + disk cost, copyright risk) ─────────────────
  - name: youtube_download
    action: ask
    description: "Confirm before downloading YouTube video/audio (bandwidth + copyright)"

  - name: web_download_file
    action: ask
    description: "Confirm before downloading a file from the internet"

  # ── 🎨 API-Cost Multimodal (each call costs money) ───────────────────────
  - name: image_generate
    action: ask
    description: "Confirm before generating an image (costs API credits)"

  - name: speech_to_text
    action: ask
    description: "Confirm before transcribing audio (costs API credits)"

  - name: text_to_speech
    action: ask
    description: "Confirm before generating speech audio (costs API credits)"

  - name: vision_analyze
    action: ask
    description: "Confirm before sending an image for vision analysis (costs API credits)"

  # ── 📅 Calendar / Drive (external calendar/document mutations) ────────────
  - name: google_calendar_create_event
    action: ask
    description: "Confirm adding new events to Google Calendar"

  - name: google_calendar_delete_event
    action: ask
    description: "Confirm before deleting a calendar event"

  - name: google_drive_upload_text
    action: ask
    description: "Confirm before uploading documents to Google Drive"

  # ── ⏱️  Scheduled Tasks (persistent background automation) ────────────────
  - name: cron_schedule
    action: ask
    description: "Confirm before scheduling a recurring or future task"

  - name: cron_delete
    action: ask
    description: "Confirm before deleting a scheduled job"

  # ── 🗄️  Databases & CMS (external data mutations) ────────────────────────
  - name: "supabase_*"
    action: ask
    description: "Confirm before modifying data in Supabase"

  - name: "nextcloud_*"
    action: ask
    description: "Confirm before modifying files or data in Nextcloud"

  - name: "airtable_*"
    action: ask
    description: "Confirm before modifying data in Airtable"

  - name: "notion_*"
    action: ask
    description: "Confirm before modifying data in Notion"

  # ── 🤝 Social & Professional (public posts) ──────────────────────────────
  - name: "linkedin_*"
    action: ask
    description: "Confirm before posting to LinkedIn"

  - name: "twitter_*"
    action: ask
    description: "Confirm before posting to Twitter/X"

# Blacklist: Tools that are strictly NEVER allowed
blacklist: []

# Whitelist: If set, ONLY these tools are permitted (leave commented for open access)
# whitelist:
#   - calc
#   - get_time
#   - wikipedia_search

# Analysis: Tools flagged for extra scrutiny (future LLM review integration)
analyze: []
"""
        self.path.write_text(default_content, encoding="utf-8")

    def check(self, tool_name: str, args: dict) -> tuple[str, str]:
        """
        Check if a tool call is allowed.
        Returns: (action, reason)
        Action is one of: allow, block, ask
        """
        # 1. Check blacklist
        blacklist = self._rules.get("blacklist", [])
        if tool_name in blacklist:
            return FirewallAction.BLOCK, f"Tool '{tool_name}' is blacklisted."

        # 2. Check whitelist (if not empty)
        whitelist = self._rules.get("whitelist")
        if whitelist and tool_name not in whitelist:
            return FirewallAction.BLOCK, f"Tool '{tool_name}' is not in the whitelist."

        # 3. Check specific tool rules
        tool_rules = self._rules.get("tools", [])
        for rule in tool_rules:
            rule_name = str(rule.get("name", "")).strip()
            if not rule_name:
                continue
            # Match exact name or wildcard pattern (e.g. "smtp_*", "*_send_*")
            matches = (rule_name == tool_name) or fnmatch.fnmatch(tool_name, rule_name)
            if matches:
                # Check argument rules if defined
                arg_rules = rule.get("rules", [])
                for arg_rule in arg_rules:
                    field = arg_rule.get("field")
                    pattern = arg_rule.get("regex")
                    if field in args and pattern:
                        try:
                            if re.search(pattern, str(args[field])):
                                action = self._normalize_action(arg_rule.get("action", rule.get("action", FirewallAction.ASK)))
                                reason = arg_rule.get("description", rule.get("description", f"Rule for {tool_name}"))
                                return action, reason
                        except Exception as e:
                            # If regex is invalid, we skip this rule or could block for safety
                            pass

                action = self._normalize_action(rule.get("action", FirewallAction.ASK))
                reason = rule.get("description", f"Rule for {tool_name}")
                return action, reason

        # 4. Fallback to default policy
        default_action = self._normalize_action(self._rules.get("policy", {}).get("default_action", FirewallAction.ASK))
        return default_action, "Default policy"

    def reload(self) -> None:
        self._load()
