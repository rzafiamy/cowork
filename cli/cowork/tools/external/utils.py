"""
🛠️ External Tool Utilities
Shared helpers for API integrations (HTTP, caching, keys).
"""

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

# ─── Key Helpers ──────────────────────────────────────────────────────────────

def _env(key: str) -> Optional[str]:
    """Return env var value or None."""
    return os.environ.get(key) or None

def _missing_key(tool_name: str, env_var: str) -> str:
    return (
        f"❌ Tool '{tool_name}' requires the `{env_var}` environment variable.\n"
        f"   Set it in your .env file and restart Cowork."
    )

# ─── Disk-Based TTL Cache ─────────────────────────────────────────────────────

_CACHE_DIR = Path.home() / ".cowork" / "api_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_TTL_SEARCH   = 3600
_TTL_NEWS     = 1800
_TTL_WEATHER  = 600
_TTL_METADATA = 86400
_TTL_WIKI     = 86400 * 7
_TTL_GITHUB   = 3600
_TTL_DEFAULT  = 3600

def _cache_key(url: str, payload: dict | None = None) -> str:
    raw = url + (json.dumps(payload, sort_keys=True) if payload else "")
    return hashlib.sha256(raw.encode()).hexdigest()

def _cache_get(key: str, ttl: int) -> dict | str | None:
    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data["ts"] < ttl:
            return data["value"]
    except Exception:
        pass
    return None

def _cache_set(key: str, value: dict | str) -> None:
    path = _CACHE_DIR / f"{key}.json"
    try:
        path.write_text(
            json.dumps({"ts": time.time(), "value": value}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass

def _http_get(
    url: str,
    headers: dict | None = None,
    timeout: int = 15,
    ttl: int = _TTL_DEFAULT,
) -> dict | str:
    ck = _cache_key(url)
    cached = _cache_get(ck, ttl)
    if cached is not None:
        return cached
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "CoworkCLI/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    try:
        result: dict | str = json.loads(raw)
    except json.JSONDecodeError:
        result = raw
    _cache_set(ck, result)
    return result

def _http_post(
    url: str,
    payload: dict,
    headers: dict | None = None,
    timeout: int = 20,
    ttl: int = _TTL_DEFAULT,
) -> dict | str:
    ck = _cache_key(url, payload)
    cached = _cache_get(ck, ttl)
    if cached is not None:
        return cached
    body = json.dumps(payload).encode("utf-8")
    default_headers = {
        "Content-Type": "application/json",
        "User-Agent": "CoworkCLI/1.0",
    }
    if headers:
        default_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=default_headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    try:
        result: dict | str = json.loads(raw)
    except json.JSONDecodeError:
        result = raw
    _cache_set(ck, result)
    return result
