from __future__ import annotations

import re
from typing import Iterable

from .schema import SkillMetadata


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if len(t) > 2}


class SkillRouter:
    """Lightweight intent router over skill metadata."""

    def __init__(self, min_score: float = 0.22) -> None:
        self.min_score = min_score

    def select(
        self,
        user_input: str,
        skills: Iterable[SkillMetadata],
        routed_categories: list[str],
    ) -> tuple[SkillMetadata | None, float]:
        text = (user_input or "").strip()
        if not text:
            return None, 0.0

        # Explicit mention takes precedence: "$skill-name" or plain skill name.
        lower = text.lower()
        for s in skills:
            if f"${s.skill_id}" in lower or f"${s.name.lower()}" in lower:
                return s, 1.0
            if s.name.lower() in lower and len(s.name) >= 4:
                return s, 0.95

        input_tokens = _tokenize(text)
        routed_set = set(routed_categories or [])
        primary_category = routed_categories[0] if routed_categories else ""
        best_skill: SkillMetadata | None = None
        best_score = 0.0

        for s in skills:
            meta_blob = " ".join([s.name, s.description, *s.triggers]).strip()
            skill_tokens = _tokenize(meta_blob)
            if not skill_tokens:
                continue

            overlap = len(input_tokens & skill_tokens)
            lexical = overlap / max(1, len(skill_tokens))

            category_bonus = 0.0
            skill_categories = set(s.tool_categories or [])
            if skill_categories and skill_categories & routed_set:
                category_bonus = 0.35
                # Prefer skills aligned with the router's primary category.
                if primary_category and primary_category in skill_categories:
                    category_bonus += 0.2
                # Prefer tighter skills (single-category skills are less likely to overreach).
                if len(skill_categories) == 1:
                    category_bonus += 0.1

            trigger_bonus = 0.0
            for trg in s.triggers:
                tr = trg.lower().strip()
                if tr and tr in lower:
                    trigger_bonus = max(trigger_bonus, 0.55)

            score = min(1.0, lexical + category_bonus + trigger_bonus)
            if score > best_score:
                best_score = score
                best_skill = s

        if best_skill and best_score >= self.min_score:
            return best_skill, best_score
        return None, 0.0
