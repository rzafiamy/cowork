from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import yaml

from .schema import SkillMetadata

_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _normalize_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


class SkillCatalog:
    """Discovers and parses SKILL.md packages from configured roots."""

    def __init__(self, roots: Iterable[Path]) -> None:
        self.roots = [Path(r) for r in roots]
        self._skills: list[SkillMetadata] = []
        self._loaded = False

    def reload(self) -> None:
        self._skills = []
        for root in self.roots:
            if not root.exists() or not root.is_dir():
                continue
            for skill_md in root.rglob("SKILL.md"):
                parsed = self._parse_skill_file(skill_md)
                if parsed:
                    self._skills.append(parsed)
        self._skills.sort(key=lambda s: s.name.lower())
        self._loaded = True

    def all(self) -> list[SkillMetadata]:
        if not self._loaded:
            self.reload()
        return list(self._skills)

    def get(self, skill_name: str) -> SkillMetadata | None:
        target = (skill_name or "").strip().lower()
        if not target:
            return None
        for skill in self.all():
            if skill.name.lower() == target or skill.skill_id == target:
                return skill
        return None

    def build_library_toc(self, max_skills: int = 64, max_desc_chars: int = 140) -> str:
        skills = self.all()[:max_skills]
        if not skills:
            return "(No skills loaded)"
        lines = []
        for s in skills:
            desc = (s.description or "").strip().replace("\n", " ")
            if len(desc) > max_desc_chars:
                desc = desc[: max_desc_chars - 3] + "..."
            lines.append(f"- {s.name}: {desc}")
        return "\n".join(lines)

    def load_body(self, skill: SkillMetadata, max_chars: int = 24_000) -> str:
        try:
            text = skill.skill_file.read_text(encoding="utf-8")
        except Exception:
            return ""

        match = _FRONTMATTER_RE.match(text)
        body = text[match.end() :] if match else text
        body = body.strip()
        if len(body) > max_chars:
            body = body[: max_chars - 18] + "\n...[TRUNCATED]..."
        return body

    def load_resource_text(self, skill: SkillMetadata, rel_path: str, max_chars: int = 14_000) -> str:
        rel = (rel_path or "").strip().lstrip("/")
        if not rel:
            return ""
        full = (skill.path / rel).resolve()
        try:
            if not str(full).startswith(str(skill.path.resolve())):
                return ""
            if not full.exists() or not full.is_file():
                return ""
            content = full.read_text(encoding="utf-8")
        except Exception:
            return ""
        if len(content) > max_chars:
            content = content[: max_chars - 18] + "\n...[TRUNCATED]..."
        return content

    def _parse_skill_file(self, skill_md: Path) -> SkillMetadata | None:
        try:
            text = skill_md.read_text(encoding="utf-8")
        except Exception:
            return None

        match = _FRONTMATTER_RE.match(text)
        if not match:
            return None

        try:
            frontmatter = yaml.safe_load(match.group(1)) or {}
        except Exception:
            return None

        name = str(frontmatter.get("name", "")).strip()
        description = str(frontmatter.get("description", "")).strip()
        if not name or not description:
            return None

        trust_tier = frontmatter.get("trust_tier", 1)
        try:
            trust_tier_int = int(trust_tier)
        except Exception:
            trust_tier_int = 1
        trust_tier_int = max(1, min(4, trust_tier_int))

        manifest = frontmatter.get("permissions", {}) or {}
        categories = _normalize_str_list(frontmatter.get("tool_categories"))
        allowed_tools = _normalize_str_list(manifest.get("tools"))
        if not categories:
            categories = _normalize_str_list(manifest.get("categories"))

        return SkillMetadata(
            name=name,
            description=description,
            path=skill_md.parent,
            triggers=_normalize_str_list(frontmatter.get("triggers")),
            tool_categories=categories,
            allowed_tools=allowed_tools,
            trust_tier=trust_tier_int,
            manifest=manifest if isinstance(manifest, dict) else {},
        )

