"""
📍 Centralized Paths
"""

from pathlib import Path

import os
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR  = Path(os.getenv("CONFIG_DIR", "~/.cowork")).expanduser().resolve()
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"
SCRATCHPAD_DIR = CONFIG_DIR / "scratchpad"
WORKSPACE_ROOT = CONFIG_DIR / "workspace"
JOBS_FILE        = CONFIG_DIR / "jobs.json"
TOKENS_FILE      = CONFIG_DIR / "tokens.json"
AI_PROFILES_FILE = CONFIG_DIR / "ai_profiles.json"
FIREWALL_FILE    = CONFIG_DIR / "firewall.yaml"
ACL_FILE         = CONFIG_DIR / "acl.yaml"
ACL_LOG_FILE     = CONFIG_DIR / "acl.log"
