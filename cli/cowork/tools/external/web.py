"""
🔥 Web Scraping Tools
Implementations for scraping and crawling using Firecrawl.
"""

import time
from .utils import _env, _missing_key, _http_get, _http_post, _TTL_DEFAULT

def firecrawl_scrape(
    url: str,
    formats: list[str] | None = None,
    only_main_content: bool = True,
) -> str:
    """Scrape a single URL using Firecrawl API."""
    api_key = _env("FIRECRAWL_API_KEY")
    if not api_key: return _missing_key("firecrawl_scrape", "FIRECRAWL_API_KEY")

    payload = {
        "url": url,
        "formats": formats or ["markdown"],
        "onlyMainContent": only_main_content,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        data = _http_post("https://api.firecrawl.dev/v1/scrape", payload, headers=headers)
        if not data.get("success"): return f"Firecrawl scrape failed: {data.get('error')}"
        res = data.get("data", {})
        markdown = res.get("markdown", "")
        return f"🔥 **Firecrawl Scrape** — {res.get('metadata', {}).get('title', url)}\n\n{markdown[:8000]}"
    except Exception as e:
        return f"Firecrawl scrape failed: {e}"

def firecrawl_crawl(
    url: str,
    max_pages: int = 5,
) -> str:
    """Crawl a website using Firecrawl API."""
    api_key = _env("FIRECRAWL_API_KEY")
    if not api_key: return _missing_key("firecrawl_crawl", "FIRECRAWL_API_KEY")

    payload = {"url": url, "limit": min(max_pages, 20), "scrapeOptions": {"formats": ["markdown"]}}
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        data = _http_post("https://api.firecrawl.dev/v1/crawl", payload, headers=headers)
        job_id = data.get("id")
        if not job_id: return "No job ID returned."

        for _ in range(10):
            time.sleep(3)
            status_data = _http_get(f"https://api.firecrawl.dev/v1/crawl/{job_id}", headers=headers)
            if status_data.get("status") == "completed":
                pages = status_data.get("data", [])
                lines = [f"🔥 **Firecrawl Crawl** — {url}\n"]
                for i, p in enumerate(pages[:max_pages], 1):
                    lines.append(f"### {i}. {p.get('metadata', {}).get('title')}\n{p.get('markdown', '')[:1000]}\n")
                return "\n".join(lines)
        return "Crawl timed out."
    except Exception as e:
        return f"Firecrawl crawl failed: {e}"

TOOLS = [
    {
        "category": "WEB_TOOLS",
        "type": "function",
        "function": {
            "name": "firecrawl_scrape",
            "description": "Scrape a single URL using Firecrawl API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "category": "WEB_TOOLS",
        "type": "function",
        "function": {
            "name": "firecrawl_crawl",
            "description": "Crawl a website using Firecrawl API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Base URL to crawl"},
                },
                "required": ["url"],
            },
        },
    },
]
