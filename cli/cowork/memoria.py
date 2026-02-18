"""
🧠 Memoria: Hybrid Long-Term Memory System
Implements the Knowledge Graph + Session Summary memory framework.
Uses local JSON storage (no external vector DB required for CLI).
"""

import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import CONFIG_DIR
from .theme import OP_DEFAULTS

MEMORIA_DIR = CONFIG_DIR / "memoria"
MEMORIA_DIR.mkdir(exist_ok=True)

# ─── Prompts ──────────────────────────────────────────────────────────────────

TRIPLET_EXTRACTION_PROMPT = """Extract factual knowledge triplets from the following user message.
Return ONLY a JSON array of triplets. Each triplet must have: subject, predicate, object.
Focus on facts about the user, their preferences, goals, and context.
If there are no extractable facts, return an empty array [].

Message: {message}

Return format: [{{"subject": "...", "predicate": "...", "object": "..."}}]"""

SESSION_SUMMARY_PROMPT = """Update the session summary with the latest interaction.

Current Summary:
{current_summary}

New Interaction:
User: {user_message}
Assistant: {assistant_response}

Provide an updated, concise summary (under 200 words) capturing:
1. Main topics discussed
2. Key decisions or preferences expressed
3. Ongoing context and goals

Return ONLY the updated summary text."""

CONTEXT_FUSION_TEMPLATE = """📝 SESSION CONTEXT:
{summary}

🧩 PERSONA KNOWLEDGE:
{triplets}"""


class Memoria:
    """
    Hybrid memory system combining:
    - Knowledge Graph (triplets) stored as local JSON
    - Session summaries for rolling conversation context
    - EWA temporal decay for relevance weighting
    """

    def __init__(self, user_id: str, session_id: str, api_client: Any, config: Any) -> None:
        self.user_id = user_id
        self.session_id = session_id
        self.api_client = api_client
        self.config = config
        self.decay_rate = config.get("decay_rate", OP_DEFAULTS["decay_rate"])
        self.top_k = config.get("top_k_memories", OP_DEFAULTS["top_k_memories"])

        # Storage paths
        self._kg_path = MEMORIA_DIR / f"kg_{user_id}.json"
        self._summary_path = MEMORIA_DIR / f"summary_{session_id}.json"

        self._kg: list[dict] = self._load_kg()
        self._summary: str = self._load_summary()

    # ── Storage I/O ───────────────────────────────────────────────────────────

    def _load_kg(self) -> list[dict]:
        if self._kg_path.exists():
            try:
                with open(self._kg_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_kg(self) -> None:
        with open(self._kg_path, "w") as f:
            json.dump(self._kg, f, indent=2)

    def _load_summary(self) -> str:
        if self._summary_path.exists():
            try:
                with open(self._summary_path) as f:
                    data = json.load(f)
                return data.get("summary", "")
            except Exception:
                pass
        return ""

    def _save_summary(self) -> None:
        with open(self._summary_path, "w") as f:
            json.dump({
                "session_id": self.session_id,
                "summary": self._summary,
                "updated_at": datetime.utcnow().isoformat(),
            }, f, indent=2)

    # ── Read Path ─────────────────────────────────────────────────────────────

    def get_fused_context(self, query: str) -> str:
        """
        Retrieve relevant context for the current query.
        Combines session summary + weighted persona triplets.
        """
        summary = self._summary
        triplets = self._get_weighted_triplets(query)

        if not summary and not triplets:
            return ""

        triplet_lines = []
        for t in triplets[:self.top_k]:
            weight = t.get("weight", 0.5)
            triplet_lines.append(
                f"  • {t['subject']} {t['predicate']} {t['object']} (relevance: {weight:.2f})"
            )

        triplets_str = "\n".join(triplet_lines) if triplet_lines else "  (No persona facts yet)"
        summary_str = summary if summary else "(No session summary yet)"

        return CONTEXT_FUSION_TEMPLATE.format(
            summary=summary_str,
            triplets=triplets_str,
        )

    def _get_weighted_triplets(self, query: str) -> list[dict]:
        """
        Semantic search via keyword matching + EWA temporal decay.
        (Local implementation — no vector DB required.)
        """
        if not self._kg:
            return []

        query_words = set(re.findall(r'\w+', query.lower()))
        now = datetime.utcnow()
        weighted = []

        for triplet in self._kg:
            # Compute keyword similarity
            triplet_text = f"{triplet['subject']} {triplet['predicate']} {triplet['object']}".lower()
            triplet_words = set(re.findall(r'\w+', triplet_text))
            overlap = len(query_words & triplet_words)
            similarity = min(1.0, overlap / max(len(query_words), 1))

            # Apply EWA temporal decay
            created_at_str = triplet.get("created_at", now.isoformat())
            try:
                created_at = datetime.fromisoformat(created_at_str)
            except Exception:
                created_at = now
            delta_min = (now - created_at).total_seconds() / 60.0
            weight = similarity * math.exp(-self.decay_rate * delta_min)

            # Always include triplets with some relevance
            if weight > 0.001 or similarity > 0:
                weighted.append({**triplet, "weight": weight, "similarity": similarity})

        # Sort by weight descending
        weighted.sort(key=lambda t: t["weight"], reverse=True)
        return weighted

    # ── Write Path ────────────────────────────────────────────────────────────

    async def update(self, user_message: str, assistant_response: str) -> None:
        """
        Non-blocking memory update (called in background).
        Extracts triplets and updates session summary in parallel.
        """
        if not user_message:
            return
        try:
            import asyncio
            await asyncio.gather(
                self._process_triplets(user_message),
                self._update_session_summary(user_message, assistant_response),
            )
        except Exception:
            pass  # Memory failures are non-fatal

    async def _process_triplets(self, user_message: str) -> None:
        """Extract knowledge triplets from user message and save to KG."""
        try:
            prompt = TRIPLET_EXTRACTION_PROMPT.format(message=user_message)
            result = await self.api_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.get("model_text"),
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=500,
            )
            content = result.get("content", "[]")

            # Robust JSON parsing
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    triplets = parsed
                elif isinstance(parsed, dict):
                    triplets = parsed.get("triplets", [])
                else:
                    triplets = []
            except json.JSONDecodeError:
                # Try to extract JSON array from text
                match = re.search(r'\[.*\]', content, re.DOTALL)
                triplets = json.loads(match.group()) if match else []

            # Insert new triplets
            import uuid
            for t in triplets:
                if isinstance(t, dict) and all(k in t for k in ("subject", "predicate", "object")):
                    self._kg.append({
                        "id": str(uuid.uuid4()),
                        "user_id": self.user_id,
                        "subject": str(t["subject"])[:200],
                        "predicate": str(t["predicate"])[:200],
                        "object": str(t["object"])[:200],
                        "created_at": datetime.utcnow().isoformat(),
                    })

            self._save_kg()
        except Exception:
            pass

    async def _update_session_summary(self, user_message: str, assistant_response: str) -> None:
        """Update the rolling session summary."""
        if not assistant_response:
            return
        try:
            prompt = SESSION_SUMMARY_PROMPT.format(
                current_summary=self._summary or "(none yet)",
                user_message=user_message[:500],
                assistant_response=assistant_response[:1000],
            )
            result = await self.api_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.get("model_compress"),
                temperature=OP_DEFAULTS["temperature_compress"],
                max_tokens=300,
            )
            new_summary = result.get("content", "").strip()
            if new_summary:
                self._summary = new_summary
                self._save_summary()
        except Exception:
            pass

    # ── Utility ───────────────────────────────────────────────────────────────

    def get_triplet_count(self) -> int:
        return len(self._kg)

    def get_summary(self) -> str:
        return self._summary

    def clear_session(self) -> None:
        """Clear session summary (keep KG)."""
        self._summary = ""
        if self._summary_path.exists():
            self._summary_path.unlink()

    def clear_all(self) -> None:
        """Clear all memory for this user."""
        self._kg = []
        self._summary = ""
        self._save_kg()
        if self._summary_path.exists():
            self._summary_path.unlink()
