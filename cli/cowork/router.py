"""
🧠 Meta-Router: Intent Classification & Tool Schema Filtering
Implements the Brain phase — dynamic tool schema loading via intent classification.
"""

import json
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
    domains.add("CONVERSATIONAL_ONLY")
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

    def _estimate_tool_probability(self, prompt: str) -> float:
        p = prompt.lower()
        action_terms = [
            # English - Search & Info
            "search", "find", "look up", "who is", "what is", "where is", "when did", "latest", "today", "current",
            "news", "weather", "forecast", "temperature", "rain", "snow", "wind", "storm", "price", "stock", "crypto",
            "exchange rate", "calculate", "math", "convert", "formula", "equation", "map", "location", "address",
            # English - Web & Communication
            "scrape", "crawl", "website", "url", "extract", "fetch", "send", "email", "gmail", "mail", "message",
            "post", "tweet", "slack", "telegram", "whatsapp", "linkedin", "browse", "visit", "link",
            # English - Creation & Files
            "create", "generate", "build", "write", "save", "store", "file", "document", "pdf", "docx", "xlsx", "pptx",
            "csv", "json", "xml", "txt", "log", "scratchpad", "remember", "note", "artifact", "workspace",
            # English - Productivity & Coding
            "schedule", "book", "calendar", "event", "meeting", "reminder", "task", "todo", "kanban", "cron",
            "code", "coding", "python", "javascript", "typescript", "react", "html", "css", "github", "repo",
            "git ", "branch", "commit", "push", "pull", "bug", "fix", "refactor", "implement", "deploy", "server",
            "backend", "frontend", "api", "endpoint", "database", "sql", "query", "docker", "container", "linux", "terminal",
            # English - Media & Multimodal
            "image", "picture", "photo", "draw", "video", "youtube", "yt ", "audio", "transcribe", "stt", "tts",
            "vision", "describe", "analyze", "ocr", "diagram", "chart",
            # French - Recherche & Info
            "chercher", "trouver", "qui est", "c'est quoi", "où est", "quand", "dernier", "aujourd'hui", "actuel",
            "nouvelles", "infos", "actualités", "météo", "prévision", "température", "pluie", "neige", "vent", "orage",
            "soleil", "nuage", "froid", "chaud", "humide", "prix", "bourse", "cours de", "calculer", "maths", "convertir",
            "formule", "équation", "carte", "adresse", "journal", "presse",
            # French - Web & Communication
            "extraire", "récupérer", "site web", "lien", "url", "envoyer", "courriel", "mail", "message", "poster",
            "tweeter", "discuter", "naviguer", "parcourir",
            # French - Création & Fichiers
            "créer", "générer", "construire", "écrire", "sauvegarder", "enregistrer", "fichier", "document", "note",
            "mémo", "rappelle", "souviens",
            # French - Productivité & Coding
            "organiser", "réserver", "calendrier", "agenda", "événement", "reunion", "rappel", "tâche", "liste",
            "code", "coder", "programmer", "programmation", "développement", "débugger", "corriger", "réparer",
            "implémenter", "déployer", "serveur", "base de données", "requête", "terminal", "ligne de commande",
            # French - Média & Multimodal
            "photo", "vidéo", "audio", "transcrire", "dessiner", "vision", "décrire", "analyser", "graphique",
            "synthèse vocale", "image",
            # Special tags
            "#code", "#coding", "#web", "#search",
        ]
        has_action = any(t in p for t in action_terms)
        long_turn = len(prompt) > 180
        questiony = ("?" in prompt) and not has_action
        if has_action:
            return 0.75
        if questiony and not long_turn:
            return 0.12
        if questiony:
            return 0.25
        return 0.4

    async def classify(self, prompt: str) -> dict:
        """
        Classify the user's intent.
        Returns: {"categories": [...], "confidence": float, "reasoning": str}
        """
        # Fast-path for small conceptual turns that are unlikely to need tools.
        tool_probability = self._estimate_tool_probability(prompt)
        if tool_probability < 0.2 and len(prompt.strip()) <= 220:
            return {
                "categories": ["CONVERSATIONAL_ONLY"],
                "confidence": 0.9,
                "reasoning": "Fast-path conversational routing (low tool-need probability).",
                "tool_probability": tool_probability,
            }

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
                res["tool_probability"] = tool_probability
                if tool_probability < 0.2:
                    res["categories"] = ["CONVERSATIONAL_ONLY"]
                    res["reasoning"] = "Calibrated to conversational-only after LLM routing failure."
                else:
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

            routed = {
                "categories": valid,
                "confidence": parsed.get("confidence", 0.5),
                "reasoning": parsed.get("reasoning", ""),
            }
            routed["tool_probability"] = tool_probability
            if routed["tool_probability"] < 0.2:
                routed["categories"] = ["CONVERSATIONAL_ONLY"]
                routed["reasoning"] = "Calibrated to conversational-only (low tool-need probability)."
            return routed
        except Exception as e:
            # JSON parse failed — fall back to keyword routing
            res = self._keyword_fallback(prompt)
            res["tool_probability"] = tool_probability
            if tool_probability < 0.2:
                res["categories"] = ["CONVERSATIONAL_ONLY"]
                res["reasoning"] = "Calibrated to conversational-only after fallback."
            else:
                res["reasoning"] = f"Keyword-based fallback (JSON parse error: {e})"
            return res

    def _keyword_fallback(self, prompt: str) -> dict:
        """Keyword-based fallback when LLM routing fails."""
        p = prompt.lower()
        categories = []

        # YouTube & Media
        if any(w in p for w in ["youtube", "yt ", "video transcript", "audio", "vidéo", "transcrire", "speech", "synthèse vocale"]):
            categories.append("YOUTUBE_TOOLS")
        
        # Search & Info
        if any(w in p for w in ["google search", "serpapi", "brave search", "search google", "chercher", "trouver", "recherche"]):
            categories.append("SEARCH_TOOLS")
        
        # Web & Scraping
        if any(w in p for w in ["firecrawl", "scrape", "crawl", "website content", "extract", "website", "site web", "extraire", "lien"]):
            categories.append("WEB_TOOLS")
        
        # News
        if any(w in p for w in ["news", "headlines", "newsapi", "actualités", "nouvelles", "infos"]):
            categories.extend(["NEWS_TOOLS", "SEARCH_TOOLS"])
        
        # Coding (Global)
        if any(w in p for w in [
            "codebase", "source code", "refactor", "debug", "bug fix", "implement", "write code",
            "python", "javascript", "typescript", "react", "next.js", "django", "flask",
            "fastapi", "frontend", "backend", "api endpoint", "unit test", "web app",
            "coder", "programmer", "programmation", "développement", "débugger", "corrigé", "implémenter",
        ]):
            categories.append("CODING_TOOLS")
        
        # Weather
        if any(w in p for w in ["weather", "forecast", "temperature", "météo", "prévision", "température", "pluie", "neige"]):
            categories.append("WEATHER_TOOLS")
        
        # Multi-modal
        if any(w in p for w in [
            "generate image", "create image", "dall-e", "stable diffusion", "make a picture", "draw",
            "transcribe", "stt", "tts", "vision", "describe image", "analyze image", "ocr",
            "générer image", "créer image", "dessiner", "décrire image", "analyser image",
        ]):
            categories.append("MULTIMODAL_TOOLS")

        # Communication & Google
        if any(w in p for w in [
            "email", "smtp", "telegram", "slack", "whatsapp", "twitter", "tweet", "message", "send", "gmail",
            "courriel", "mail", "envoyer", "poster"
        ]):
            categories.extend(["COMMUNICATION_TOOLS", "GOOGLE_TOOLS"])
        
        if any(w in p for w in ["google calendar", "google drive", "gmail", "gdrive", "calendar event", "upload", "agenda", "calendrier"]):
            categories.append("GOOGLE_TOOLS")

        # Workspace & Scratchpad
        if any(w in p for w in ["save", "store", "remember", "scratchpad", "sauvegarder", "enregistrer", "souviens", "rappelle"]):
            categories.append("SESSION_SCRATCHPAD")
        if any(w in p for w in ["workspace", "artifact", "write file", "save file", "fichier", "écrire"]):
            categories.append("WORKSPACE_TOOLS")

        if not categories:
            # General fallbacks
            if any(w in p for w in ["hello", "hi", "hey", "thanks", "thank you", "bonjour", "salut", "merci"]):
                categories = ["CONVERSATIONAL"]
            else:
                categories = ["ALL_TOOLS"]

        return {"categories": categories, "confidence": 0.6, "reasoning": "Keyword-based fallback routing (bilingual update)"}

    def get_category_display(self, categories: list[str]) -> str:
        """Get a display string for the classified categories."""
        parts = []
        for cat in categories:
            if cat in CATEGORY_STYLES:
                parts.append(CATEGORY_STYLES[cat][0])
        return " + ".join(parts) if parts else "[muted]Unknown[/muted]"
