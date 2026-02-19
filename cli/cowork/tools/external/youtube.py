"""
🎬 YouTube Tools
Implementations for searching and getting metadata/transcripts from YouTube.
"""

import re
import urllib.parse
from .utils import _env, _missing_key, _http_get, _TTL_SEARCH, _TTL_METADATA

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
    No API key needed (uses youtube-transcript-api).
    """
    if "youtube.com" in video_id or "youtu.be" in video_id:
        match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", video_id)
        if match:
            video_id = match.group(1)
        else:
            return f"Could not extract video ID from URL: {video_id}"

    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        
        if hasattr(YouTubeTranscriptApi, 'get_transcript'):
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[language, "en"])
            full_text = " ".join(entry["text"] for entry in transcript_list)
            duration_secs = sum(entry.get("duration", 0) for entry in transcript_list)
        else:
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
        return "❌ `youtube-transcript-api` not installed. Run: pip install youtube-transcript-api"
    except Exception as e:
        return f"Transcript fetch failed for '{video_id}': {e}"

def youtube_metadata(video_id: str) -> str:
    """
    Fetch detailed metadata for a YouTube video.
    Requires: YOUTUBE_API_KEY
    """
    api_key = _env("YOUTUBE_API_KEY")
    if not api_key:
        return _missing_key("youtube_metadata", "YOUTUBE_API_KEY")

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
        duration = details.get("duration", "PT0S")
        views = stats.get("viewCount", "0")
        likes = stats.get("likeCount", "0")
        comments = stats.get("commentCount", "0")

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
            f"**URL**: https://www.youtube.com/watch?v={video_id}\n\n"
            f"**Description**:\n{description}..."
        )
    except Exception as e:
        return f"YouTube metadata fetch failed: {e}"

TOOLS = [
    {
        "category": "YOUTUBE_TOOLS",
        "type": "function",
        "function": {
            "name": "youtube_search",
            "description": "Search YouTube for videos matching a query.",
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
            "description": "Fetch the full transcript/captions of a YouTube video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "description": "YouTube video URL or video ID"},
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
            "description": "Fetch detailed metadata for a YouTube video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "description": "YouTube video URL or video ID"},
                },
                "required": ["video_id"],
            },
        },
    },
]
