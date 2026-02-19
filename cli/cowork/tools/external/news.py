"""
📰 News Tools
Implementations for fetching news headlines using NewsAPI.
"""

import urllib.parse
from .utils import _env, _missing_key, _http_get, _TTL_NEWS

def newsapi_headlines(
    query: str = "",
    category: str = "",
    country: str = "us",
    max_results: int = 5,
) -> str:
    """Fetch top news headlines using NewsAPI."""
    api_key = _env("NEWSAPI_KEY")
    if not api_key: return _missing_key("newsapi_headlines", "NEWSAPI_KEY")

    params = {"apiKey": api_key, "pageSize": min(max_results, 20)}
    if query:
        endpoint = "https://newsapi.org/v2/everything"
        params["q"] = query
    else:
        endpoint = "https://newsapi.org/v2/top-headlines"
        params["country"] = country
        if category: params["category"] = category

    url = f"{endpoint}?{urllib.parse.urlencode(params)}"

    try:
        data = _http_get(url, ttl=_TTL_NEWS)
        if data.get("status") != "ok": return f"NewsAPI error: {data.get('message')}"
        articles = data.get("articles", [])
        lines = [f"📰 **News Headlines**\n"]
        for i, art in enumerate(articles[:max_results], 1):
            lines.append(f"{i}. **{art.get('title')}**\n   {art.get('source', {}).get('name')} | {art.get('publishedAt')[:10]}\n   URL: {art.get('url')}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"NewsAPI failed: {e}"

TOOLS = [
    {
        "category": "NEWS_TOOLS",
        "type": "function",
        "function": {
            "name": "newsapi_headlines",
            "description": "Fetch top news headlines using NewsAPI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword"},
                    "category": {"type": "string", "description": "News category"},
                },
                "required": [],
            },
        },
    },
]
