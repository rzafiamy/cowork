"""
🔌 External Tools Aggregator
Aggregates modular tool implementations from per-service files.
"""

from typing import Any, Optional
from .utils import _env

# Import service modules
from . import youtube
from . import search
from . import web
from . import news
from . import code
# Note: In weather.py I didn't include the OPENWEATHER prefix but let's keep it consistent
from . import weather
from . import media
from . import knowledge
from . import communication
from . import google
from . import social

# Re-export key functions for tools/__init__.py or manager.py if needed
# But better to aggregate them here.

EXTERNAL_TOOLS: list[dict] = []
EXTERNAL_TOOL_HANDLERS: dict[str, Any] = {}

# Aggregate from all modules
_modules = [
    youtube, search, web, news, code, weather, 
    media, knowledge, communication, google, social
]

for mod in _modules:
    # Add tools schemas
    EXTERNAL_TOOLS.extend(mod.TOOLS)
    # Add handlers
    for tool_schema in mod.TOOLS:
        name = tool_schema["function"]["name"]
        handler = getattr(mod, name, None)
        if handler:
            EXTERNAL_TOOL_HANDLERS[name] = handler

# Maintain KEY_REQUIREMENTS for get_available_external_tools
KEY_REQUIREMENTS: dict[str, str | list[str] | None] = {
    "youtube_search":       "YOUTUBE_API_KEY",
    "youtube_transcript":   None,
    "youtube_metadata":     "YOUTUBE_API_KEY",
    "google_cse_search":    "GOOGLE_API_KEY",
    "google_search":        ["GOOGLE_API_KEY", "SERPAPI_KEY"],
    "brave_search":         "BRAVE_SEARCH_API_KEY",
    "firecrawl_scrape":     "FIRECRAWL_API_KEY",
    "firecrawl_crawl":      "FIRECRAWL_API_KEY",
    "newsapi_headlines":    "NEWSAPI_KEY",
    "github_search":        None,
    "openweather_current":  "OPENWEATHER_API_KEY",
    "openweather_forecast": "OPENWEATHER_API_KEY",
    "tmdb_search":          "TMDB_API_KEY",
    "tmdb_details":         "TMDB_API_KEY",
    "wikipedia_search":     None,
    "wikipedia_article":    None,
    "smtp_send_email":      "SMTP_PASS",
    "telegram_send_message":"TELEGRAM_BOT_TOKEN",
    "slack_send_message":   "SLACK_BOT_TOKEN",
    "twitter_post_tweet":   "TWITTER_BEARER_TOKEN",
    "google_calendar_events":      None,
    "google_calendar_create_event":None,
    "google_drive_search":         None,
    "google_drive_upload_text":    None,
    "gmail_send_email":            "GOOGLE_API_KEY",
    "linkedin_search":      None,
    "whatsapp_send_message":None,
}

def get_available_external_tools() -> list[dict]:
    """Return only the external tools whose required API keys are configured."""
    available = []
    for tool in EXTERNAL_TOOLS:
        name = tool["function"]["name"]
        required = KEY_REQUIREMENTS.get(name)
        
        is_available = False
        if required is None:
            is_available = True
        elif isinstance(required, list):
            is_available = any(_env(k) for k in required)
        else:
            is_available = bool(_env(required))

        if is_available:
            available.append(tool)
    return available

# Re-export specific implementations that might be used elsewhere (like openweather_current in connectors.py)
openweather_current = weather.openweather_current
