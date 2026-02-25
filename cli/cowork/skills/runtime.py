from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .catalog import SkillCatalog
from .router import SkillRouter
from .schema import SkillMetadata
from .trust import SkillTrustEngine, TrustReport


@dataclass
class ActiveSkillContext:
    skill: SkillMetadata | None = None
    score: float = 0.0
    trust: TrustReport | None = None
    instruction_body: str = ""
    resources: list[tuple[str, str]] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return self.skill is not None and self.trust is not None and self.trust.allowed


class SkillRuntime:
    """
    Skill orchestration layer:
    - Always-on metadata catalog (Level 1)
    - Intent-based instruction loading (Level 2)
    - Explicit resource loading directives (Level 3)
    """

    RESOURCE_DIRECTIVE_RE = re.compile(r"LOAD_REF\(([^)]+)\)")

    def __init__(self, config: Any) -> None:
        self.config = config
        self.catalog = SkillCatalog(self._resolve_roots(config))
        self.router = SkillRouter(min_score=float(config.get("skills_router_min_score", 0.22)))
        self.trust_engine = SkillTrustEngine()

    def build_metadata_toc(self) -> str:
        max_skills = int(self.config.get("skills_max_metadata_skills", 64))
        return self.catalog.build_library_toc(max_skills=max_skills)

    def activate(self, user_input: str, routed_categories: list[str]) -> ActiveSkillContext:
        if not bool(self.config.get("skills_enabled", True)):
            return ActiveSkillContext()

        skills = self.catalog.all()
        skill, score = self.router.select(user_input, skills, routed_categories)
        if not skill:
            return ActiveSkillContext()

        max_body_chars = int(self.config.get("skills_instruction_max_chars", 20_000))
        body = self.catalog.load_body(skill, max_chars=max_body_chars)
        trust = self.trust_engine.evaluate(skill, body)
        active = ActiveSkillContext(skill=skill, score=score, trust=trust, instruction_body="")
        if not trust.allowed:
            return active

        if trust.tier >= 2:
            active.instruction_body = body
        if trust.tier >= 2:
            active.resources = self._load_explicit_resources(skill, body)
        return active

    def merge_categories(self, routed_categories: list[str], active: ActiveSkillContext) -> list[str]:
        categories = list(dict.fromkeys(routed_categories))
        if not active.enabled or not active.skill:
            return categories
        if "CONVERSATIONAL_ONLY" in categories:
            return categories
        # Always inject the activated skill's own categories so its tools
        # are available.  Without this, the skill activates but its tools
        # are never loaded because they belong to a category missing from
        # the routed set.
        for c in (active.skill.tool_categories or []):
            if c and c not in categories:
                categories.append(c)
        return categories

    def filter_tools(self, tools_schema: list[dict[str, Any]], active: ActiveSkillContext) -> list[dict[str, Any]]:
        if not active.skill or not active.trust:
            return tools_schema
        return self.trust_engine.filter_tools_by_tier(tools_schema, active.skill, active.trust)

    def build_context_message(self, active: ActiveSkillContext) -> str:
        if not active.skill:
            return ""
        if not active.trust or not active.trust.allowed:
            return (
                f"[SKILL SELECTED BUT BLOCKED]\n"
                f"name={active.skill.name}; score={active.score:.2f}; tier={active.skill.trust_tier}\n"
                f"failed_gates={','.join(active.trust.failed_gates if active.trust else [])}"
            )
        lines = [
            f"### 🔌 Active Skill: {active.skill.name.replace('-', ' ').title()}",
            f"{active.skill.description}",
            "",
            "#### 📖 Instructions",
            active.instruction_body.strip() or "_No specific priority instructions for this task._",
        ]
        if active.resources:
            lines.extend(["", "#### 🔗 Skill Resources"])
            for rel, content in active.resources:
                lines.append(f"**Resource**: `{rel}`\n{content}")
        return "\n".join(lines).strip()

    def _load_explicit_resources(self, skill: SkillMetadata, body: str) -> list[tuple[str, str]]:
        max_resources = int(self.config.get("skills_max_resources_per_activation", 3))
        max_chars = int(self.config.get("skills_resource_max_chars", 10_000))
        found = self.RESOURCE_DIRECTIVE_RE.findall(body or "")
        loaded: list[tuple[str, str]] = []
        for rel in found[:max_resources]:
            rel_path = rel.strip().strip("'\"")
            content = self.catalog.load_resource_text(skill, rel_path, max_chars=max_chars)
            if content:
                loaded.append((rel_path, content))
        return loaded

    @staticmethod
    def _resolve_roots(config: Any) -> list[Path]:
        roots: list[Path] = []
        raw = config.get("skills_paths", [])
        if isinstance(raw, str) and raw.strip():
            roots.append(Path(raw.strip()))
        elif isinstance(raw, list):
            for val in raw:
                if isinstance(val, str) and val.strip():
                    roots.append(Path(val.strip()))

        local_default = Path(__file__).resolve().parent / "library"
        if local_default not in roots:
            roots.append(local_default)
        return roots
