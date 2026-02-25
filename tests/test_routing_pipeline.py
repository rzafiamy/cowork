"""
🧪 Unit Tests — Routing & Skill Pipeline
Verifies the fixes to the routing, skill activation, and trust filtering pipeline.
These tests are deterministic and do NOT require a running LLM.

Run:  python3 tests/test_routing_pipeline.py
"""

import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Setup path
project_root = Path(__file__).parent.parent
cli_dir = project_root / "cli"
sys.path.insert(0, str(cli_dir))

# Load .env so external tool availability checks work
from dotenv import load_dotenv
load_dotenv(cli_dir / ".env")


# ─── Router Tests ─────────────────────────────────────────────────────────────

class TestToolProbabilityEstimator(unittest.TestCase):
    """Verify that _estimate_tool_probability doesn't misclassify data-like inputs."""

    def setUp(self):
        from cowork.router import MetaRouter
        self.router = MetaRouter(MagicMock(), model="fake")

    def test_email_address_not_conversational(self):
        prob = self.router._estimate_tool_probability("plola@infodev.ovh")
        self.assertGreaterEqual(prob, 0.5, "Email address should not be fast-pathed to conversational")

    def test_url_not_conversational(self):
        prob = self.router._estimate_tool_probability("https://example.com/page")
        self.assertGreaterEqual(prob, 0.5, "URL should not be fast-pathed to conversational")

    def test_file_path_not_conversational(self):
        prob = self.router._estimate_tool_probability("/home/user/report.pdf")
        self.assertGreaterEqual(prob, 0.5, "File path should not be fast-pathed to conversational")

    def test_session_context_prefix(self):
        prompt = "[SESSION CONTEXT: user: find youtube videos] Current user message: plola@infodev.ovh"
        prob = self.router._estimate_tool_probability(prompt)
        self.assertGreaterEqual(prob, 0.6, "Session context prefix should elevate probability")

    def test_greeting_still_low(self):
        prob = self.router._estimate_tool_probability("hello")
        self.assertLess(prob, 0.5, "Greeting should remain low probability")

    def test_question_still_low(self):
        prob = self.router._estimate_tool_probability("how are you?")
        self.assertLess(prob, 0.2, "Simple question should still be low probability")

    def test_action_term_high(self):
        prob = self.router._estimate_tool_probability("search for python tutorials")
        self.assertGreaterEqual(prob, 0.7, "Action terms should return high probability")


class TestKeywordFallback(unittest.TestCase):
    """Verify keyword fallback maps chart/plot/graph to DATA_AND_UTILITY."""

    def setUp(self):
        from cowork.router import MetaRouter
        self.router = MetaRouter(MagicMock(), model="fake")

    def test_chart_keyword(self):
        result = self.router._keyword_fallback("create a chart of my data")
        self.assertIn("DATA_AND_UTILITY", result["categories"])

    def test_plotchar_keyword(self):
        result = self.router._keyword_fallback("generate a plotchart of temperatures")
        self.assertIn("DATA_AND_UTILITY", result["categories"])

    def test_graph_keyword(self):
        result = self.router._keyword_fallback("make a graph of sales")
        self.assertIn("DATA_AND_UTILITY", result["categories"])

    def test_french_graphique_keyword(self):
        result = self.router._keyword_fallback("fais un graphique des ventes")
        self.assertIn("DATA_AND_UTILITY", result["categories"])

    def test_weather_and_chart_combined(self):
        result = self.router._keyword_fallback("meteo de toulouse sous forme de plotchart")
        cats = result["categories"]
        self.assertIn("WEATHER_TOOLS", cats, "Should route to weather")
        self.assertIn("DATA_AND_UTILITY", cats, "Should route to data/utility for chart")

    def test_youtube_and_email_combined(self):
        result = self.router._keyword_fallback("find youtube videos and send by email")
        cats = result["categories"]
        self.assertIn("YOUTUBE_TOOLS", cats, "Should route to youtube")
        self.assertIn("COMMUNICATION_TOOLS", cats, "Should route to communication")


# ─── Skill Runtime Tests ─────────────────────────────────────────────────────

class MockConfig:
    """Minimal config mock for skill tests."""
    def get(self, key, default=None):
        defaults = {
            "skills_enabled": True,
            "skills_paths": [],
            "skills_router_min_score": 0.22,
            "skills_max_metadata_skills": 64,
            "skills_instruction_max_chars": 20000,
            "skills_max_resources_per_activation": 3,
            "skills_resource_max_chars": 10000,
        }
        return defaults.get(key, default)


class TestSkillCategoryInjection(unittest.TestCase):
    """Verify that activated skill's categories are always injected into routed set."""

    def setUp(self):
        from cowork.skills.runtime import SkillRuntime
        self.runtime = SkillRuntime(MockConfig())

    def test_skill_injects_own_category(self):
        """When data-utility-tools activates via 'chart' trigger, DATA_AND_UTILITY
        must be added even if it wasn't in the original routed categories."""
        routed = ["COMMUNICATION_TOOLS"]
        active = self.runtime.activate(
            "make a plotchar of sales data",
            routed,
        )
        merged = self.runtime.merge_categories(routed, active)
        self.assertIn("DATA_AND_UTILITY", merged,
                       "Activated skill must inject its own categories")

    def test_no_skill_no_injection(self):
        """When no skill activates, categories should remain unchanged."""
        routed = ["WEATHER_TOOLS"]
        active = self.runtime.activate("what is the weather", routed)
        merged = self.runtime.merge_categories(routed, active)
        # Weather skill injects WEATHER_TOOLS but that's already in routed
        self.assertIn("WEATHER_TOOLS", merged)

    def test_conversational_only_not_expanded(self):
        """CONVERSATIONAL_ONLY should never have categories added."""
        routed = ["CONVERSATIONAL_ONLY"]
        active = self.runtime.activate("make a chart", routed)
        merged = self.runtime.merge_categories(routed, active)
        self.assertEqual(merged, ["CONVERSATIONAL_ONLY"])


# ─── Trust Filter Tests ──────────────────────────────────────────────────────

class TestDomainScopedFiltering(unittest.TestCase):
    """Verify that skill trust filters only restrict tools within the skill's own categories."""

    def setUp(self):
        from cowork.skills.trust import SkillTrustEngine, TrustReport
        from cowork.skills.schema import SkillMetadata
        self.engine = SkillTrustEngine()
        self.TrustReport = TrustReport
        self.SkillMetadata = SkillMetadata

    def _make_skill(self, categories, allowed_tools, tier=2):
        return self.SkillMetadata(
            name="test-skill",
            description="Test skill",
            path=Path("/tmp/test"),
            triggers=["test"],
            tool_categories=categories,
            allowed_tools=allowed_tools,
            trust_tier=tier,
        )

    def _make_tool(self, name, category):
        return {
            "category": category,
            "type": "function",
            "function": {"name": name, "parameters": {"type": "object", "properties": {}}},
        }

    def test_other_domain_tools_pass_through(self):
        """Tools from categories NOT owned by the skill should pass through untouched."""
        skill = self._make_skill(["DATA_AND_UTILITY"], ["calc", "plotchar"])
        report = self.TrustReport(allowed=True, tier=2, failed_gates=[], notes=[])
        tools = [
            self._make_tool("calc", "DATA_AND_UTILITY"),
            self._make_tool("plotchar", "DATA_AND_UTILITY"),
            self._make_tool("openweather_forecast", "WEATHER_TOOLS"),
            self._make_tool("smtp_send_email", "COMMUNICATION_TOOLS"),
        ]
        filtered = self.engine.filter_tools_by_tier(tools, skill, report)
        names = [t["function"]["name"] for t in filtered]
        self.assertIn("openweather_forecast", names, "Weather tool should pass through")
        self.assertIn("smtp_send_email", names, "Email tool should pass through")
        self.assertIn("calc", names, "Skill's own tool should be kept")
        self.assertIn("plotchar", names, "Skill's own tool should be kept")

    def test_skill_domain_tools_filtered(self):
        """Tools in the skill's own category but NOT in allowed_tools should be removed."""
        skill = self._make_skill(["DATA_AND_UTILITY"], ["calc"])
        report = self.TrustReport(allowed=True, tier=2, failed_gates=[], notes=[])
        tools = [
            self._make_tool("calc", "DATA_AND_UTILITY"),
            self._make_tool("gen_diagram", "DATA_AND_UTILITY"),  # not in allowed_tools
        ]
        filtered = self.engine.filter_tools_by_tier(tools, skill, report)
        names = [t["function"]["name"] for t in filtered]
        self.assertIn("calc", names)
        self.assertNotIn("gen_diagram", names, "Tool not in allowed_tools should be removed")

    def test_tier2_mutation_block_scoped_to_skill(self):
        """Tier-2 mutation block should NOT affect tools from other categories."""
        skill = self._make_skill(["DATA_AND_UTILITY"], ["calc", "plotchar"], tier=2)
        report = self.TrustReport(allowed=True, tier=2, failed_gates=[], notes=[])
        tools = [
            self._make_tool("smtp_send_email", "COMMUNICATION_TOOLS"),  # 'send' = mutating
            self._make_tool("scratchpad_save", "SESSION_SCRATCHPAD"),   # 'save' = mutating
            self._make_tool("calc", "DATA_AND_UTILITY"),
        ]
        filtered = self.engine.filter_tools_by_tier(tools, skill, report)
        names = [t["function"]["name"] for t in filtered]
        self.assertIn("smtp_send_email", names,
                       "smtp_send_email should NOT be blocked by tier-2 since it's outside skill's domain")
        self.assertIn("scratchpad_save", names,
                       "scratchpad_save should NOT be blocked by tier-2 since it's outside skill's domain")
        self.assertIn("calc", names)

    def test_tier1_blocks_everything(self):
        """Tier 1 should block all tools regardless."""
        skill = self._make_skill(["DATA_AND_UTILITY"], ["calc"], tier=1)
        report = self.TrustReport(allowed=True, tier=1, failed_gates=[], notes=[])
        tools = [self._make_tool("calc", "DATA_AND_UTILITY")]
        filtered = self.engine.filter_tools_by_tier(tools, skill, report)
        self.assertEqual(len(filtered), 0, "Tier 1 should block everything")

    def test_not_allowed_blocks_everything(self):
        """Not-allowed report should block all tools."""
        skill = self._make_skill(["DATA_AND_UTILITY"], ["calc"])
        report = self.TrustReport(allowed=False, tier=2, failed_gates=["gate1"], notes=[])
        tools = [self._make_tool("calc", "DATA_AND_UTILITY")]
        filtered = self.engine.filter_tools_by_tier(tools, skill, report)
        self.assertEqual(len(filtered), 0, "Not-allowed should block everything")


# ─── System Message Consolidation Tests ───────────────────────────────────────

class TestSystemMessageConsolidation(unittest.TestCase):
    """Verify that _consolidate_system_messages works correctly.
    Uses the method directly rather than instantiating the full agent."""

    def setUp(self):
        from cowork.agent import GeneralPurposeAgent
        # Access the unbound method — it only uses `self` for nothing,
        # so we can call it via the class with a dummy instance.
        self.consolidate = GeneralPurposeAgent._consolidate_system_messages
        self.dummy = MagicMock()  # stands in for `self`

    def test_multiple_system_messages_consolidated(self):
        messages = [
            {"role": "system", "content": "Instruction A"},
            {"role": "user", "content": "Hello"},
            {"role": "system", "content": "Instruction B"},
        ]
        result = self.consolidate(self.dummy, messages)
        system_msgs = [m for m in result if m["role"] == "system"]
        self.assertEqual(len(system_msgs), 1, "Should have exactly one system message")
        self.assertIn("Instruction A", system_msgs[0]["content"])
        self.assertIn("Instruction B", system_msgs[0]["content"])

    def test_non_system_order_preserved(self):
        messages = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "U1"},
            {"role": "assistant", "content": "A1"},
            {"role": "system", "content": "SYS2"},
            {"role": "user", "content": "U2"},
        ]
        result = self.consolidate(self.dummy, messages)
        non_sys = [m for m in result if m["role"] != "system"]
        self.assertEqual(non_sys[0]["content"], "U1")
        self.assertEqual(non_sys[1]["content"], "A1")
        self.assertEqual(non_sys[2]["content"], "U2")

    def test_empty_system_messages_pruned(self):
        messages = [
            {"role": "system", "content": ""},
            {"role": "system", "content": "   "},
            {"role": "system", "content": "Real content"},
        ]
        result = self.consolidate(self.dummy, messages)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], "Real content")

    def test_no_system_messages(self):
        messages = [{"role": "user", "content": "Hello"}]
        result = self.consolidate(self.dummy, messages)
        self.assertEqual(result, messages)


# ─── SKILL.md Coherence Tests ────────────────────────────────────────────────

class TestSkillManifestCoherence(unittest.TestCase):
    """Verify that SKILL.md manifests reference tools that actually exist."""

    def test_all_skill_tools_exist_in_registry(self):
        """Every tool listed in a SKILL.md 'permissions.tools' must exist in the tool registry."""
        from cowork.tools import ALL_TOOLS
        from cowork.skills.catalog import SkillCatalog

        all_tool_names = {t["function"]["name"] for t in ALL_TOOLS}
        library_root = cli_dir / "cowork" / "skills" / "library"
        catalog = SkillCatalog([library_root])
        catalog.reload()

        errors = []
        for skill in catalog.all():
            for tool_name in (skill.allowed_tools or []):
                if tool_name not in all_tool_names:
                    errors.append(f"Skill '{skill.name}' references unknown tool '{tool_name}'")

        self.assertEqual(errors, [], "\n".join(errors))

    def test_all_skill_categories_are_valid(self):
        """Every category listed in a SKILL.md must exist in the tool registry."""
        from cowork.tools import CATEGORY_TOOL_MAP
        from cowork.skills.catalog import SkillCatalog

        valid_categories = set(CATEGORY_TOOL_MAP.keys())
        library_root = cli_dir / "cowork" / "skills" / "library"
        catalog = SkillCatalog([library_root])
        catalog.reload()

        errors = []
        for skill in catalog.all():
            for cat in (skill.tool_categories or []):
                if cat not in valid_categories:
                    errors.append(f"Skill '{skill.name}' references unknown category '{cat}'")

        self.assertEqual(errors, [], "\n".join(errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
