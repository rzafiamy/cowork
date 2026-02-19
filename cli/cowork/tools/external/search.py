"""
🔍 Search Tools
Implementations for Google Search (CSE & SerpAPI) and Brave Search.
"""

import urllib.parse
from .utils import _env, _missing_key, _http_get, _TTL_SEARCH

def google_cse_search(
    query: str,
    num_results: int = 5,
    language: str = "en",
    date_restrict: str = "",
    site_search: str = "",
) -> str:
    """Search Google using the official Custom Search JSON API."""
    api_key = _env("GOOGLE_API_KEY")
    cx = _env("GOOGLE_SEARCH_ENGINE_ID")

    if not api_key: return _missing_key("google_cse_search", "GOOGLE_API_KEY")
    if not cx: return _missing_key("google_cse_search", "GOOGLE_SEARCH_ENGINE_ID")

    num_results = min(max(1, num_results), 10)
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": num_results,
        "hl": language,
    }
    if date_restrict: params["dateRestrict"] = date_restrict
    if site_search: params["siteSearch"] = site_search

    url = f"https://www.googleapis.com/customsearch/v1?{urllib.parse.urlencode(params)}"

    try:
        data = _http_get(url, ttl=_TTL_SEARCH)
        error = data.get("error")
        if error: return f"Google CSE error: {error.get('message')}"

        items = data.get("items", [])
        lines = [f"🔍 **Google Search Results** for: **{query}**\n"]
        if not items:
            lines.append("No results found.")
        else:
            for i, item in enumerate(items, 1):
                title = item.get("title", "Untitled")
                link = item.get("link", "")
                snippet = item.get("snippet", "").replace("\n", " ")
                lines.append(f"{i}. **{title}**\n   URL: {link}\n   {snippet}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Google CSE search failed: {e}"

def google_search(
    query: str,
    num_results: int = 5,
    location: str = "",
    time_range: str = "",
) -> str:
    """Search Google. Uses CSE if available, else SerpAPI."""
    if _env("GOOGLE_API_KEY") and _env("GOOGLE_SEARCH_ENGINE_ID"):
        return google_cse_search(query=query, num_results=num_results)

    api_key = _env("SERPAPI_KEY")
    if not api_key:
        return "❌ Requires GOOGLE_API_KEY+CX or SERPAPI_KEY."

    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": min(max(1, num_results), 10),
    }
    if location: params["location"] = location
    if time_range: params["tbs"] = time_range

    url = f"https://serpapi.com/search?{urllib.parse.urlencode(params)}"

    try:
        data = _http_get(url, ttl=_TTL_SEARCH)
        organic = data.get("organic_results", [])
        lines = [f"🔍 **Google Search Results** (via SerpAPI) for: **{query}**\n"]
        if not organic:
            lines.append("No results found.")
        else:
            for i, res in enumerate(organic[:num_results], 1):
                lines.append(f"{i}. **{res.get('title')}**\n   URL: {res.get('link')}\n   {res.get('snippet')}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Google search (SerpAPI) failed: {e}"

def brave_search(
    query: str,
    num_results: int = 5,
    freshness: str = "",
) -> str:
    """Search the web using Brave Search API."""
    api_key = _env("BRAVE_SEARCH_API_KEY")
    if not api_key: return _missing_key("brave_search", "BRAVE_SEARCH_API_KEY")

    params = {"q": query, "count": min(max(1, num_results), 20)}
    if freshness: params["freshness"] = freshness

    url = f"https://api.search.brave.com/res/v1/web/search?{urllib.parse.urlencode(params)}"
    headers = {"X-Subscription-Token": api_key}

    try:
        data = _http_get(url, headers=headers, ttl=_TTL_SEARCH)
        results = data.get("web", {}).get("results", [])
        if not results: return f"No results for: '{query}'"
        lines = [f"🦁 **Brave Search Results** for: **{query}**\n"]
        for i, res in enumerate(results[:num_results], 1):
            lines.append(f"{i}. **{res.get('title')}**\n   URL: {res.get('url')}\n   {res.get('description')}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Brave search failed: {e}"

TOOLS = [
    {
        "category": "SEARCH_TOOLS",
        "type": "function",
        "function": {
            "name": "google_cse_search",
            "description": "Search Google using the official Custom Search JSON API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results (1-10)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "category": "SEARCH_TOOLS",
        "type": "function",
        "function": {
            "name": "google_search",
            "description": "Search Google using CSE or SerpAPI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "category": "SEARCH_TOOLS",
        "type": "function",
        "function": {
            "name": "brave_search",
            "description": "Search the web using Brave Search API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results"},
                },
                "required": ["query"],
            },
        },
    },
]
