from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillMetadata:
    name: str
    description: str
    path: Path
    triggers: list[str] = field(default_factory=list)
    tool_categories: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    trust_tier: int = 1
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def skill_id(self) -> str:
        return self.name.strip().lower().replace(" ", "-")

    @property
    def skill_file(self) -> Path:
        return self.path / "SKILL.md"

