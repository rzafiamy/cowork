"""
🔌 External Tools — Paid API Integrations
Provides rich, production-grade tool implementations that require API keys.
Each tool degrades gracefully when its key is missing.
All API calls are disk-cached (TTL per tool) to protect rate limits.

Supported tools:
  YOUTUBE_TOOLS  : youtube_search, youtube_transcript, youtube_metadata
  SEARCH_TOOLS   : google_cse_search, google_search, brave_search
  WEB_TOOLS      : firecrawl_scrape, firecrawl_crawl
  NEWS_TOOLS     : newsapi_headlines
  CODE_TOOLS     : github_search
  WEATHER_TOOLS  : openweather_current, openweather_forecast
  MEDIA_TOOLS    : tmdb_search, tmdb_details
  KNOWLEDGE_TOOLS: wikipedia_search, wikipedia_article
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional


# ─── Key Helpers ──────────────────────────────────────────────────────────────

def _env(key: str) -> Optional[str]:
    """Return env var value or None (never raises)."""
    return os.environ.get(key) or None


def _missing_key(tool_name: str, env_var: str) -> str:
    return (
        f"❌ Tool '{tool_name}' requires the `{env_var}` environment variable.\n"
        f"   Set it in your .env file and restart Cowork.\n"
        f"   See .env.example for all available API keys."
    )


# ─── Disk-Based TTL Cache ─────────────────────────────────────────────────────
# Caches API responses to disk to avoid burning rate limits on repeated calls.
# Cache files live in ~/.cowork/api_cache/ and expire after `ttl` seconds.

_CACHE_DIR = Path.home() / ".cowork" / "api_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Default TTLs (seconds) per tool category
_TTL_SEARCH   = 3600        # 1 hour  — search results
_TTL_NEWS     = 1800        # 30 min  — news headlines
_TTL_WEATHER  = 600         # 10 min  — weather (changes fast)
_TTL_METADATA = 86400       # 24 h    — video/movie metadata
_TTL_WIKI     = 86400 * 7   # 7 days  — Wikipedia articles
_TTL_GITHUB   = 3600        # 1 hour  — GitHub search
_TTL_DEFAULT  = 3600        # 1 hour  — everything else


def _cache_key(url: str, payload: dict | None = None) -> str:
    """Stable cache key from URL + optional POST body."""
    raw = url + (json.dumps(payload, sort_keys=True) if payload else "")
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_get(key: str, ttl: int) -> dict | str | None:
    """Return cached value if it exists and is still fresh, else None."""
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
    """Persist a value to the cache."""
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
    """HTTP GET with disk-based TTL caching. Returns parsed JSON or raw text."""
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
    """HTTP POST with disk-based TTL caching. Returns parsed JSON or raw text."""
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


# ─── YouTube Tools ────────────────────────────────────────────────────────────

def youtube_search(
    query: str,
    max_results: int = 5,
    order: str = "relevance",
) -> str:
    """
    Search YouTube videos using the YouTube Data API v3.
    Requires: YOUTUBE_API_KEY
    """
    api_key = _env("YOUTUBE_API_KEY")
    if not api_key:
        return _missing_key("youtube_search", "YOUTUBE_API_KEY")

    max_results = min(max(1, max_results), 25)
    params = urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "maxResults": max_results,
        "order": order,
        "type": "video",
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"

    try:
        data = _http_get(url, ttl=_TTL_SEARCH)
        if isinstance(data, str):
            return f"YouTube Search API error: {data[:500]}"

        items = data.get("items", [])
        if not items:
            return f"No YouTube results found for: '{query}'"

        lines = [f"🎬 YouTube Search Results for: **{query}**\n"]
        for i, item in enumerate(items, 1):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            title = snippet.get("title", "Untitled")
            channel = snippet.get("channelTitle", "Unknown")
            published = snippet.get("publishedAt", "")[:10]
            description = snippet.get("description", "")[:150]
            url_video = f"https://www.youtube.com/watch?v={video_id}"
            lines.append(
                f"{i}. **{title}**\n"
                f"   Channel: {channel} | Published: {published}\n"
                f"   URL: {url_video}\n"
                f"   {description}...\n"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"YouTube search failed: {e}"


def youtube_transcript(
    video_id: str,
    language: str = "en",
) -> str:
    """
    Fetch the transcript/captions of a YouTube video.
    Requires: youtube-transcript-api (pip) — no API key needed.
    video_id can be a full URL or just the video ID.
    """
    # Extract video ID from URL if needed
    if "youtube.com" in video_id or "youtu.be" in video_id:
        match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", video_id)
        if match:
            video_id = match.group(1)
        else:
            return f"Could not extract video ID from URL: {video_id}"

    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        
        # Support for different versions of the library
        if hasattr(YouTubeTranscriptApi, 'get_transcript'):
            # Older versions: class method returning list of dicts
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[language, "en"])
            full_text = " ".join(entry["text"] for entry in transcript_list)
            duration_secs = sum(entry.get("duration", 0) for entry in transcript_list)
        else:
            # Newer versions: instance method returning snippet objects
            transcript = YouTubeTranscriptApi().fetch(video_id, languages=[language, "en"])
            full_text = " ".join(s.text for s in transcript)
            duration_secs = sum(s.duration for s in transcript)

        minutes = int(duration_secs // 60)
        seconds = int(duration_secs % 60)
        return (
            f"📝 **YouTube Transcript** — Video ID: `{video_id}`\n"
            f"Duration: ~{minutes}m {seconds}s | Language: {language}\n"
            f"Words: {len(full_text.split())}\n\n"
            f"---\n\n{full_text}"
        )
    except ImportError:
        return (
            "❌ `youtube-transcript-api` is not installed.\n"
            "   Run: pip install youtube-transcript-api"
        )
    except Exception as e:
        return f"Transcript fetch failed for '{video_id}': {e}"


def youtube_metadata(video_id: str) -> str:
    """
    Fetch detailed metadata for a YouTube video (title, description, stats, tags).
    Requires: YOUTUBE_API_KEY
    video_id can be a full URL or just the video ID.
    """
    api_key = _env("YOUTUBE_API_KEY")
    if not api_key:
        return _missing_key("youtube_metadata", "YOUTUBE_API_KEY")

    # Extract video ID from URL if needed
    if "youtube.com" in video_id or "youtu.be" in video_id:
        match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", video_id)
        if match:
            video_id = match.group(1)

    params = urllib.parse.urlencode({
        "part": "snippet,statistics,contentDetails",
        "id": video_id,
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/videos?{params}"

    try:
        data = _http_get(url, ttl=_TTL_METADATA)
        if isinstance(data, str):
            return f"YouTube API error: {data[:500]}"

        items = data.get("items", [])
        if not items:
            return f"No video found with ID: '{video_id}'"

        item = items[0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        details = item.get("contentDetails", {})

        title = snippet.get("title", "Unknown")
        channel = snippet.get("channelTitle", "Unknown")
        published = snippet.get("publishedAt", "")[:10]
        description = snippet.get("description", "")[:500]
        tags = snippet.get("tags", [])
        duration = details.get("duration", "PT0S")  # ISO 8601 duration
        views = stats.get("viewCount", "N/A")
        likes = stats.get("likeCount", "N/A")
        comments = stats.get("commentCount", "N/A")

        # Parse ISO 8601 duration
        dur_match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        if dur_match:
            h, m, s = (int(x or 0) for x in dur_match.groups())
            duration_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"
        else:
            duration_str = duration

        return (
            f"📹 **YouTube Video Metadata**\n\n"
            f"**Title**: {title}\n"
            f"**Channel**: {channel}\n"
            f"**Published**: {published}\n"
            f"**Duration**: {duration_str}\n"
            f"**Views**: {int(views):,}\n"
            f"**Likes**: {int(likes):,}\n"
            f"**Comments**: {int(comments):,}\n"
            f"**URL**: https://www.youtube.com/watch?v={video_id}\n"
            f"**Tags**: {', '.join(tags[:10]) if tags else 'None'}\n\n"
            f"**Description**:\n{description}{'...' if len(snippet.get('description','')) > 500 else ''}"
        )

    except Exception as e:
        return f"YouTube metadata fetch failed: {e}"


# ─── Google Search (Custom Search JSON API + SerpAPI fallback) ────────────────

def google_cse_search(
    query: str,
    num_results: int = 5,
    language: str = "en",
    date_restrict: str = "",
    site_search: str = "",
) -> str:
    """
    Search Google using the official Custom Search JSON API.
    Requires: GOOGLE_API_KEY + GOOGLE_SEARCH_ENGINE_ID
    date_restrict: d[N] (N days), w[N] (N weeks), m[N] (N months), y[N] (N years)
    site_search: restrict results to a specific site (e.g. 'github.com')
    """
    api_key = _env("GOOGLE_API_KEY")
    cx = _env("GOOGLE_SEARCH_ENGINE_ID")

    if not api_key:
        return _missing_key("google_cse_search", "GOOGLE_API_KEY")
    if not cx:
        return _missing_key("google_cse_search", "GOOGLE_SEARCH_ENGINE_ID")

    num_results = min(max(1, num_results), 10)
    params: dict[str, Any] = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": num_results,
        "hl": language,
    }
    if date_restrict:
        params["dateRestrict"] = date_restrict
    if site_search:
        params["siteSearch"] = site_search

    url = f"https://www.googleapis.com/customsearch/v1?{urllib.parse.urlencode(params)}"

    try:
        data = _http_get(url, ttl=_TTL_SEARCH)

        error = data.get("error")
        if error:
            return f"Google CSE API error {error.get('code')}: {error.get('message', 'Unknown error')}"

        items = data.get("items", [])
        search_info = data.get("searchInformation", {})
        total = search_info.get("formattedTotalResults", "?")  # e.g. "1,230,000"
        search_time = search_info.get("formattedSearchTime", "?")  # e.g. "0.42"

        lines = [
            f"🔍 **Google Search Results** for: **{query}**\n"
            f"   About {total} results ({search_time}s)\n"
        ]

        if not items:
            lines.append("No results found.")
        else:
            for i, item in enumerate(items, 1):
                title = item.get("title", "Untitled")
                link = item.get("link", "")
                snippet = item.get("snippet", "").replace("\n", " ")
                display_link = item.get("displayLink", "")
                # Rich snippet date if available
                pagemap = item.get("pagemap", {})
                metatags = pagemap.get("metatags", [{}])
                date = metatags[0].get("article:published_time", "")[:10] if metatags else ""
                date_str = f" | {date}" if date else ""
                lines.append(
                    f"{i}. **{title}**{date_str}\n"
                    f"   🌐 {display_link}\n"
                    f"   URL: {link}\n"
                    f"   {snippet}\n"
                )

        return "\n".join(lines)

    except Exception as e:
        return f"Google CSE search failed: {e}"


def google_search(
    query: str,
    num_results: int = 5,
    location: str = "",
    time_range: str = "",
) -> str:
    """
    Search Google. Automatically uses the best available backend:
      1. Google Custom Search JSON API (GOOGLE_API_KEY + GOOGLE_SEARCH_ENGINE_ID) — preferred
      2. SerpAPI (SERPAPI_KEY) — fallback
    time_range (SerpAPI only): qdr:h (hour), qdr:d (day), qdr:w (week), qdr:m (month)
    """
    # Prefer native Google API if both keys are present
    if _env("GOOGLE_API_KEY") and _env("GOOGLE_SEARCH_ENGINE_ID"):
        return google_cse_search(query=query, num_results=num_results)

    # Fall back to SerpAPI
    api_key = _env("SERPAPI_KEY")
    if not api_key:
        return (
            "❌ Tool 'google_search' requires either:\n"
            "   • GOOGLE_API_KEY + GOOGLE_SEARCH_ENGINE_ID  (Google Custom Search API)\n"
            "   • SERPAPI_KEY  (SerpAPI fallback)\n"
            "   Set them in your .env file and restart Cowork."
        )

    params: dict[str, Any] = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": min(max(1, num_results), 10),
        "hl": "en",
    }
    if location:
        params["location"] = location
    if time_range:
        params["tbs"] = time_range

    url = f"https://serpapi.com/search?{urllib.parse.urlencode(params)}"

    try:
        data = _http_get(url, ttl=_TTL_SEARCH)

        organic = data.get("organic_results", [])
        answer_box = data.get("answer_box", {})
        knowledge_graph = data.get("knowledge_graph", {})

        lines = [f"🔍 **Google Search Results** (via SerpAPI) for: **{query}**\n"]

        if answer_box:
            answer = answer_box.get("answer") or answer_box.get("snippet", "")
            if answer:
                lines.append(f"💡 **Direct Answer**: {answer}\n")

        if knowledge_graph:
            kg_title = knowledge_graph.get("title", "")
            kg_desc = knowledge_graph.get("description", "")
            if kg_title:
                lines.append(f"📚 **Knowledge Graph**: {kg_title} — {kg_desc}\n")

        if not organic:
            lines.append("No organic results found.")
        else:
            for i, result in enumerate(organic[:num_results], 1):
                title = result.get("title", "Untitled")
                link = result.get("link", "")
                snippet = result.get("snippet", "")
                date = result.get("date", "")
                date_str = f" | {date}" if date else ""
                lines.append(
                    f"{i}. **{title}**{date_str}\n"
                    f"   URL: {link}\n"
                    f"   {snippet}\n"
                )

        return "\n".join(lines)

    except Exception as e:
        return f"Google search (SerpAPI) failed: {e}"


# ─── Brave Search ─────────────────────────────────────────────────────────────

def brave_search(
    query: str,
    num_results: int = 5,
    freshness: str = "",
) -> str:
    """
    Search the web using Brave Search API.
    Requires: BRAVE_SEARCH_API_KEY
    freshness: pd (past day), pw (past week), pm (past month), py (past year)
    """
    api_key = _env("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return _missing_key("brave_search", "BRAVE_SEARCH_API_KEY")

    params: dict[str, Any] = {
        "q": query,
        "count": min(max(1, num_results), 20),
    }
    if freshness:
        params["freshness"] = freshness

    url = f"https://api.search.brave.com/res/v1/web/search?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }

    try:
        data = _http_get(url, headers=headers, ttl=_TTL_SEARCH)

        results = data.get("web", {}).get("results", [])
        if not results:
            return f"No Brave Search results for: '{query}'"

        lines = [f"🦁 **Brave Search Results** for: **{query}**\n"]
        for i, result in enumerate(results[:num_results], 1):
            title = result.get("title", "Untitled")
            url_r = result.get("url", "")
            description = result.get("description", "")
            age = result.get("age", "")
            age_str = f" | {age}" if age else ""
            lines.append(
                f"{i}. **{title}**{age_str}\n"
                f"   URL: {url_r}\n"
                f"   {description}\n"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"Brave search failed: {e}"


# ─── Firecrawl ────────────────────────────────────────────────────────────────

def firecrawl_scrape(
    url: str,
    formats: list[str] | None = None,
    only_main_content: bool = True,
) -> str:
    """
    Scrape a single URL using Firecrawl API (returns clean markdown).
    Requires: FIRECRAWL_API_KEY
    formats: ['markdown', 'html', 'rawHtml', 'links', 'screenshot']
    """
    api_key = _env("FIRECRAWL_API_KEY")
    if not api_key:
        return _missing_key("firecrawl_scrape", "FIRECRAWL_API_KEY")

    formats = formats or ["markdown"]
    payload = {
        "url": url,
        "formats": formats,
        "onlyMainContent": only_main_content,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        data = _http_post("https://api.firecrawl.dev/v1/scrape", payload, headers=headers, ttl=_TTL_DEFAULT)
        if isinstance(data, str):
            return f"Firecrawl API error: {data[:500]}"

        if not data.get("success"):
            return f"Firecrawl scrape failed: {data.get('error', 'Unknown error')}"

        result_data = data.get("data", {})
        markdown = result_data.get("markdown", "")
        metadata = result_data.get("metadata", {})
        title = metadata.get("title", url)
        description = metadata.get("description", "")

        return (
            f"🔥 **Firecrawl Scrape** — {title}\n"
            f"URL: {url}\n"
            f"Description: {description}\n\n"
            f"---\n\n{markdown[:8000]}"
            + ("...\n[Content truncated]" if len(markdown) > 8000 else "")
        )

    except Exception as e:
        return f"Firecrawl scrape failed: {e}"


def firecrawl_crawl(
    url: str,
    max_pages: int = 5,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
) -> str:
    """
    Crawl a website using Firecrawl API (returns multiple pages as markdown).
    Requires: FIRECRAWL_API_KEY
    """
    api_key = _env("FIRECRAWL_API_KEY")
    if not api_key:
        return _missing_key("firecrawl_crawl", "FIRECRAWL_API_KEY")

    max_pages = min(max(1, max_pages), 20)
    payload: dict[str, Any] = {
        "url": url,
        "limit": max_pages,
        "scrapeOptions": {"formats": ["markdown"]},
    }
    if include_paths:
        payload["includePaths"] = include_paths
    if exclude_paths:
        payload["excludePaths"] = exclude_paths

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        # Start crawl job
        data = _http_post("https://api.firecrawl.dev/v1/crawl", payload, headers=headers, ttl=_TTL_DEFAULT)
        if isinstance(data, str):
            return f"Firecrawl API error: {data[:500]}"

        if not data.get("success"):
            return f"Firecrawl crawl failed: {data.get('error', 'Unknown error')}"

        job_id = data.get("id", "")
        if not job_id:
            return "Firecrawl crawl: No job ID returned."

        # Poll for results (up to 30 seconds)
        import time
        for attempt in range(10):
            time.sleep(3)
            status_data = _http_get(
                f"https://api.firecrawl.dev/v1/crawl/{job_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if isinstance(status_data, str):
                continue
            status = status_data.get("status", "")
            if status == "completed":
                pages = status_data.get("data", [])
                lines = [f"🔥 **Firecrawl Crawl** — {url}\nPages crawled: {len(pages)}\n\n"]
                for i, page in enumerate(pages[:max_pages], 1):
                    page_meta = page.get("metadata", {})
                    page_title = page_meta.get("title", f"Page {i}")
                    page_url = page_meta.get("sourceURL", "")
                    page_md = page.get("markdown", "")[:2000]
                    lines.append(f"### {i}. {page_title}\nURL: {page_url}\n\n{page_md}\n\n---\n")
                return "\n".join(lines)
            elif status == "failed":
                return f"Firecrawl crawl job failed: {status_data.get('error', 'Unknown')}"

        return f"Firecrawl crawl timed out. Job ID: {job_id} — Check Firecrawl dashboard."

    except Exception as e:
        return f"Firecrawl crawl failed: {e}"


# ─── NewsAPI ──────────────────────────────────────────────────────────────────

def newsapi_headlines(
    query: str = "",
    category: str = "",
    country: str = "us",
    language: str = "en",
    max_results: int = 5,
) -> str:
    """
    Fetch top news headlines using NewsAPI.
    Requires: NEWSAPI_KEY
    category: business, entertainment, health, science, sports, technology
    """
    api_key = _env("NEWSAPI_KEY")
    if not api_key:
        return _missing_key("newsapi_headlines", "NEWSAPI_KEY")

    max_results = min(max(1, max_results), 20)
    params: dict[str, Any] = {
        "apiKey": api_key,
        "language": language,
        "pageSize": max_results,
    }

    if query:
        endpoint = "https://newsapi.org/v2/everything"
        params["q"] = query
        params["sortBy"] = "publishedAt"
    else:
        endpoint = "https://newsapi.org/v2/top-headlines"
        params["country"] = country
        if category:
            params["category"] = category

    url = f"{endpoint}?{urllib.parse.urlencode(params)}"

    try:
        data = _http_get(url, ttl=_TTL_NEWS)

        if data.get("status") != "ok":
            return f"NewsAPI error: {data.get('message', 'Unknown error')}"

        articles = data.get("articles", [])
        if not articles:
            return f"No news articles found for: '{query or category or country}'"

        header = f"📰 **News Headlines**"
        if query:
            header += f" — '{query}'"
        elif category:
            header += f" — {category.title()}"
        lines = [header + "\n"]

        for i, article in enumerate(articles[:max_results], 1):
            title = article.get("title", "Untitled")
            source = article.get("source", {}).get("name", "Unknown")
            published = article.get("publishedAt", "")[:10]
            description = article.get("description", "") or ""
            url_a = article.get("url", "")
            lines.append(
                f"{i}. **{title}**\n"
                f"   Source: {source} | {published}\n"
                f"   {description[:200]}\n"
                f"   URL: {url_a}\n"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"NewsAPI fetch failed: {e}"


# ─── GitHub Search ────────────────────────────────────────────────────────────

def github_search(
    query: str,
    search_type: str = "repositories",
    max_results: int = 5,
    language: str = "",
    sort: str = "stars",
) -> str:
    """
    Search GitHub repositories, code, or issues.
    Requires: GITHUB_TOKEN (for higher rate limits)
    search_type: repositories, code, issues, users
    """
    token = _env("GITHUB_TOKEN")

    max_results = min(max(1, max_results), 10)
    q = query
    if language and search_type == "repositories":
        q += f" language:{language}"

    params = urllib.parse.urlencode({
        "q": q,
        "per_page": max_results,
        "sort": sort,
    })
    url = f"https://api.github.com/search/{search_type}?{params}"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        data = _http_get(url, headers=headers, ttl=_TTL_GITHUB)

        items = data.get("items", [])
        total = data.get("total_count", 0)

        if not items:
            return f"No GitHub {search_type} found for: '{query}'"

        lines = [f"🐙 **GitHub {search_type.title()} Search** — '{query}' ({total:,} total)\n"]

        for i, item in enumerate(items[:max_results], 1):
            if search_type == "repositories":
                name = item.get("full_name", "Unknown")
                desc = item.get("description", "") or "No description"
                stars = item.get("stargazers_count", 0)
                forks = item.get("forks_count", 0)
                lang = item.get("language", "")
                url_r = item.get("html_url", "")
                lines.append(
                    f"{i}. **{name}** ⭐ {stars:,} | 🍴 {forks:,} | {lang}\n"
                    f"   {desc[:150]}\n"
                    f"   URL: {url_r}\n"
                )
            elif search_type == "code":
                repo = item.get("repository", {}).get("full_name", "")
                path = item.get("path", "")
                url_r = item.get("html_url", "")
                lines.append(f"{i}. `{repo}/{path}`\n   URL: {url_r}\n")
            elif search_type == "issues":
                title = item.get("title", "Untitled")
                state = item.get("state", "")
                url_r = item.get("html_url", "")
                lines.append(f"{i}. [{state.upper()}] **{title}**\n   URL: {url_r}\n")
            else:
                lines.append(f"{i}. {item.get('login', item.get('name', 'Unknown'))}\n")

        if not token:
            lines.append("\n💡 Set GITHUB_TOKEN in .env for higher rate limits.")
        return "\n".join(lines)

    except Exception as e:
        return f"GitHub search failed: {e}"


# ─── OpenWeatherMap ───────────────────────────────────────────────────────────

def openweather_current(location: str, units: str = "metric") -> str:
    """
    Get current weather conditions for a city using OpenWeatherMap API.
    Requires: OPENWEATHER_API_KEY
    units: metric (°C), imperial (°F), standard (K)
    """
    api_key = _env("OPENWEATHER_API_KEY")
    if not api_key:
        return _missing_key("openweather_current", "OPENWEATHER_API_KEY")

    params = urllib.parse.urlencode({
        "q": location,
        "appid": api_key,
        "units": units,
    })
    url = f"https://api.openweathermap.org/data/2.5/weather?{params}"

    try:
        data = _http_get(url, ttl=_TTL_WEATHER)
        if isinstance(data, str):
            return f"OpenWeatherMap error: {data[:500]}"
        if data.get("cod") not in (200, "200"):
            return f"OpenWeatherMap error: {data.get('message', 'Unknown error')}"

        unit_sym = "°C" if units == "metric" else ("°F" if units == "imperial" else "K")
        main = data.get("main", {})
        wind = data.get("wind", {})
        weather = data.get("weather", [{}])[0]
        sys = data.get("sys", {})
        visibility = data.get("visibility", 0)
        city = data.get("name", location)
        country = sys.get("country", "")

        return (
            f"🌤️ **Current Weather** — {city}, {country}\n\n"
            f"**Condition**: {weather.get('description', '').title()}\n"
            f"**Temperature**: {main.get('temp')}{unit_sym} "
            f"(feels like {main.get('feels_like')}{unit_sym})\n"
            f"**Min/Max**: {main.get('temp_min')}{unit_sym} / {main.get('temp_max')}{unit_sym}\n"
            f"**Humidity**: {main.get('humidity')}%\n"
            f"**Pressure**: {main.get('pressure')} hPa\n"
            f"**Wind**: {wind.get('speed')} m/s, direction {wind.get('deg', 'N/A')}°\n"
            f"**Visibility**: {visibility // 1000} km\n"
            f"**Cloud Cover**: {data.get('clouds', {}).get('all', 0)}%"
        )
    except Exception as e:
        return f"OpenWeatherMap current weather failed: {e}"


def openweather_forecast(
    location: str,
    days: int = 5,
    units: str = "metric",
) -> str:
    """
    Get a 5-day / 3-hour weather forecast using OpenWeatherMap API.
    Requires: OPENWEATHER_API_KEY
    """
    api_key = _env("OPENWEATHER_API_KEY")
    if not api_key:
        return _missing_key("openweather_forecast", "OPENWEATHER_API_KEY")

    days = min(max(1, days), 5)
    params = urllib.parse.urlencode({
        "q": location,
        "appid": api_key,
        "units": units,
        "cnt": days * 8,  # 8 readings per day (every 3h)
    })
    url = f"https://api.openweathermap.org/data/2.5/forecast?{params}"

    try:
        data = _http_get(url, ttl=_TTL_WEATHER)
        if isinstance(data, str):
            return f"OpenWeatherMap error: {data[:500]}"
        if data.get("cod") not in (200, "200"):
            return f"OpenWeatherMap error: {data.get('message', 'Unknown error')}"

        unit_sym = "°C" if units == "metric" else ("°F" if units == "imperial" else "K")
        city_info = data.get("city", {})
        city = city_info.get("name", location)
        country = city_info.get("country", "")
        forecasts = data.get("list", [])

        # Group by day
        from collections import defaultdict
        daily: dict[str, list] = defaultdict(list)
        for entry in forecasts:
            day = entry.get("dt_txt", "")[:10]
            daily[day].append(entry)

        lines = [f"📅 **{days}-Day Forecast** — {city}, {country}\n"]
        for day, entries in list(daily.items())[:days]:
            temps = [e["main"]["temp"] for e in entries]
            descs = [e["weather"][0]["description"] for e in entries]
            humidity = entries[0]["main"]["humidity"]
            most_common_desc = max(set(descs), key=descs.count).title()
            lines.append(
                f"**{day}**: {most_common_desc} | "
                f"Low {min(temps):.1f}{unit_sym} / High {max(temps):.1f}{unit_sym} | "
                f"Humidity {humidity}%"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"OpenWeatherMap forecast failed: {e}"


# ─── TMDB (The Movie Database) ────────────────────────────────────────────────

def tmdb_search(
    query: str,
    media_type: str = "multi",
    max_results: int = 5,
    year: int = 0,
) -> str:
    """
    Search for movies, TV shows, or people on TMDB.
    Requires: TMDB_API_KEY
    media_type: multi, movie, tv, person
    """
    api_key = _env("TMDB_API_KEY")
    if not api_key:
        return _missing_key("tmdb_search", "TMDB_API_KEY")

    max_results = min(max(1, max_results), 20)
    params: dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "include_adult": "false",
    }
    if year:
        params["year"] = year

    url = f"https://api.themoviedb.org/3/search/{media_type}?{urllib.parse.urlencode(params)}"

    try:
        data = _http_get(url, ttl=_TTL_METADATA)
        if isinstance(data, str):
            return f"TMDB API error: {data[:500]}"

        results = data.get("results", [])
        total = data.get("total_results", 0)
        if not results:
            return f"No TMDB results found for: '{query}'"

        lines = [f"🎬 **TMDB Search** — '{query}' ({total:,} results)\n"]
        for i, item in enumerate(results[:max_results], 1):
            mtype = item.get("media_type", media_type)
            if mtype == "movie":
                title = item.get("title", "Unknown")
                date = item.get("release_date", "")[:4]
                overview = item.get("overview", "")[:200]
                rating = item.get("vote_average", 0)
                tmdb_id = item.get("id")
                lines.append(
                    f"{i}. 🎥 **{title}** ({date}) ⭐ {rating:.1f}/10\n"
                    f"   ID: {tmdb_id} | {overview}...\n"
                )
            elif mtype == "tv":
                title = item.get("name", "Unknown")
                date = item.get("first_air_date", "")[:4]
                overview = item.get("overview", "")[:200]
                rating = item.get("vote_average", 0)
                tmdb_id = item.get("id")
                lines.append(
                    f"{i}. 📺 **{title}** ({date}) ⭐ {rating:.1f}/10\n"
                    f"   ID: {tmdb_id} | {overview}...\n"
                )
            elif mtype == "person":
                name = item.get("name", "Unknown")
                dept = item.get("known_for_department", "")
                known_for = ", ".join(
                    kf.get("title") or kf.get("name", "") for kf in item.get("known_for", [])[:3]
                )
                lines.append(f"{i}. 👤 **{name}** ({dept}) — Known for: {known_for}\n")
            else:
                lines.append(f"{i}. {item.get('title') or item.get('name', 'Unknown')}\n")

        lines.append("\n💡 Use `tmdb_details` with an ID to get full info.")
        return "\n".join(lines)

    except Exception as e:
        return f"TMDB search failed: {e}"


def tmdb_details(
    tmdb_id: int,
    media_type: str = "movie",
) -> str:
    """
    Get full details for a movie or TV show from TMDB.
    Requires: TMDB_API_KEY
    media_type: movie, tv
    """
    api_key = _env("TMDB_API_KEY")
    if not api_key:
        return _missing_key("tmdb_details", "TMDB_API_KEY")

    params = urllib.parse.urlencode({
        "api_key": api_key,
        "append_to_response": "credits,videos,keywords",
    })
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?{params}"

    try:
        data = _http_get(url, ttl=_TTL_METADATA)
        if isinstance(data, str):
            return f"TMDB API error: {data[:500]}"
        if "status_message" in data:
            return f"TMDB error: {data['status_message']}"

        if media_type == "movie":
            title = data.get("title", "Unknown")
            tagline = data.get("tagline", "")
            release = data.get("release_date", "")[:10]
            runtime = data.get("runtime", 0)
            rating = data.get("vote_average", 0)
            votes = data.get("vote_count", 0)
            genres = ", ".join(g["name"] for g in data.get("genres", []))
            overview = data.get("overview", "")
            budget = data.get("budget", 0)
            revenue = data.get("revenue", 0)
            status = data.get("status", "")
            homepage = data.get("homepage", "")
            # Cast
            cast = data.get("credits", {}).get("cast", [])[:5]
            cast_str = ", ".join(f"{c['name']} as {c['character']}" for c in cast)
            # Director
            crew = data.get("credits", {}).get("crew", [])
            directors = [c["name"] for c in crew if c.get("job") == "Director"]

            return (
                f"🎬 **{title}**\n"
                + (f"*{tagline}*\n" if tagline else "")
                + f"\n**Release**: {release} | **Runtime**: {runtime} min\n"
                f"**Rating**: ⭐ {rating:.1f}/10 ({votes:,} votes)\n"
                f"**Status**: {status}\n"
                f"**Genres**: {genres}\n"
                f"**Director(s)**: {', '.join(directors) or 'N/A'}\n"
                f"**Cast**: {cast_str}\n"
                + (f"**Budget**: ${budget:,}\n" if budget else "")
                + (f"**Revenue**: ${revenue:,}\n" if revenue else "")
                + (f"**Homepage**: {homepage}\n" if homepage else "")
                + f"\n**Overview**:\n{overview}"
            )

        elif media_type == "tv":
            title = data.get("name", "Unknown")
            tagline = data.get("tagline", "")
            first_air = data.get("first_air_date", "")[:10]
            last_air = data.get("last_air_date", "")[:10]
            seasons = data.get("number_of_seasons", 0)
            episodes = data.get("number_of_episodes", 0)
            rating = data.get("vote_average", 0)
            votes = data.get("vote_count", 0)
            genres = ", ".join(g["name"] for g in data.get("genres", []))
            overview = data.get("overview", "")
            status = data.get("status", "")
            networks = ", ".join(n["name"] for n in data.get("networks", []))
            cast = data.get("credits", {}).get("cast", [])[:5]
            cast_str = ", ".join(f"{c['name']} as {c['character']}" for c in cast)

            return (
                f"📺 **{title}**\n"
                + (f"*{tagline}*\n" if tagline else "")
                + f"\n**First Air**: {first_air} | **Last Air**: {last_air}\n"
                f"**Seasons**: {seasons} | **Episodes**: {episodes}\n"
                f"**Rating**: ⭐ {rating:.1f}/10 ({votes:,} votes)\n"
                f"**Status**: {status}\n"
                f"**Network(s)**: {networks}\n"
                f"**Genres**: {genres}\n"
                f"**Cast**: {cast_str}\n"
                f"\n**Overview**:\n{overview}"
            )

        return f"Unsupported media_type: {media_type}. Use 'movie' or 'tv'."

    except Exception as e:
        return f"TMDB details fetch failed: {e}"


# ─── Wikipedia (Enhanced) ─────────────────────────────────────────────────────

def wikipedia_search(query: str, max_results: int = 5) -> str:
    """
    Search Wikipedia and return a list of matching article titles.
    No API key required.
    """
    params = urllib.parse.urlencode({
        "action": "opensearch",
        "search": query,
        "limit": min(max(1, max_results), 20),
        "namespace": 0,
        "format": "json",
    })
    url = f"https://en.wikipedia.org/w/api.php?{params}"

    try:
        data = _http_get(url, headers={"User-Agent": "CoworkCLI/1.0 (contact@cowork.ai)"}, ttl=_TTL_WIKI)
        if isinstance(data, str):
            return f"Wikipedia search error: {data[:500]}"

        # opensearch returns [query, [titles], [descriptions], [urls]]
        if not isinstance(data, list) or len(data) < 4:
            return f"No Wikipedia results for: '{query}'"

        titles = data[1]
        descriptions = data[2]
        urls = data[3]

        if not titles:
            return f"No Wikipedia articles found for: '{query}'"

        lines = [f"📖 **Wikipedia Search** — '{query}'\n"]
        for i, (title, desc, url) in enumerate(zip(titles, descriptions, urls), 1):
            lines.append(
                f"{i}. **{title}**\n"
                f"   {desc[:200] if desc else 'No description'}\n"
                f"   URL: {url}\n"
            )
        lines.append("\n💡 Use `wikipedia_article` with a title to get the full article.")
        return "\n".join(lines)

    except Exception as e:
        return f"Wikipedia search failed: {e}"


def wikipedia_article(title: str, section: str = "") -> str:
    """
    Fetch the full text of a Wikipedia article (or a specific section).
    No API key required.
    """
    # First get the full article via the REST API
    encoded = urllib.parse.quote(title.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"

    try:
        summary_data = _http_get(url, headers={"User-Agent": "CoworkCLI/1.0"}, ttl=_TTL_WIKI)
        if isinstance(summary_data, str):
            return f"Wikipedia error: {summary_data[:500]}"

        page_title = summary_data.get("title", title)
        extract = summary_data.get("extract", "")
        page_url = summary_data.get("content_urls", {}).get("desktop", {}).get("page", "")
        description = summary_data.get("description", "")

        # If section requested, fetch full content via parse API
        if section:
            params = urllib.parse.urlencode({
                "action": "parse",
                "page": title,
                "prop": "wikitext",
                "section": section,
                "format": "json",
            })
            section_url = f"https://en.wikipedia.org/w/api.php?{params}"
            section_data = _http_get(section_url, headers={"User-Agent": "CoworkCLI/1.0"})
            if isinstance(section_data, dict):
                wikitext = section_data.get("parse", {}).get("wikitext", {}).get("*", "")
                # Strip wiki markup
                wikitext = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", wikitext)
                wikitext = re.sub(r"\{\{[^}]+\}\}", "", wikitext)
                wikitext = re.sub(r"<[^>]+>", "", wikitext)
                wikitext = re.sub(r"\s+", " ", wikitext).strip()
                extract = wikitext[:5000]

        return (
            f"📖 **{page_title}**\n"
            + (f"*{description}*\n" if description else "")
            + f"\nSource: {page_url}\n\n"
            f"---\n\n{extract}"
            + ("\n\n[Article truncated — use section parameter for specific sections]" if len(extract) >= 5000 else "")
        )

    except Exception as e:
        return f"Wikipedia article fetch failed for '{title}': {e}"


# ─── Tool Schema Definitions (for ALL_TOOLS registry) ─────────────────────────

EXTERNAL_TOOLS: list[dict] = [
    # ── YOUTUBE_TOOLS ─────────────────────────────────────────────────────────
    {
        "category": "YOUTUBE_TOOLS",
        "type": "function",
        "function": {
            "name": "youtube_search",
            "description": (
                "Search YouTube for videos matching a query. "
                "Returns titles, channels, publish dates, and URLs. "
                "Requires YOUTUBE_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Number of results (1-25, default 5)"},
                    "order": {
                        "type": "string",
                        "description": "Sort order",
                        "enum": ["relevance", "date", "viewCount", "rating"],
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "category": "YOUTUBE_TOOLS",
        "type": "function",
        "function": {
            "name": "youtube_transcript",
            "description": (
                "Fetch the full transcript/captions of a YouTube video. "
                "Accepts a video URL or video ID. "
                "No API key required (uses youtube-transcript-api)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "description": "YouTube video URL or video ID (e.g. dQw4w9WgXcQ)"},
                    "language": {"type": "string", "description": "Preferred language code (default: en)"},
                },
                "required": ["video_id"],
            },
        },
    },
    {
        "category": "YOUTUBE_TOOLS",
        "type": "function",
        "function": {
            "name": "youtube_metadata",
            "description": (
                "Fetch detailed metadata for a YouTube video: title, channel, "
                "duration, view count, likes, tags, and description. "
                "Requires YOUTUBE_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "description": "YouTube video URL or video ID"},
                },
                "required": ["video_id"],
            },
        },
    },
    # ── SEARCH_TOOLS ──────────────────────────────────────────────────────────
    {
        "category": "SEARCH_TOOLS",
        "type": "function",
        "function": {
            "name": "google_cse_search",
            "description": (
                "Search Google using the official Custom Search JSON API. "
                "Returns titles, URLs, snippets, and publication dates. "
                "Supports site-restricted search and date filtering. "
                "Requires GOOGLE_API_KEY + GOOGLE_SEARCH_ENGINE_ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results (1-10, default 5)"},
                    "language": {"type": "string", "description": "Language code for results (default: en)"},
                    "date_restrict": {
                        "type": "string",
                        "description": "Restrict by date: d5 (5 days), w2 (2 weeks), m1 (1 month), y1 (1 year)",
                    },
                    "site_search": {
                        "type": "string",
                        "description": "Restrict results to a specific domain (e.g. 'github.com')",
                    },
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
            "description": (
                "Search Google using the best available backend: "
                "Google Custom Search API (preferred, needs GOOGLE_API_KEY + GOOGLE_SEARCH_ENGINE_ID) "
                "or SerpAPI fallback (needs SERPAPI_KEY). "
                "Returns organic results, answer boxes, and knowledge graph data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results (1-10, default 5)"},
                    "location": {"type": "string", "description": "Geographic location for localized results (SerpAPI only)"},
                    "time_range": {
                        "type": "string",
                        "description": "Time filter (SerpAPI only): qdr:h (hour), qdr:d (day), qdr:w (week), qdr:m (month)",
                    },
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
            "description": (
                "Search the web using Brave Search API. Privacy-focused, "
                "independent index. Good alternative to Google. "
                "Requires BRAVE_SEARCH_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results (1-20, default 5)"},
                    "freshness": {
                        "type": "string",
                        "description": "Time filter: pd (day), pw (week), pm (month), py (year)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    # ── WEB_TOOLS ─────────────────────────────────────────────────────────────
    {
        "category": "WEB_TOOLS",
        "type": "function",
        "function": {
            "name": "firecrawl_scrape",
            "description": (
                "Scrape a single URL using Firecrawl and return clean Markdown. "
                "Handles JavaScript-rendered pages, paywalls, and complex layouts. "
                "Much better than basic HTML scraping. "
                "Requires FIRECRAWL_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape"},
                    "formats": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Output formats: markdown, html, links (default: ['markdown'])",
                    },
                    "only_main_content": {
                        "type": "boolean",
                        "description": "Strip navigation/ads and return only main content (default: true)",
                    },
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
            "description": (
                "Crawl an entire website using Firecrawl and return multiple pages as Markdown. "
                "Useful for documentation sites, blogs, or knowledge bases. "
                "Requires FIRECRAWL_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Starting URL to crawl"},
                    "max_pages": {"type": "integer", "description": "Maximum pages to crawl (1-20, default 5)"},
                    "include_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "URL path patterns to include (e.g. ['/docs/', '/blog/'])",
                    },
                    "exclude_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "URL path patterns to exclude",
                    },
                },
                "required": ["url"],
            },
        },
    },
    # ── NEWS_TOOLS ────────────────────────────────────────────────────────────
    {
        "category": "NEWS_TOOLS",
        "type": "function",
        "function": {
            "name": "newsapi_headlines",
            "description": (
                "Fetch top news headlines or search news articles using NewsAPI. "
                "Covers 150,000+ sources worldwide. "
                "Requires NEWSAPI_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (leave empty for top headlines)"},
                    "category": {
                        "type": "string",
                        "description": "News category (for top headlines only)",
                        "enum": ["business", "entertainment", "health", "science", "sports", "technology", ""],
                    },
                    "country": {"type": "string", "description": "2-letter country code (default: us)"},
                    "language": {"type": "string", "description": "Language code (default: en)"},
                    "max_results": {"type": "integer", "description": "Number of articles (1-20, default 5)"},
                },
                "required": [],
            },
        },
    },
    # ── CODE_TOOLS ────────────────────────────────────────────────────────────
    {
        "category": "CODE_TOOLS",
        "type": "function",
        "function": {
            "name": "github_search",
            "description": (
                "Search GitHub for repositories, code snippets, or issues. "
                "GITHUB_TOKEN is optional but recommended for higher rate limits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "search_type": {
                        "type": "string",
                        "description": "What to search",
                        "enum": ["repositories", "code", "issues", "users"],
                    },
                    "max_results": {"type": "integer", "description": "Number of results (1-10, default 5)"},
                    "language": {"type": "string", "description": "Filter by programming language (for repositories)"},
                    "sort": {
                        "type": "string",
                        "description": "Sort order for repositories",
                        "enum": ["stars", "forks", "updated", "best-match"],
                    },
                },
                "required": ["query"],
            },
        },
    },
    # ── WEATHER_TOOLS ─────────────────────────────────────────────────────────
    {
        "category": "WEATHER_TOOLS",
        "type": "function",
        "function": {
            "name": "openweather_current",
            "description": (
                "Get real-time current weather conditions for any city: temperature, "
                "humidity, wind speed, visibility, and cloud cover. "
                "More detailed than the built-in get_weather tool. "
                "Requires OPENWEATHER_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name (e.g. 'Paris', 'New York,US')"},
                    "units": {
                        "type": "string",
                        "description": "Temperature units",
                        "enum": ["metric", "imperial", "standard"],
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "category": "WEATHER_TOOLS",
        "type": "function",
        "function": {
            "name": "openweather_forecast",
            "description": (
                "Get a multi-day weather forecast (up to 5 days) for any city. "
                "Returns daily high/low temperatures, conditions, and humidity. "
                "Requires OPENWEATHER_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name (e.g. 'Tokyo', 'London,GB')"},
                    "days": {"type": "integer", "description": "Number of forecast days (1-5, default 5)"},
                    "units": {
                        "type": "string",
                        "description": "Temperature units",
                        "enum": ["metric", "imperial", "standard"],
                    },
                },
                "required": ["location"],
            },
        },
    },
    # ── MEDIA_TOOLS ───────────────────────────────────────────────────────────
    {
        "category": "MEDIA_TOOLS",
        "type": "function",
        "function": {
            "name": "tmdb_search",
            "description": (
                "Search for movies, TV shows, or people on The Movie Database (TMDB). "
                "Returns titles, ratings, release years, and overviews. "
                "Requires TMDB_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Movie, TV show, or person name to search"},
                    "media_type": {
                        "type": "string",
                        "description": "Type of content to search",
                        "enum": ["multi", "movie", "tv", "person"],
                    },
                    "max_results": {"type": "integer", "description": "Number of results (1-20, default 5)"},
                    "year": {"type": "integer", "description": "Filter by release year (optional)"},
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
            "description": (
                "Get full details for a movie or TV show from TMDB: cast, director, "
                "budget, revenue, genres, runtime, and more. "
                "Use tmdb_search first to get the TMDB ID. "
                "Requires TMDB_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tmdb_id": {"type": "integer", "description": "TMDB numeric ID (from tmdb_search results)"},
                    "media_type": {
                        "type": "string",
                        "description": "Content type",
                        "enum": ["movie", "tv"],
                    },
                },
                "required": ["tmdb_id"],
            },
        },
    },
    # ── KNOWLEDGE_TOOLS ───────────────────────────────────────────────────────
    {
        "category": "KNOWLEDGE_TOOLS",
        "type": "function",
        "function": {
            "name": "wikipedia_search",
            "description": (
                "Search Wikipedia for articles matching a query. "
                "Returns a list of article titles and short descriptions. "
                "No API key required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Number of results (1-20, default 5)"},
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
            "description": (
                "Fetch the full text of a Wikipedia article by exact title. "
                "Returns the complete summary and optionally a specific section. "
                "No API key required. More complete than wiki_get."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Exact Wikipedia article title (e.g. 'Python (programming language)')"},
                    "section": {"type": "string", "description": "Section number to fetch (e.g. '1', '2') — leave empty for summary"},
                },
                "required": ["title"],
            },
        },
    },
]

# ─── Function Dispatcher ──────────────────────────────────────────────────────

EXTERNAL_TOOL_HANDLERS: dict[str, Any] = {
    # YouTube
    "youtube_search":       youtube_search,
    "youtube_transcript":   youtube_transcript,
    "youtube_metadata":     youtube_metadata,
    # Search
    "google_cse_search":    google_cse_search,
    "google_search":        google_search,
    "brave_search":         brave_search,
    # Web
    "firecrawl_scrape":     firecrawl_scrape,
    "firecrawl_crawl":      firecrawl_crawl,
    # News
    "newsapi_headlines":    newsapi_headlines,
    # Code
    "github_search":        github_search,
    # Weather
    "openweather_current":  openweather_current,
    "openweather_forecast": openweather_forecast,
    # Media
    "tmdb_search":          tmdb_search,
    "tmdb_details":         tmdb_details,
    # Knowledge
    "wikipedia_search":     wikipedia_search,
    "wikipedia_article":    wikipedia_article,
}


# ─── Key Requirements Map ─────────────────────────────────────────────────────
# None = no key required (always available)
# str  = env var name that must be set
KEY_REQUIREMENTS: dict[str, str | None] = {
    "youtube_search":       "YOUTUBE_API_KEY",
    "youtube_transcript":   None,               # No key required
    "youtube_metadata":     "YOUTUBE_API_KEY",
    # google_cse_search needs GOOGLE_API_KEY; checked via custom logic below
    "google_cse_search":    "GOOGLE_API_KEY",
    # google_search works with either Google CSE keys OR SerpAPI — always show it
    "google_search":        None,
    "brave_search":         "BRAVE_SEARCH_API_KEY",
    "firecrawl_scrape":     "FIRECRAWL_API_KEY",
    "firecrawl_crawl":      "FIRECRAWL_API_KEY",
    "newsapi_headlines":    "NEWSAPI_KEY",
    "github_search":        None,               # Optional (GITHUB_TOKEN for rate limits)
    "openweather_current":  "OPENWEATHER_API_KEY",
    "openweather_forecast": "OPENWEATHER_API_KEY",
    "tmdb_search":          "TMDB_API_KEY",
    "tmdb_details":         "TMDB_API_KEY",
    "wikipedia_search":     None,               # No key required
    "wikipedia_article":    None,               # No key required
}


def get_available_external_tools() -> list[dict]:
    """
    Return only the external tools whose required API keys are configured.
    Tools with no key requirement are always included.
    """
    available = []
    for tool in EXTERNAL_TOOLS:
        name = tool["function"]["name"]
        required_key = KEY_REQUIREMENTS.get(name)
        if required_key is None or _env(required_key):
            available.append(tool)
    return available


def get_all_external_tools() -> list[dict]:
    """Return all external tool schemas regardless of key availability."""
    return EXTERNAL_TOOLS


def execute_external_tool(tool_name: str, args: dict) -> str:
    """Execute an external tool by name with the given arguments."""
    handler = EXTERNAL_TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return f"❌ Unknown external tool: '{tool_name}'"
    try:
        return handler(**args)
    except TypeError as e:
        return f"❌ Invalid arguments for '{tool_name}': {e}"
    except Exception as e:
        return f"❌ External tool '{tool_name}' failed: {e}"
