"""
🎬 Media Tools
Implementations for TMDB (The Movie Database).
"""

import urllib.parse
from .utils import _env, _missing_key, _http_get, _TTL_METADATA

def tmdb_search(query: str, media_type: str = "multi") -> str:
    """Search for movies/TV shows on TMDB."""
    api_key = _env("TMDB_API_KEY")
    if not api_key: return _missing_key("tmdb_search", "TMDB_API_KEY")

    params = {"api_key": api_key, "query": query}
    url = f"https://api.themoviedb.org/3/search/{media_type}?{urllib.parse.urlencode(params)}"

    try:
        data = _http_get(url, ttl=_TTL_METADATA)
        results = data.get("results", [])
        lines = [f"🎬 **TMDB Search** — '{query}'\n"]
        for i, res in enumerate(results[:5], 1):
            lines.append(f"{i}. **{res.get('title') or res.get('name')}**\n   ID: {res.get('id')} | {res.get('overview')[:100]}...\n")
        return "\n".join(lines)
    except Exception as e:
        return f"TMDB search failed: {e}"

def tmdb_details(tmdb_id: int, media_type: str = "movie") -> str:
    """Get full details for a movie or TV show from TMDB."""
    api_key = _env("TMDB_API_KEY")
    if not api_key: return _missing_key("tmdb_details", "TMDB_API_KEY")

    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={api_key}"

    try:
        data = _http_get(url, ttl=_TTL_METADATA)
        return f"🎬 **{data.get('title') or data.get('name')}**\n\n{data.get('overview')}"
    except Exception as e:
        return f"TMDB details failed: {e}"

def tmdb_now_playing(region: str = "") -> str:
    """Get movies currently in theaters from TMDB."""
    api_key = _env("TMDB_API_KEY")
    if not api_key: return _missing_key("tmdb_now_playing", "TMDB_API_KEY")

    params = {"api_key": api_key, "language": "en-US", "page": 1}
    if region: params["region"] = region
    url = f"https://api.themoviedb.org/3/movie/now_playing?{urllib.parse.urlencode(params)}"

    try:
        data = _http_get(url, ttl=_TTL_METADATA)
        results = data.get("results", [])
        lines = [f"🎬 **TMDB Now Playing**\n"]
        for i, res in enumerate(results[:10], 1):
            date = res.get("release_date", "Unknown")
            lines.append(f"{i}. **{res.get('title')}** (Released: {date})\n   ID: {res.get('id')} | Rating: {res.get('vote_average')}\n   {res.get('overview')[:120]}...\n")
        return "\n".join(lines)
    except Exception as e:
        return f"TMDB now playing failed: {e}"

TOOLS = [
    {
        "category": "MEDIA_TOOLS",
        "type": "function",
        "function": {
            "name": "tmdb_search",
            "description": "Search for movies or TV shows on TMDB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "media_type": {"type": "string", "enum": ["movie", "tv", "multi"]},
                },
                "required": ["query"],
            },
        },
    },
    {
        "category": "MEDIA_TOOLS",
        "type": "function",
        "function": {
            "name": "tmdb_details",
            "description": "Get detailed info for a movie/TV show by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tmdb_id": {"type": "integer", "description": "TMDB ID"},
                    "media_type": {"type": "string", "enum": ["movie", "tv"]},
                },
                "required": ["tmdb_id"],
            },
        },
    },
    {
        "category": "MEDIA_TOOLS",
        "type": "function",
        "function": {
            "name": "tmdb_now_playing",
            "description": "Get a list of movies currently in the cinema/theaters (Now Playing).",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {"type": "string", "description": "Optional ISO 3166-1 country code (e.g. 'US', 'FR')"},
                },
            },
        },
    },
]
