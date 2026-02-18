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
    "SEARCH_AND_INFO",
    "MEDIA_AND_ENTERTAINMENT",
    "VISION",
    "DATA_AND_UTILITY",
    "SESSION_SCRATCHPAD",
    "APP_CONNECTORS",
    "CONVERSATIONAL",
    "ALL_TOOLS",
]

# ─── Router System Prompt ─────────────────────────────────────────────────────
ROUTER_SYSTEM_PROMPT = """You are a Meta-Router for an enterprise AI agent system.
Your ONLY job is to classify the user's intent and return the relevant tool categories.

Available categories:
- SEARCH_AND_INFO: Web search, Wikipedia, URL scraping, weather, real-time data
- MEDIA_AND_ENTERTAINMENT: Images, YouTube, movies
- VISION: Image analysis, OCR
- DATA_AND_UTILITY: Math calculations, charts, diagrams, time/date
- SESSION_SCRATCHPAD: Storing/retrieving large data within the session
- APP_CONNECTORS: Notes, Kanban tasks, calendar events, file storage
- CONVERSATIONAL: Simple chat, greetings, opinions (NO tools needed)
- ALL_TOOLS: When intent is ambiguous or multiple domains are needed

Respond ONLY with a JSON object in this exact format:
{"categories": ["CATEGORY1", "CATEGORY2"], "confidence": 0.95, "reasoning": "brief reason"}

Rules:
- Return CONVERSATIONAL for greetings, opinions, or simple questions answerable from training data
- Return 1-3 categories maximum (except ALL_TOOLS)
- Prefer specific categories over ALL_TOOLS
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

        if any(w in p for w in ["search", "find", "look up", "what is", "who is", "when did", "weather", "news"]):
            categories.append("SEARCH_AND_INFO")
        if any(w in p for w in ["calculate", "compute", "math", "formula", "equation", "time", "date", "diagram", "chart"]):
            categories.append("DATA_AND_UTILITY")
        if any(w in p for w in ["save", "store", "remember", "scratchpad", "ref:"]):
            categories.append("SESSION_SCRATCHPAD")
        if any(w in p for w in ["note", "task", "kanban", "calendar", "event", "file", "write"]):
            categories.append("APP_CONNECTORS")
        if any(w in p for w in ["image", "picture", "photo", "video", "youtube", "movie"]):
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
