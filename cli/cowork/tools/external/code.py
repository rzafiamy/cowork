"""
🐙 Code Tools
Implementations for GitHub search.
"""

import urllib.parse
from .utils import _env, _http_get, _TTL_GITHUB

def github_search(
    query: str,
    search_type: str = "repositories",
    max_results: int = 5,
) -> str:
    """Search GitHub repositories, code, or issues."""
    token = _env("GITHUB_TOKEN")
    params = {"q": query, "per_page": min(max_results, 10)}
    url = f"https://api.github.com/search/{search_type}?{urllib.parse.urlencode(params)}"
    headers = {"Accept": "application/vnd.github+json"}
    if token: headers["Authorization"] = f"Bearer {token}"

    try:
        data = _http_get(url, headers=headers, ttl=_TTL_GITHUB)
        items = data.get("items", [])
        lines = [f"🐙 **GitHub Search** — '{query}'\n"]
        for i, item in enumerate(items[:max_results], 1):
            if search_type == "repositories":
                lines.append(f"{i}. **{item.get('full_name')}** ⭐ {item.get('stargazers_count')}\n   URL: {item.get('html_url')}\n")
            else:
                lines.append(f"{i}. {item.get('html_url')}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"GitHub search failed: {e}"

TOOLS = [
    {
        "category": "CODE_TOOLS",
        "type": "function",
        "function": {
            "name": "github_search",
            "description": "Search GitHub repositories, code, or issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "search_type": {"type": "string", "enum": ["repositories", "code", "issues"]},
                },
                "required": ["query"],
            },
        },
    },
]
