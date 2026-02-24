from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .schema import SkillMetadata

SUSPICIOUS_PATTERNS = [
    r"rm\s+-rf",
    r"curl\s+.+\|\s*sh",
    r"wget\s+.+\|\s*bash",
    r"os\.system\(",
    r"subprocess\.(Popen|run)\(",
    r"eval\(",
]


@dataclass
class TrustReport:
    allowed: bool
    tier: int
    failed_gates: list[str]
    notes: list[str]


def is_read_only_tool(tool: dict[str, Any]) -> bool:
    fn = tool.get("function", {})
    name = str(fn.get("name", "")).lower()
    verbs_read = ("list", "read", "search", "grep", "get", "find", "status", "show")
    verbs_write = ("write", "create", "update", "delete", "edit", "append", "save", "schedule", "send", "upload")
    if any(v in name for v in verbs_write):
        return False
    return any(v in name for v in verbs_read)


def is_mutating_tool(tool: dict[str, Any]) -> bool:
    """
    Conservative mutation detector used for Tier-2 controls.
    Blocks known write/action verbs, but allows informational tools whose
    names do not include explicit read verbs (e.g., openweather_current).
    """
    name = str(tool.get("function", {}).get("name", "")).lower()
    mutating_verbs = (
        "write", "create", "update", "delete", "edit", "append", "save",
        "schedule", "send", "upload", "push", "commit", "clone", "init",
        "download", "convert", "generate",
    )
    return any(v in name for v in mutating_verbs)


def is_code_execution_tool(tool: dict[str, Any]) -> bool:
    name = str(tool.get("function", {}).get("name", "")).lower()
    return any(k in name for k in ("bash", "shell", "run_command", "execute"))


def is_network_tool(tool: dict[str, Any]) -> bool:
    category = str(tool.get("category", "")).upper()
    network_categories = {
        "SEARCH_TOOLS",
        "WEB_TOOLS",
        "NEWS_TOOLS",
        "WEATHER_TOOLS",
        "MEDIA_TOOLS",
        "KNOWLEDGE_TOOLS",
        "COMMUNICATION_TOOLS",
        "GOOGLE_TOOLS",
        "SOCIAL_TOOLS",
        "NEXTCLOUD_TOOLS",
        "YOUTUBE_TOOLS",
        "GIT_TOOLS",
    }
    return category in network_categories


class SkillTrustEngine:
    """Gate-based trust checks with tier capability enforcement."""

    def evaluate(self, skill: SkillMetadata, body: str) -> TrustReport:
        failed: list[str] = []
        notes: list[str] = []

        # Gate 1: static analysis
        matched = [pat for pat in SUSPICIOUS_PATTERNS if re.search(pat, body or "", re.IGNORECASE)]
        if matched:
            failed.append("gate1_static_analysis")
            notes.append(f"Suspicious patterns found: {', '.join(matched[:3])}")

        # Gate 2: semantic consistency (lightweight heuristic)
        desc_tokens = set(re.findall(r"[a-zA-Z0-9_]+", (skill.description or "").lower()))
        body_tokens = set(re.findall(r"[a-zA-Z0-9_]+", (body or "").lower()))
        overlap = len(desc_tokens & body_tokens)
        if desc_tokens and overlap <= 1 and skill.trust_tier >= 2:
            failed.append("gate2_semantic_classification")
            notes.append("Skill description and body are weakly aligned.")

        # Gate 4: manifest validation (basic schema)
        manifest = skill.manifest or {}
        if manifest and not isinstance(manifest, dict):
            failed.append("gate4_manifest_validation")
            notes.append("Permissions manifest must be an object.")
        else:
            for key in ("tools", "categories"):
                val = manifest.get(key)
                if val is not None and not isinstance(val, list):
                    failed.append("gate4_manifest_validation")
                    notes.append(f"permissions.{key} must be a list.")
                    break

        tier = max(1, min(4, skill.trust_tier))
        if tier == 1 and failed and "gate1_static_analysis" in failed:
            return TrustReport(False, tier, failed, notes)
        if tier >= 2 and any(g in failed for g in ("gate1_static_analysis", "gate2_semantic_classification")):
            return TrustReport(False, tier, failed, notes)
        if "gate4_manifest_validation" in failed:
            return TrustReport(False, tier, failed, notes)
        return TrustReport(True, tier, failed, notes)

    def filter_tools_by_tier(
        self,
        tools_schema: list[dict[str, Any]],
        skill: SkillMetadata,
        report: TrustReport,
    ) -> list[dict[str, Any]]:
        if not report.allowed:
            return []
        tier = report.tier
        filtered = list(tools_schema)

        if tier == 1:
            return []
        if tier == 2:
            filtered = [t for t in filtered if not is_code_execution_tool(t) and not is_mutating_tool(t)]
        elif tier == 3:
            filtered = [t for t in filtered if not is_network_tool(t)]

        allowed_categories = set(skill.tool_categories or [])
        allowed_tools = set(skill.allowed_tools or [])
        if allowed_categories:
            filtered = [t for t in filtered if str(t.get("category", "")) in allowed_categories]
        if allowed_tools:
            filtered = [t for t in filtered if str(t.get("function", {}).get("name", "")) in allowed_tools]

        return filtered
