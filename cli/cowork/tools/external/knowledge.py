"""
📖 Knowledge Tools
Implementations for Wikipedia.
"""

import re
import urllib.parse
from .utils import _http_get, _TTL_WIKI

def wikipedia_search(query: str, max_results: int = 5) -> str:
    """Search Wikipedia for matching article titles."""
    params = urllib.parse.urlencode({"action": "opensearch", "search": query, "limit": max_results, "format": "json"})
    url = f"https://en.wikipedia.org/w/api.php?{params}"

    try:
        data = _http_get(url, ttl=_TTL_WIKI)
        titles = data[1]
        lines = [f"📖 **Wikipedia Results** for: **{query}**\n"]
        for i, title in enumerate(titles, 1):
            lines.append(f"{i}. {title}")
        return "\n".join(lines)
    except Exception as e:
        return f"Wikipedia search failed: {e}"

def wikipedia_article(title: str) -> str:
    """Fetch the full text of a Wikipedia article."""
    encoded = urllib.parse.quote(title.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"

    try:
        data = _http_get(url, ttl=_TTL_WIKI)
        return f"📖 **{data.get('title')}**\n\n{data.get('extract')}"
    except Exception as e:
        return f"Wikipedia article failed: {e}"

TOOLS = [
    {
        "category": "KNOWLEDGE_TOOLS",
        "type": "function",
        "function": {
            "name": "wikipedia_search",
            "description": "Search Wikipedia for article titles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "category": "KNOWLEDGE_TOOLS",
        "type": "function",
        "function": {
            "name": "wikipedia_article",
            "description": "Get the summary of a Wikipedia article.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Article title"},
                },
                "required": ["title"],
            },
        },
    },
]
