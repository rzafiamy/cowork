"""
💾 Configuration & Persistence Layer
Handles .env loading, config file (TOML-like JSON), and session state.
"""

import json
import os
import uuid
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

# ─── Paths ────────────────────────────────────────────────────────────────────
CONFIG_DIR  = Path.home() / ".cowork"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"
SCRATCHPAD_DIR = CONFIG_DIR / "scratchpad"
JOBS_FILE        = CONFIG_DIR / "jobs.json"
TOKENS_FILE      = CONFIG_DIR / "tokens.json"
AI_PROFILES_FILE = CONFIG_DIR / "ai_profiles.json"
FIREWALL_FILE    = CONFIG_DIR / "firewall.yaml"

def _ensure_dirs() -> None:
    CONFIG_DIR.mkdir(exist_ok=True)
    SESSIONS_DIR.mkdir(exist_ok=True)
    SCRATCHPAD_DIR.mkdir(exist_ok=True)

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
    "temperature_router":         0.0,
    "temperature_compress":       0.1,
    "temperature_agent":          0.4,
    "temperature_chat":           0.7,
    "search_freshness":           "1wk",
    "stream":                     True,
    "show_trace":                 False,
    "theme":                      "dark",
}

# ─── Config Manager ───────────────────────────────────────────────────────────
class ConfigManager:
    """Manages persistent configuration stored in ~/.cowork/config.json."""

    def __init__(self) -> None:
        load_dotenv()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        # Merge defaults (don't overwrite existing)
        for k, v in DEFAULT_CONFIG.items():
            self._data.setdefault(k, v)
        # Override from environment
        if os.getenv("OPENAI_API_KEY"):
            self._data["api_key"] = os.getenv("OPENAI_API_KEY", "")
        if os.getenv("COWORK_API_ENDPOINT"):
            self._data["api_endpoint"] = os.getenv("COWORK_API_ENDPOINT", "")
        if os.getenv("COWORK_MODEL"):
            self._data["model_text"] = os.getenv("COWORK_MODEL", "")
        # ── External Tool API Keys (loaded from .env, stored in memory only) ──
        _ext_keys = [
            "YOUTUBE_API_KEY",
            "GOOGLE_API_KEY",
            "GOOGLE_SEARCH_ENGINE_ID",
            "SERPAPI_KEY",
            "BRAVE_SEARCH_API_KEY",
            "FIRECRAWL_API_KEY",
            "NEWSAPI_KEY",
            "GITHUB_TOKEN",
            "OPENWEATHER_API_KEY",
            "TMDB_API_KEY",
            "TWITTER_BEARER_TOKEN",
        ]
        for _k in _ext_keys:
            val = os.getenv(_k)
            if val:
                self._data[_k] = val

    def save(self) -> None:
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

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
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at
        self.messages: list[dict] = []
        self.summary: str = ""
        self.triplets: list[dict] = []
        self.metadata: dict = {}

    def add_message(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        })
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
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
        s.created_at = data.get("created_at", s.created_at)
        s.updated_at = data.get("updated_at", s.updated_at)
        s.messages = data.get("messages", [])
        s.summary = data.get("summary", "")
        s.triplets = data.get("triplets", [])
        s.metadata = data.get("metadata", {})
        return s

    def save(self) -> None:
        path = SESSIONS_DIR / f"{self.session_id}.json"
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, session_id: str) -> Optional["Session"]:
        path = SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def list_all(cls) -> list[dict]:
        sessions = []
        for p in sorted(SESSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(p) as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data["session_id"],
                    "title": data.get("title", "Untitled"),
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


# ─── Scratchpad ───────────────────────────────────────────────────────────────
class Scratchpad:
    """
    Pass-by-Reference memory system.
    Stores large payloads on disk, returns lightweight ref:key pointers.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._dir = SCRATCHPAD_DIR / session_id
        self._dir.mkdir(exist_ok=True)
        self._index: dict[str, dict] = {}
        self._load_index()

    def _index_path(self) -> Path:
        return self._dir / "_index.json"

    def _load_index(self) -> None:
        p = self._index_path()
        if p.exists():
            with open(p) as f:
                self._index = json.load(f)

    def _save_index(self) -> None:
        with open(self._index_path(), "w") as f:
            json.dump(self._index, f, indent=2)

    def save(self, key: str, content: str, description: str = "") -> str:
        """Save content, return ref:key pointer."""
        ref_key = f"ref:{key}"
        path = self._dir / f"{key}.txt"
        path.write_text(content, encoding="utf-8")
        self._index[key] = {
            "key": key,
            "description": description,
            "size_chars": len(content),
            "saved_at": datetime.utcnow().isoformat(),
            "path": str(path),
        }
        self._save_index()
        return ref_key

    def get(self, key: str) -> Optional[str]:
        """Retrieve full content by key."""
        clean_key = key.replace("ref:", "")
        path = self._dir / f"{clean_key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
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
        self.created_at = datetime.utcnow().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.steps: int = 0
        self.tool_calls: int = 0
        self.categories: list[str] = []

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
            self._jobs[job_id].started_at = datetime.utcnow().isoformat()
            self._save()

    def complete(self, job_id: str, result: str) -> None:
        if job_id in self._jobs:
            j = self._jobs[job_id]
            j.status = JobStatus.COMPLETED
            j.result = result
            j.completed_at = datetime.utcnow().isoformat()
            self._save()

    def fail(self, job_id: str, error: str) -> None:
        if job_id in self._jobs:
            j = self._jobs[job_id]
            j.status = JobStatus.FAILED
            j.error = error
            j.completed_at = datetime.utcnow().isoformat()
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


# ─── Token Tracker ────────────────────────────────────────────────────────────

class TokenTracker:
    """
    Tracks cumulative token usage per (endpoint, model) pair.
    Persists to ~/.cowork/tokens.json.
    """

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
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat(),
            }
        entry = self._data[key]
        entry["prompt_tokens"]     += usage.get("prompt_tokens", 0)
        entry["completion_tokens"] += usage.get("completion_tokens", 0)
        entry["total_tokens"]      += usage.get("total_tokens", 0)
        entry["request_count"]     += 1
        entry["last_seen"]          = datetime.utcnow().isoformat()
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
        self.created_at = datetime.utcnow().isoformat()

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
        self._load()

    def _load(self) -> None:
        """Load rules from YAML. Create default if missing."""
        if not self.path.exists():
            self._create_default()
        
        try:
            with open(self.path, "r") as f:
                self._rules = yaml.safe_load(f) or {}
        except Exception:
            self._rules = {"policy": {"default_action": "allow"}}

    def _create_default(self) -> None:
        """Initialize firewall.yaml with safe defaults."""
        default_content = """# 🛡️ Cowork Tool Firewall
# Use this to control which tools can run and which require user confirmation.

# Default policy: allow, block, or ask
policy:
  default_action: allow

# Tools that ALWAYS require explicit user confirmation
tools:
  - name: gmail_send_email
    action: ask
    description: "Prevent sending unauthorized emails via Gmail"
  
  - name: smtp_send_email
    action: ask
    description: "Prevent sending unauthorized emails via SMTP"

  - name: google_calendar_create_event
    action: ask
    description: "Confirm adding new events to your calendar"

  - name: storage_write
    action: ask
    description: "Prevent overwriting local system files"

  - name: twitter_post_tweet
    action: ask
    description: "Prevent accidental public tweets"

  - name: google_drive_upload_text
    action: ask
    description: "Confirm uploading documents to Google Drive"

  - name: firecrawl_scrape
    action: ask
    description: "Confirm scraping external website content"

  - name: firecrawl_crawl
    action: ask
    description: "Confirm multi-page crawl of external website"

  - name: cron_schedule
    action: ask
    description: "Confirm scheduling a recurring or future task"

# Whitelist: If defined, ONLY these tools are allowed
# whitelist:
#   - calc
#   - get_time

# Blacklist: Tools that are strictly forbidden
blacklist: []

# Analysis: Tools that should be scrutinized (requires LLM reasoning in future)
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
            if rule.get("name") == tool_name:
                action = rule.get("action", FirewallAction.ALLOW)
                reason = rule.get("description", f"Rule for {tool_name}")
                return action, reason

        # 4. Fallback to default policy
        default_action = self._rules.get("policy", {}).get("default_action", FirewallAction.ALLOW)
        return default_action, "Default policy"

    def reload(self) -> None:
        self._load()
