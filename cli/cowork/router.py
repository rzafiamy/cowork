"""
🧠 Meta-Router: Intent Classification & Tool Schema Filtering
Implements the Brain phase — dynamic tool schema loading via intent classification.
"""

import json
import re
from typing import Any, Optional

from .prompts import ROUTER_CATEGORY_DESCRIPTIONS, ROUTER_SYSTEM_TEMPLATE, ROUTER_USER_TEMPLATE
from .theme import CATEGORY_STYLES, OP_DEFAULTS
from .tools import get_all_available_tools

def get_supported_domains() -> list[str]:
    """Get list of categories that have at least one available tool."""
    available_tools = get_all_available_tools()
    domains = set()
    for tool in available_tools:
        domains.add(tool["category"])
    
    # Always include special categories
    domains.add("CONVERSATIONAL")
    domains.add("ALL_TOOLS")
    
    return sorted(list(domains))

# ─── Prompts are centralized in prompts.py ───────────────────────────────────
# Import: ROUTER_CATEGORY_DESCRIPTIONS, ROUTER_SYSTEM_TEMPLATE, ROUTER_USER_TEMPLATE


class MetaRouter:
    """
    The Brain: Classifies user intent and returns relevant tool schemas.
    Runs at Temperature 0.0 for maximum determinism.
    """

    def __init__(self, api_client: Any, model: str = "gpt-4o-mini") -> None:
        self.api_client = api_client
        self.model = model

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

        # Build dynamic system prompt
        domains = get_supported_domains()
        category_lines = []
        for d in domains:
            desc = ROUTER_CATEGORY_DESCRIPTIONS.get(d, "No description available")
            category_lines.append(f"- {d}: {desc}")
        
        category_list_str = "\n".join(category_lines)
        system_prompt = ROUTER_SYSTEM_TEMPLATE.format(category_list=category_list_str)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": ROUTER_USER_TEMPLATE.format(prompt=prompt)},
        ]

        first_error: Optional[Exception] = None
        result = None

        # Attempt 1: With JSON mode (best for OpenAI-compatible endpoints)
        try:
            result = await self.api_client.chat(
                messages=messages,
                model=self.model,
                temperature=OP_DEFAULTS["temperature_router"],
                response_format={"type": "json_object"},
                max_tokens=200,
            )
        except Exception as e1:
            first_error = e1

        # Attempt 2: Without JSON mode (fallback for local models / proxies that
        # don't support response_format, e.g. Gemini OpenAI-compat layer)
        if result is None:
            try:
                result = await self.api_client.chat(
                    messages=messages,
                    model=self.model,
                    temperature=OP_DEFAULTS["temperature_router"],
                    max_tokens=200,
                )
            except Exception as e2:
                # Both attempts failed — fall back to keyword routing
                err = first_error or e2
                err_msg = str(err)
                if "not_found_error" in err_msg.lower() or "404" in err_msg:
                    hint = f"Model '{self.model}' not found — check model_router in config."
                elif "401" in err_msg or "unauthorized" in err_msg.lower() or "invalid_api_key" in err_msg.lower():
                    hint = "Invalid API key — check api_key in config."
                elif "403" in err_msg or "forbidden" in err_msg.lower():
                    hint = "API key not authorized for this endpoint."
                else:
                    hint = err_msg[:80] + "..." if len(err_msg) > 80 else err_msg

                res = self._keyword_fallback(prompt)
                res["reasoning"] = f"Keyword-based fallback (LLM routing failed: {hint})"
                return res

        try:
            content = result.get("content", "{}")

            # Extract JSON if not clean (sometimes models ignore the Respond ONLY instruction)
            if "{" in content:
                content = content[content.find("{"):content.rfind("}")+1]

            parsed = json.loads(content)
            categories = parsed.get("categories", ["ALL_TOOLS"])
            # Validate categories
            valid = [c for c in categories if c in domains]
            if not valid:
                valid = ["ALL_TOOLS"]

            # Heuristic: Inject SEARCH_TOOLS for specific data domains to ensure fallback
            # (In case the specific tool's API key is missing)
            if any(c in valid for c in ["NEWS_TOOLS", "WEATHER_TOOLS", "WEB_TOOLS"]):
                if "SEARCH_TOOLS" not in valid:
                    valid.append("SEARCH_TOOLS")

            return {
                "categories": valid,
                "confidence": parsed.get("confidence", 0.5),
                "reasoning": parsed.get("reasoning", ""),
            }
        except Exception as e:
            # JSON parse failed — fall back to keyword routing
            res = self._keyword_fallback(prompt)
            res["reasoning"] = f"Keyword-based fallback (JSON parse error: {e})"
            return res

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
            categories.extend(["NEWS_TOOLS", "SEARCH_TOOLS"])
        if any(w in p for w in ["github", "repository", "open source", "code search", "pull request", "issue"]):
            categories.append("CODE_TOOLS")
        if any(w in p for w in ["weather", "forecast", "temperature", "humidity", "openweather", "rain", "snow", "wind"]):
            categories.append("WEATHER_TOOLS")
        if any(w in p for w in ["movie", "film", "tv show", "series", "tmdb", "cast", "director", "imdb", "actor", "actress"]):
            categories.append("MEDIA_TOOLS")
        if any(w in p for w in ["wikipedia", "wiki article", "encyclopedia", "who was", "what is the history"]):
            categories.append("KNOWLEDGE_TOOLS")
        if any(w in p for w in ["email", "smtp", "telegram", "slack", "whatsapp", "twitter", "tweet", "post to x", "message", "send to", "gmail"]):
            categories.extend(["COMMUNICATION_TOOLS", "GOOGLE_TOOLS"])
        if any(w in p for w in ["google calendar", "google drive", "gmail", "gdrive", "calendar event", "upload to drive", "create event"]):
            categories.append("GOOGLE_TOOLS")
        if any(w in p for w in ["linkedin", "professional profile"]):
            categories.append("SOCIAL_TOOLS")

        # Multi-modal intent keywords
        if any(w in p for w in [
            "generate image", "image generation", "create image", "dall-e", "dalle",
            "stable diffusion", "text to image", "make a picture", "draw",
            "transcribe", "speech to text", "stt", "asr", "whisper", "audio transcription",
            "convert audio", "audio to text",
            "text to speech", "tts", "synthesize speech", "read aloud", "speak",
            "vision", "describe image", "analyze image", "ocr", "image analysis",
            "look at this image", "what is in this", "what does this image",
        ]):
            categories.append("MULTIMODAL_TOOLS")

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
            if any(w in p for w in ["cron", "schedule", "remind me", "every day", "daily", "weekly", "tomorrow at"]):
                categories.append("CRON_TOOLS")
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
