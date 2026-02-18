"""
🧠 Meta-Router: Intent Classification & Tool Schema Filtering
Implements the Brain phase — dynamic tool schema loading via intent classification.
"""

import json
import re
from typing import Any

from .theme import CATEGORY_STYLES, OP_DEFAULTS

# ─── Classification Domains ───────────────────────────────────────────────────
DOMAINS = [
    # ── Built-in ──────────────────────────────────────────────────────────────
    "MEDIA_AND_ENTERTAINMENT",
    "VISION",
    "DATA_AND_UTILITY",
    "SESSION_SCRATCHPAD",
    "APP_CONNECTORS",
    "WORKSPACE_TOOLS",   # Filesystem-backed session workspace (artifacts, notes, context)
    "CONVERSATIONAL",
    "ALL_TOOLS",
    # ── External (Paid API) ───────────────────────────────────────────────────
    "YOUTUBE_TOOLS",    # YouTube Search, Transcript, Metadata (YouTube Data API v3)
    "SEARCH_TOOLS",     # Google Search (SerpAPI), Brave Search
    "WEB_TOOLS",        # Firecrawl scrape & crawl
    "NEWS_TOOLS",       # NewsAPI headlines & search
    "CODE_TOOLS",       # GitHub repository/code/issue search
    "WEATHER_TOOLS",    # OpenWeatherMap current + forecast
    "MEDIA_TOOLS",      # TMDB movie/TV search & details
    "KNOWLEDGE_TOOLS",  # Wikipedia search & full article
    "COMMUNICATION_TOOLS", # Email (SMTP), Telegram, Slack, WhatsApp
    "GOOGLE_TOOLS",     # Google Calendar, Drive, Gmail
    "SOCIAL_TOOLS",     # LinkedIn
]

# ─── Router System Prompt ─────────────────────────────────────────────────────
ROUTER_SYSTEM_PROMPT = """You are a Meta-Router for an enterprise AI agent system.
Your ONLY job is to classify the user's intent and return the relevant tool categories.

Available categories:
- SEARCH_TOOLS: Premium Google Search (SerpAPI) or Brave Search — use for ANY web research or fact-finding
- KNOWLEDGE_TOOLS: Wikipedia article search and full-text retrieval — use for deep research on specific topics
- YOUTUBE_TOOLS: YouTube video search, transcripts, video metadata
- WEB_TOOLS: Firecrawl — use to scrape or read specific websites/URLs provided by the user
- WEATHER_TOOLS: OpenWeatherMap current conditions and multi-day forecasts
- NEWS_TOOLS: News headlines and article search (NewsAPI)
- CODE_TOOLS: GitHub repository, code, and issue search
- MEDIA_AND_ENTERTAINMENT: Images, movies (general), general media
- MEDIA_TOOLS: TMDB movie/TV show search and detailed info (cast, ratings, etc.)
- COMMUNICATION_TOOLS: Email (SMTP), Telegram, Slack, and X (Twitter) posting
- GOOGLE_TOOLS: Google Calendar (list/create), Google Drive (search/upload), Gmail (send)
- SOCIAL_TOOLS: LinkedIn profile/post search
- VISION: Image analysis, OCR
- DATA_AND_UTILITY: Math calculations, charts, diagrams, time/date
- SESSION_SCRATCHPAD: Storing/retrieving large data within the session
- APP_CONNECTORS: Notes, Kanban tasks, calendar events, file storage
- WORKSPACE_TOOLS: Write/read files to the session workspace folder, save notes, update session context, search across sessions
- CONVERSATIONAL: Simple chat, greetings, opinions (NO tools needed)
- ALL_TOOLS: When intent is ambiguous or multiple domains are needed

Respond ONLY with a JSON object in this exact format:
{"categories": ["CATEGORY1", "CATEGORY2"], "confidence": 0.95, "reasoning": "brief reason"}

Rules:
- Return CONVERSATIONAL for greetings, opinions, or simple questions answerable from training data
- Return 1-3 categories maximum (except ALL_TOOLS)
- Prefer specific categories over ALL_TOOLS
- Use SEARCH_TOOLS for general questions needing live data
- Use KNOWLEDGE_TOOLS for "Who is", "What is", "History of" queries
- Use WEB_TOOLS when the user provides a specific link to read
- Use YOUTUBE_TOOLS for anything YouTube-related
- Use MEDIA_TOOLS for specialized movie/TV queries
- Return ALL_TOOLS only when truly ambiguous"""

ROUTER_USER_TEMPLATE = "Classify this user request: {prompt}"


class MetaRouter:
    """
    The Brain: Classifies user intent and returns relevant tool schemas.
    Runs at Temperature 0.0 for maximum determinism.
    """

    def __init__(self, api_client: Any) -> None:
        self.api_client = api_client

    async def classify(self, prompt: str) -> dict:
        """
        Classify the user's intent.
        Returns: {"categories": [...], "confidence": float, "reasoning": str}
        """
        # Truncate very long prompts for routing (Head/Tail truncation)
        if len(prompt) > 2000:
            head = prompt[:800]
            tail = prompt[-400:]
            prompt = f"{head}\n...[TRUNCATED]...\n{tail}"

        messages = [
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": ROUTER_USER_TEMPLATE.format(prompt=prompt)},
        ]

        try:
            result = await self.api_client.chat(
                messages=messages,
                temperature=OP_DEFAULTS["temperature_router"],
                response_format={"type": "json_object"},
                max_tokens=200,
            )
            content = result.get("content", "{}")
            parsed = json.loads(content)
            categories = parsed.get("categories", ["ALL_TOOLS"])
            # Validate categories
            valid = [c for c in categories if c in DOMAINS]
            if not valid:
                valid = ["ALL_TOOLS"]
            return {
                "categories": valid,
                "confidence": parsed.get("confidence", 0.5),
                "reasoning": parsed.get("reasoning", ""),
            }
        except Exception:
            # Fallback: simple keyword-based routing
            return self._keyword_fallback(prompt)

    def _keyword_fallback(self, prompt: str) -> dict:
        """Keyword-based fallback when LLM routing fails."""
        p = prompt.lower()
        categories = []

        # External tool keywords (checked first for specificity)
        if any(w in p for w in ["youtube", "yt ", "video transcript", "youtube search", "youtube metadata"]):
            categories.append("YOUTUBE_TOOLS")
        if any(w in p for w in ["google search", "serpapi", "brave search", "search google"]):
            categories.append("SEARCH_TOOLS")
        if any(w in p for w in ["firecrawl", "scrape", "crawl", "website content", "extract from url"]):
            categories.append("WEB_TOOLS")
        if any(w in p for w in ["news", "headlines", "breaking news", "newsapi", "latest news"]):
            categories.append("NEWS_TOOLS")
        if any(w in p for w in ["github", "repository", "open source", "code search", "pull request", "issue"]):
            categories.append("CODE_TOOLS")
        if any(w in p for w in ["weather", "forecast", "temperature", "humidity", "openweather", "rain", "snow", "wind"]):
            categories.append("WEATHER_TOOLS")
        if any(w in p for w in ["movie", "film", "tv show", "series", "tmdb", "cast", "director", "imdb", "actor", "actress"]):
            categories.append("MEDIA_TOOLS")
        if any(w in p for w in ["wikipedia", "wiki article", "encyclopedia", "who was", "what is the history"]):
            categories.append("KNOWLEDGE_TOOLS")
        if any(w in p for w in ["email", "smtp", "telegram", "slack", "whatsapp", "twitter", "tweet", "post to x", "message", "send to"]):
            categories.append("COMMUNICATION_TOOLS")
        if any(w in p for w in ["google calendar", "google drive", "gmail", "gdrive", "calendar event", "upload to drive", "create event"]):
            categories.append("GOOGLE_TOOLS")
        if any(w in p for w in ["linkedin", "professional profile"]):
            categories.append("SOCIAL_TOOLS")

        # Built-in tool keywords
        if not categories:
            if any(w in p for w in ["search", "find", "look up", "what is", "who is", "when did", "weather"]):
                categories.append("SEARCH_AND_INFO")
            if any(w in p for w in ["calculate", "compute", "math", "formula", "equation", "time", "date", "diagram", "chart"]):
                categories.append("DATA_AND_UTILITY")
            if any(w in p for w in ["save", "store", "remember", "scratchpad", "ref:"]):
                categories.append("SESSION_SCRATCHPAD")
            if any(w in p for w in ["workspace", "artifact", "write file", "save file", "session note", "context.md"]):
                categories.append("WORKSPACE_TOOLS")
            if any(w in p for w in ["note", "task", "kanban", "calendar", "event", "file", "write"]):
                categories.append("APP_CONNECTORS")
            if any(w in p for w in ["image", "picture", "photo", "movie"]):
                categories.append("MEDIA_AND_ENTERTAINMENT")
            if any(w in p for w in ["analyze", "look at", "describe", "vision", "ocr"]):
                categories.append("VISION")

        if not categories:
            # Check if it's conversational
            if any(w in p for w in ["hello", "hi", "hey", "thanks", "thank you", "how are you", "what do you think"]):
                categories = ["CONVERSATIONAL"]
            else:
                categories = ["ALL_TOOLS"]

        return {"categories": categories, "confidence": 0.6, "reasoning": "Keyword-based fallback routing"}

    def get_category_display(self, categories: list[str]) -> str:
        """Get a display string for the classified categories."""
        parts = []
        for cat in categories:
            if cat in CATEGORY_STYLES:
                parts.append(CATEGORY_STYLES[cat][0])
        return " + ".join(parts) if parts else "[muted]Unknown[/muted]"
