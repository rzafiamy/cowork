"""
🤖 General Purpose Agent — The REACT Execution Loop
Implements the full Manager-Worker agentic workflow:
  Phase 1: Input Gatekeeper
  Phase 2: Meta-Routing (Brain)
  Phase 3: REACT Loop (Worker)
  Phase 4: Context Compression
  Phase 5: Background Persistence
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .api_client import APIClient, APIError
from .config import AgentJob, ConfigManager, FirewallManager, FirewallAction, JobManager, Scratchpad, Session
from .prompts import AGENT_CHAT_SYSTEM_PROMPT, AGENT_SYSTEM_PROMPT, COMPRESS_PROMPT, SESSION_RE_TITLE_PROMPT
from .memoria import Memoria
from .issues import IssueManager
from .router import MetaRouter
from .skills import ActiveSkillContext, SkillRuntime
from .theme import (
    GATEWAY_ERROR_PREFIX,
    OP_DEFAULTS,
    TELEMETRY_STEPS,
    TOOL_ERROR_PREFIX,
)
from .tools import (
    ExecutionGateway,
    ToolExecutor,
    get_available_tools_for_categories,
    get_tools_for_categories,
)

# ─── Prompts are centralized in prompts.py ───────────────────────────────────
# Import: AGENT_SYSTEM_PROMPT, COMPRESS_PROMPT, SESSION_RE_TITLE_PROMPT

# ─── Context Compressor ───────────────────────────────────────────────────────

class ContextCompressor:
    """
    Manages context window size via Map-Reduce compression.
    Runs at Temperature 0.1 to preserve factual integrity.
    """

    # Prompt sourced from prompts.py — edit there to change compression behavior.

    def __init__(self, api_client: APIClient, config: ConfigManager, scratchpad: Scratchpad) -> None:
        self.api_client = api_client
        self.config = config
        self.scratchpad = scratchpad

    def _sanitize_ref_key(self, raw: str, prefix: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", (raw or "").strip().lower()).strip("_")
        if not cleaned:
            cleaned = f"{prefix}_{int(time.time())}"
        return cleaned[:80]

    async def _generate_ref_metadata(self, history_text: str) -> tuple[str, str]:
        excerpt = history_text[:1200]
        prompt = (
            "Create a compact JSON object for archival naming.\n"
            "Return ONLY JSON with keys: key, description.\n"
            "Rules:\n"
            "- key: snake_case, <= 60 chars, filename-safe, meaningful topic title\n"
            "- description: <= 100 chars\n\n"
            f"Conversation excerpt:\n{excerpt}"
        )
        try:
            result = await self.api_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.get("model_compress"),
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=80,
            )
            payload = json.loads(result.get("content", "{}"))
            key = self._sanitize_ref_key(str(payload.get("key", "")), "conversation")
            desc = str(payload.get("description", "")).strip()[:100] or "Compressed conversation source"
            return key, desc
        except Exception:
            fallback = self._sanitize_ref_key(excerpt.split("\n", 1)[0], "conversation")
            return fallback, "Compressed conversation source"

    def _estimate_tokens(self, messages: list[dict]) -> int:
        """Rough token estimate: 4 chars ≈ 1 token."""
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return total_chars // 4

    def _smart_chunk(self, text: str, chunk_size: int = 3000) -> list[str]:
        """Split on semantic boundaries (paragraphs, sentences)."""
        chunks = []
        while len(text) > chunk_size:
            # Find best split point
            split_at = chunk_size
            for sep in ["\n\n", "\n", ". ", " "]:
                idx = text.rfind(sep, 0, chunk_size)
                if idx > chunk_size // 2:
                    split_at = idx + len(sep)
                    break
            chunks.append(text[:split_at])
            text = text[split_at:]
        if text:
            chunks.append(text)
        return chunks

    async def optimize(
        self,
        messages: list[dict],
        system_prompt: str,
        status_cb: Optional[Callable[[str], None]] = None,
        trace_cb: Optional[Callable[[str, dict], None]] = None,
    ) -> list[dict]:
        """
        Optimize context window. Returns compressed messages list.
        Protects: system prompt + last 2 human messages.
        """
        limit = self.config.get("context_limit_tokens", OP_DEFAULTS["context_limit_tokens"])
        estimated = self._estimate_tokens(messages)

        if estimated <= limit:
            if trace_cb:
                trace_cb("context_compression_skipped", {"estimated_tokens": estimated, "limit_tokens": limit})
            return messages

        if status_cb:
            status_cb("🖇️  Context window full — running Map-Reduce compression...")
        if trace_cb:
            trace_cb("context_compression_started", {"estimated_tokens": estimated, "limit_tokens": limit})

        # Identify compressible history (exclude last 2 user messages)
        user_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
        protect_from = user_indices[-2] if len(user_indices) >= 2 else (user_indices[-1] if user_indices else len(messages))

        compressible = messages[:protect_from]
        protected = messages[protect_from:]

        if not compressible:
            return messages

        # Build history text for compression
        history_text = "\n\n".join(
            f"{m['role'].upper()}: {m.get('content', '')}"
            for m in compressible
            if m.get("content") and not (
                m.get("role") == "system"
                and str(m.get("content", "")).startswith("[CONVERSATION SUMMARY]")
            )
        )
        source_ref = ""
        if history_text.strip():
            try:
                key, desc = await self._generate_ref_metadata(history_text)
                source_ref = self.scratchpad.save(key, history_text, description=desc)
                if trace_cb:
                    trace_cb("context_compression_source_saved", {"ref": source_ref, "description": desc})
            except Exception:
                source_ref = ""

        # Map phase: chunk and summarize (12k chars ≈ 3k tokens)
        chunks = self._smart_chunk(history_text, chunk_size=12000)
        summaries = []
        for idx, chunk in enumerate(chunks, start=1):
            try:
                if trace_cb:
                    trace_cb(
                        "context_compression_map_request",
                        {"chunk_index": idx, "chunk_count": len(chunks), "chunk": chunk},
                    )
                result = await self.api_client.chat(
                    messages=[{"role": "user", "content": COMPRESS_PROMPT.format(history=chunk)}],
                    model=self.config.get("model_compress"),
                    temperature=OP_DEFAULTS["temperature_compress"],
                    max_tokens=600,
                )
                summary = result.get("content", "")
                summaries.append(summary)
                if trace_cb:
                    trace_cb(
                        "context_compression_map_response",
                        {"chunk_index": idx, "summary": summary, "finish_reason": result.get("finish_reason", "stop")},
                    )
            except Exception:
                summaries.append(chunk[:500] + "... [truncated]")
                if trace_cb:
                    trace_cb("context_compression_map_error", {"chunk_index": idx})

        # Reduce phase: combine summaries
        combined = "\n\n".join(summaries)
        summary_content = (
            f"[CONVERSATION SUMMARY]\n"
            f"{f'Source archived at {source_ref}\\n' if source_ref else ''}"
            f"{combined}"
        )

        # 1. Maintain consistent system prompt structure
        # Combine base system_prompt and the new summary into ONE system message.
        consolidated_content = f"{system_prompt}\n\n{summary_content}"
        return [{"role": "system", "content": consolidated_content}] + protected


# ─── Agent Trace ─────────────────────────────────────────────────────────────

@dataclass
class AgentTrace:
    """Records the full execution trace for debugging."""
    job_id: str
    steps: list[dict] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    total_tool_calls: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    def add_step(self, step_type: str, data: dict) -> None:
        self.steps.append({
            "step": len(self.steps) + 1,
            "type": step_type,
            "elapsed_ms": int((time.time() - self.start_time) * 1000),
            **data,
        })

    def finish(self) -> None:
        self.end_time = time.time()
        # Extract all tool calls from steps for easy persistence
        self.all_tool_calls_executed = []
        for s in self.steps:
            if s["type"] == "tool_execution_result":
                self.all_tool_calls_executed.append({
                    "name": s["name"],
                    "args": s["args"],
                    "status": "success" if "[TOOL ERROR]" not in s["result"] else "error"
                })

    @property
    def elapsed_seconds(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time


# ─── General Purpose Agent ────────────────────────────────────────────────────

class GeneralPurposeAgent:
    """
    The REACT Loop Worker.
    Orchestrates: routing → context compression → LLM reasoning → tool execution → memory update.
    """

    def __init__(
        self,
        api_client: APIClient,
        config: ConfigManager,
        scratchpad: Scratchpad,
        memoria: Memoria,
        job_manager: JobManager,
        status_callback: Optional[Callable[[str], None]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        confirmation_callback: Optional[Callable[[str, str, dict], Any]] = None,
        trace_callback: Optional[Callable[[str, dict], None]] = None,
    ) -> None:
        self.api_client = api_client
        self.config = config
        self.scratchpad = scratchpad
        self.memoria = memoria
        self.job_manager = job_manager
        self.status_cb = status_callback or (lambda msg: None)
        self.stream_cb = stream_callback or (lambda token: None)
        self.confirm_cb = confirmation_callback
        self.trace_cb = trace_callback or (lambda _event, _data: None)

        self.router = MetaRouter(api_client, config.get("model_router", "gpt-4o-mini"))
        self.compressor = ContextCompressor(api_client, config, scratchpad)
        self.issue_manager = IssueManager(user_id=memoria.user_id, config=config)
        self.gateway = ExecutionGateway(scratchpad)
        self.executor = ToolExecutor(scratchpad, config, status_callback=self.status_cb)
        self.firewall = FirewallManager()
        self.skill_runtime = SkillRuntime(config)

    def _strip_nonlimit_status_banner(self, text: str) -> str:
        """
        Remove GOAL banner if the model emits it on a normal non-limit turn.
        """
        if not text:
            return text
        lines = text.splitlines()
        if not lines:
            return text
        first = lines[0].strip()
        pattern = re.compile(r"^[✅⚠️❌]\s+GOAL\s+(ACHIEVED|PARTIALLY ACHIEVED|NOT ACHIEVED)\s*$")
        if pattern.match(first):
            stripped = "\n".join(lines[1:]).lstrip()
            return stripped or text
        return text

    def _should_persist_memory(self, user_input: str) -> bool:
        """
        Persist only durable preference/profile/project-state messages.
        Delegate to Memoria so read/write paths share the same memory policy.
        """
        return self.memoria.is_durable_message(user_input)

    def _make_meaningful_ref_key(self, user_input: str) -> str:
        """
        Build a stable, readable scratchpad key from user intent.
        """
        words = re.findall(r"[a-zA-Z0-9_]+", (user_input or "").lower())
        stop = {
            "the", "and", "for", "with", "that", "this", "from", "into", "your", "you",
            "want", "need", "please", "just", "then", "about", "have", "will", "would",
        }
        meaningful = [w for w in words if len(w) >= 3 and w not in stop][:5]
        slug = "_".join(meaningful) or "important_note"
        return f"mem_{slug}_{int(time.time())}"

    def _sanitize_ref_key(self, raw: str, prefix: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", (raw or "").strip().lower()).strip("_")
        if not cleaned:
            cleaned = f"{prefix}_{int(time.time())}"
        return cleaned[:90]

    async def _generate_ref_metadata(self, content: str, kind: str, hint: str = "") -> tuple[str, str]:
        excerpt = (content or "")[:1200]
        prompt = (
            "Create archival metadata for scratchpad storage.\n"
            "Return ONLY JSON with keys: key, description.\n"
            "Rules:\n"
            "- key: snake_case, <= 70 chars, filename-safe, specific\n"
            "- description: <= 110 chars\n"
            f"- kind: {kind}\n"
            f"- hint: {hint or 'none'}\n\n"
            f"Content excerpt:\n{excerpt}"
        )
        try:
            result = await self.api_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.get("model_compress"),
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=90,
            )
            payload = json.loads(result.get("content", "{}"))
            key = self._sanitize_ref_key(str(payload.get("key", "")), kind)
            desc = str(payload.get("description", "")).strip()[:110] or f"Archived {kind}"
            return key, desc
        except Exception:
            fallback_seed = f"{kind}_{hint}_{excerpt[:80]}"
            key = self._sanitize_ref_key(fallback_seed, kind)
            return key, f"Archived {kind}"

    async def _compress_tool_result_if_needed(self, tool_name: str, result: str) -> str:
        if re.search(r"\[Full result saved as ref:[^\]]+\]", result or ""):
            return result

        limit = self.config.get("tool_output_limit_tokens", OP_DEFAULTS["tool_output_limit_tokens"])
        estimated_tokens = len(result or "") // 4
        if estimated_tokens <= limit:
            return result

        key, desc = await self._generate_ref_metadata(result, kind="tool_output", hint=tool_name)
        ref = self.scratchpad.save(key, result, description=desc)
        preview = self.scratchpad.sandwich_preview(result)
        return f"{preview}\n\n[Full result saved as {ref}]"

    def _save_important_ref_memory(self, user_input: str, assistant_response: str) -> Optional[str]:
        """
        Persist an important turn as a named ref with compact description.
        """
        key = self._make_meaningful_ref_key(user_input)
        short_user = " ".join((user_input or "").split())[:120]
        description = short_user or "Important turn snapshot"
        content = (
            f"USER_REQUEST:\n{user_input.strip()}\n\n"
            f"ASSISTANT_RESPONSE:\n{assistant_response.strip()}\n"
        )
        try:
            return self.scratchpad.save(key, content, description=description)
        except Exception:
            return None

    # ── Scratchpad Index Builder ───────────────────────────────────────────────

    def _build_scratchpad_index(self) -> str:
        """
        Build a compact, human-readable scratchpad index to inject into
        the system prompt. Gives the AI immediate awareness of stored context
        without needing to call scratchpad_list first.
        """
        try:
            items = self.scratchpad.list_all()
            if not items:
                return "(empty — no task context stored yet)"
            lines = []
            for item in items:
                key = item['key']
                desc = item.get('description') or 'no description'
                size = item.get('size_chars', 0)
                marker = " ← 🎯 TASK GOAL" if key == "task_goal" else ""
                lines.append(f"• ref:{key} — {desc} ({size} chars){marker}")
            return "\n".join(lines)
        except Exception:
            return "(scratchpad unavailable)"

    def _assess_tool_result(self, tool_name: str, result: str) -> dict[str, str]:
        """
        Produce a compact, model-friendly assessment for a tool output.
        This is injected back into the loop so the next step reasons from
        distilled findings instead of only raw tool text.
        """
        text = (result or "").strip()
        lowered = text.lower()

        if text.startswith(TOOL_ERROR_PREFIX):
            status = "error"
            next_action = "Use an alternative tool or fix arguments and retry."
        elif text.startswith(GATEWAY_ERROR_PREFIX):
            status = "error"
            next_action = "Repair tool-call schema/refs and retry."
        elif "[FIREWALL BLOCK]" in text or "[FIREWALL CANCEL]" in text:
            status = "blocked"
            next_action = "Ask user confirmation or choose a safer alternative."
        else:
            status = "ok"
            next_action = "Proceed with synthesis or call next required tool."

        # Extract compact evidence snippets from non-empty, non-decorative lines.
        snippets: list[str] = []
        for line in text.splitlines():
            ln = line.strip()
            if not ln:
                continue
            if ln.startswith("•"):
                ln = ln[1:].strip()
            if ln.startswith("✅") or ln.startswith("❌") or ln.startswith("⚠️") or ln.startswith("🛡️"):
                ln = ln[1:].strip()
            if ln and not ln.startswith("[") and len(ln) > 2:
                snippets.append(ln)
            if len(snippets) >= 2:
                break

        finding = " | ".join(snippets)[:260] if snippets else (text[:260] if text else "No output.")
        if "not found" in lowered and status == "ok":
            status = "partial"
            next_action = "Validate input/query and retry with adjusted parameters."

        if status in ("error", "partial"):
            matches = self.issue_manager.search_issues(f"{tool_name} {finding}")
            if matches:
                hints = [m["solution"] for m in matches]
                next_action += f" [HINTS FROM PAST: {' | '.join(hints)}]"

        return {
            "tool": tool_name,
            "status": status,
            "finding": finding,
            "next_action": next_action,
        }

    def _snapshot_assistant_output(self, content: str, step: int) -> Optional[str]:
        """
        Persist assistant text for exact downstream reuse (e.g., text -> TTS).
        Always updates ref:last_assistant_response and optionally stores a step snapshot.
        """
        text = (content or "").strip()
        if not text:
            return None

        try:
            self.scratchpad.save(
                "last_assistant_response",
                text,
                description="Exact text of the latest assistant response for tool chaining",
            )
            if len(text) >= 400:
                key = f"assistant_step_{int(time.time())}_{step}"
                self.scratchpad.save(
                    key,
                    text,
                    description=f"Assistant response snapshot from step {step}",
                )
                return f"ref:{key}"
        except Exception:
            return None
        return None

    def _build_tool_reflection_note(self, step: int, assessments: list[dict[str, str]]) -> str:
        """
        Build a compact structured note for the next LLM step.
        """
        lines = [
            "[TOOL REFLECTION]",
            f"Step: {step}",
            "Use this to continue reasoning from validated tool outcomes.",
        ]
        for i, a in enumerate(assessments, start=1):
            lines.append(
                f"{i}. tool={a['tool']}; status={a['status']}; finding={a['finding']}; next={a['next_action']}"
            )
        return "\n".join(lines)[:1800]

    def _build_tool_contract_message(self, tools_schema: list[dict[str, Any]]) -> str:
        """
        Inject explicit allowed tool contract to reduce tool-call hallucinations.
        """
        if not tools_schema:
            return "[TOOL CONTRACT]\nNo tool calls are allowed in this turn."

        lines = [
            "### 📜 Tool Usage Contract",
            "You may call **ONLY** these exact tool names. Never invent or alias tool names.",
        ]
        for tool in tools_schema:
            fn = tool.get("function", {})
            name = str(fn.get("name", "")).strip()
            if not name:
                continue
            params = fn.get("parameters", {}) or {}
            required = params.get("required", []) if isinstance(params, dict) else []
            req_txt = ", ".join(f"`{r}`" for r in required) if required else "_none_"
            lines.append(f"- **{name}**: requires {req_txt}")
        lines.append("\nIf no listed tool fits the current need, ask the user for clarification or answer without tools.")
        return "\n".join(lines)

    def _looks_like_goal_status(self, text: str) -> bool:
        head = (text or "").strip().splitlines()
        if not head:
            return False
        first = head[0].strip()
        return bool(re.match(r"^[✅⚠️❌]\s+GOAL\s+(ACHIEVED|PARTIALLY ACHIEVED|NOT ACHIEVED)\s*$", first))

    # ── Input Gatekeeper ──────────────────────────────────────────────────────

    def _gatekeeper(self, user_input: str, session: Session) -> str:
        """
        Phase 1: Check if input is too large. If so, offload to scratchpad.
        Returns the (possibly ref:key-replaced) input for the agent.
        """
        limit = self.config.get("user_input_limit_tokens", OP_DEFAULTS["user_input_limit_tokens"])
        estimated_tokens = len(user_input) // 4

        if estimated_tokens > limit:
            self.status_cb(f"🛡️  Input too large ({estimated_tokens} tokens) — offloading to scratchpad...")
            import uuid
            key = f"input_{uuid.uuid4().hex[:8]}"
            self.scratchpad.save(key, user_input, description="Large user input")
            preview = self.scratchpad.sandwich_preview(user_input)
            return (
                f"[Large input offloaded to scratchpad]\n"
                f"Reference: ref:{key}\n\n"
                f"Preview:\n{preview}"
            )
        return user_input

    # ── Main Run ──────────────────────────────────────────────────────────────

    async def run(
        self,
        user_input: str,
        session: Session,
        job: AgentJob,
        action_mode: Optional[dict] = None,
    ) -> str:
        """
        Execute the full agentic workflow for a user request.
        Returns the final assistant response string.
        """
        import datetime as dt
        trace = AgentTrace(job_id=job.job_id)
        self.trace_cb(
            "turn_started",
            {
                "job_id": job.job_id,
                "session_id": session.session_id,
                "action_mode": action_mode or {},
                "config": {
                    "max_steps": self.config.get("max_steps", OP_DEFAULTS["max_steps"]),
                    "max_total_tool_calls": self.config.get("max_total_tool_calls", OP_DEFAULTS["max_total_tool_calls"]),
                    "max_tool_calls_per_step": self.config.get("max_tool_calls_per_step", OP_DEFAULTS["max_tool_calls_per_step"]),
                    "tool_output_limit_tokens": self.config.get("tool_output_limit_tokens", OP_DEFAULTS["tool_output_limit_tokens"]),
                    "context_limit_tokens": self.config.get("context_limit_tokens", OP_DEFAULTS["context_limit_tokens"]),
                },
            },
        )
        max_steps = self.config.get("max_steps", OP_DEFAULTS["max_steps"])
        max_tool_calls = self.config.get("max_total_tool_calls", OP_DEFAULTS["max_total_tool_calls"])
        total_tool_calls = 0

        # ── Phase 1: Input Gatekeeper ─────────────────────────────────────────
        self.status_cb("🛡️  Phase 1 · Input Gatekeeper...")
        processed_input = self._gatekeeper(user_input, session)
        self.trace_cb("gatekeeper_result", {"user_input": user_input, "processed_input": processed_input})
        trace.add_step("gatekeeper", {"original_len": len(user_input), "processed_len": len(processed_input)})

        # ── Phase 2: Meta-Routing (Brain) ─────────────────────────────────────
        if action_mode:
            # Fast-track: skip router, use predefined categories
            categories = action_mode.get("categories", ["ALL_TOOLS"])
            self.status_cb(f"⚡ Action Mode — bypassing router, using: {', '.join(categories)}")
            routing_info = {
                "categories": categories,
                "confidence": 1.0,
                "reasoning": "Action mode",
            }
        else:
            self.status_cb("🧭  Phase 2 · Meta-Routing intent classification...")
            # ── Session-Context-Aware Routing ──────────────────────────────
            # When the user sends a short follow-up (e.g., an email address
            # in response to "who should I send it to?"), the router sees it
            # in isolation and misclassifies it as CONVERSATIONAL_ONLY.
            # Fix: prepend a compact context hint from recent messages so
            # the router can understand the follow-up in context.
            routing_prompt = processed_input
            if session.messages and len(processed_input.strip()) < 120:
                recent = session.messages[-4:]  # last 2 turns (user+assistant)
                context_parts = []
                for m in recent:
                    role = m.get("role", "")
                    content = str(m.get("content", "")).strip()
                    if role in ("user", "assistant") and content:
                        context_parts.append(f"{role}: {content[:150]}")
                if context_parts:
                    context_hint = " | ".join(context_parts)
                    routing_prompt = (
                        f"[SESSION CONTEXT: {context_hint}] "
                        f"Current user message: {processed_input}"
                    )
            self.trace_cb("router_request", {"prompt": routing_prompt})
            routing_info = await self.router.classify(routing_prompt)
            categories = routing_info["categories"]
            display = self.router.get_category_display(categories)
            self.status_cb(f"🎯  Routed to: {display} (confidence: {routing_info['confidence']:.0%})")

        # ── Skill Runtime Activation (Progressive Disclosure) ─────────────────
        active_skill: ActiveSkillContext = self.skill_runtime.activate(processed_input, categories)
        categories = self.skill_runtime.merge_categories(categories, active_skill)
        if active_skill.skill:
            job.skill_name = active_skill.skill.name
            if active_skill.enabled:
                self.status_cb(
                    f"🧩  Skill activated: {active_skill.skill.name} (tier {active_skill.trust.tier}, score {active_skill.score:.2f})"
                )
            else:
                self.status_cb(f"🧩  Skill blocked by trust gates: {active_skill.skill.name}")

        # ── Always include SESSION_SCRATCHPAD so task_goal tools are always available ──
        if (
            "CONVERSATIONAL_ONLY" not in categories
            and "CONVERSATIONAL" not in categories
            and "SESSION_SCRATCHPAD" not in categories
            and "ALL_TOOLS" not in categories
        ):
            categories = list(categories) + ["SESSION_SCRATCHPAD"]

        trace.add_step("routing", routing_info)
        self.trace_cb("router_response", routing_info)
        self.trace_cb(
            "skill_routing",
            {
                "active_skill": active_skill.skill.name if active_skill.skill else "",
                "score": active_skill.score,
                "enabled": active_skill.enabled,
                "trust_tier": active_skill.trust.tier if active_skill.trust else None,
                "failed_gates": active_skill.trust.failed_gates if active_skill.trust else [],
            },
        )
        trace.categories = categories
        job.categories = categories

        # ── Memory Context Retrieval ───────────────────────────────────────────
        memory_context = ""
        self.status_cb("🧠  Retrieving memory context...")
        memory_context = self.memoria.get_fused_context(processed_input)
        self.trace_cb("memory_context", {"memory_context": memory_context, "skipped": False})

        # ── Build Tool Schema (Filters out unconfigured paid tools) ───────────
        tools_schema_raw = [] if "CONVERSATIONAL_ONLY" in categories else get_available_tools_for_categories(categories)
        tools_schema = self.skill_runtime.filter_tools(tools_schema_raw, active_skill)
        skill_filtered_empty = bool(active_skill.enabled and tools_schema_raw and not tools_schema)
        if skill_filtered_empty:
            # Coherence safeguard: avoid empty-tool dead-ends caused by overly strict skill manifests.
            self.status_cb("⚠️  Skill constraints removed all tools — falling back to routed tool set.")
            tools_schema = tools_schema_raw
        self.trace_cb(
            "tools_schema_selected",
            {
                "categories": categories,
                "tool_names": [t["function"]["name"] for t in tools_schema],
                "tools_schema": tools_schema,
                "tools_schema_raw": tools_schema_raw,
                "skill_filtered_empty_fallback": skill_filtered_empty,
                "bypass_tool_schema": "CONVERSATIONAL_ONLY" in categories,
            },
        )

        if tools_schema:
            premium_tools = [t["function"]["name"] for t in tools_schema if t["category"] in categories and t["category"] != "CONVERSATIONAL"]
            if premium_tools:
                self.status_cb(f"🔌 Enabled {len(premium_tools)} tool(s) for this task.")
        allowed_tool_names = {str(t.get("function", {}).get("name", "")) for t in tools_schema}
        allowed_tool_names.discard("")
        multimodal_tool_names = {"image_generate", "speech_to_text", "text_to_speech", "vision_analyze"}
        multimodal_allowed = ("MULTIMODAL_TOOLS" in categories) or ("ALL_TOOLS" in categories)

        # ── Build System Prompt ───────────────────────────────────────────────
        current_dt = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
        # ── Build Consolidated System Prompt ──────────────────────────────────
        skill_toc = self.skill_runtime.build_metadata_toc()
        skill_context = self.skill_runtime.build_context_message(active_skill) or "(No specific skill active)"
        tool_contract = self._build_tool_contract_message(tools_schema)

        if "CONVERSATIONAL_ONLY" in categories:
            system_prompt = AGENT_CHAT_SYSTEM_PROMPT.format(
                current_datetime=current_dt,
                memory_context=memory_context or "(No memory context yet)",
                session_id=session.session_id[:8],
                message_count=len(session.messages),
            )
        else:
            scratchpad_index = self._build_scratchpad_index()
            system_prompt = AGENT_SYSTEM_PROMPT.format(
                current_datetime=current_dt,
                memory_context=memory_context or "(No memory context yet)",
                session_id=session.session_id[:8],
                message_count=len(session.messages),
                scratchpad_index=scratchpad_index,
                skill_context=skill_context,
                skill_toc=skill_toc,
                tool_contract=tool_contract,
            )

        # ── Build Message List ────────────────────────────────────────────────
        chat_history = session.get_chat_messages()
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            *chat_history,
            {"role": "user", "content": processed_input},
        ]
        self.trace_cb(
            "initial_messages_built",
            {
                "system_prompt": system_prompt,
                "chat_history_count": len(chat_history),
                "messages": messages,
            },
        )

        # ── Phase 3: REACT Loop ───────────────────────────────────────────────
        self.status_cb("🤖  Phase 3 · REACT Execution Loop...")
        final_response = ""
        step_ledger: list[dict[str, Any]] = []
        disallowed_tool_attempts = 0
        step_limit_reached = False

        last_tool_hash = None
        repeat_count = 0

        for step in range(max_steps):
            # Context compression check
            messages = await self.compressor.optimize(messages, system_prompt, self.status_cb, self.trace_cb)

            self.status_cb(f"🔄  Step {step + 1}/{max_steps} · Reasoning...")
            trace.add_step("react_step_start", {"step": step + 1})

            # LLM call
            try:
                use_stream = self.config.get("stream", True) and bool(self.stream_cb)
                if use_stream and tools_schema:
                    # With tools: non-streaming (tools + streaming is tricky)
                    self.trace_cb(
                        "llm_request",
                        {
                            "step": step + 1,
                            "stream": False,
                            "model": self.config.get("model_text"),
                            "temperature": self.config.get("temperature_agent", OP_DEFAULTS["temperature_agent"]),
                            "messages": messages,
                            "tools_schema": tools_schema,
                        },
                    )
                    result = await self.api_client.chat(
                        messages=messages,
                        model=self.config.get("model_text"),
                        temperature=self.config.get("temperature_agent", OP_DEFAULTS["temperature_agent"]),
                        tools=tools_schema if tools_schema else None,
                        max_tokens=4096,
                    )
                elif use_stream and not tools_schema:
                    # Pure text: stream it
                    self.trace_cb(
                        "llm_request",
                        {
                            "step": step + 1,
                            "stream": True,
                            "model": self.config.get("model_text"),
                            "temperature": self.config.get("temperature_agent", OP_DEFAULTS["temperature_agent"]),
                            "messages": messages,
                            "tools_schema": [],
                        },
                    )
                    result = await self.api_client.chat_stream(
                        messages=messages,
                        model=self.config.get("model_text"),
                        temperature=self.config.get("temperature_agent", OP_DEFAULTS["temperature_agent"]),
                        on_chunk=self.stream_cb,
                    )
                else:
                    self.trace_cb(
                        "llm_request",
                        {
                            "step": step + 1,
                            "stream": False,
                            "model": self.config.get("model_text"),
                            "temperature": self.config.get("temperature_agent", OP_DEFAULTS["temperature_agent"]),
                            "messages": messages,
                            "tools_schema": tools_schema,
                        },
                    )
                    result = await self.api_client.chat(
                        messages=messages,
                        model=self.config.get("model_text"),
                        temperature=self.config.get("temperature_agent", OP_DEFAULTS["temperature_agent"]),
                        tools=tools_schema if tools_schema else None,
                        max_tokens=4096,
                    )
            except APIError as e:
                error_msg = f"❌ API Error: {e}"
                trace.add_step("api_error", {"error": str(e)})
                self.trace_cb("llm_error", {"step": step + 1, "error": str(e)})
                return error_msg

            content = result.get("content", "")
            tool_calls = result.get("tool_calls", [])
            finish_reason = result.get("finish_reason", "stop")
            snapshot_ref = self._snapshot_assistant_output(content, step + 1)
            self.trace_cb(
                "llm_response",
                {
                    "step": step + 1,
                    "content": content,
                    "tool_calls": tool_calls,
                    "finish_reason": finish_reason,
                    "snapshot_ref": snapshot_ref or "ref:last_assistant_response",
                    "usage": result.get("usage", {}),
                },
            )

            # Append assistant message to context
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            # ── Tool Execution ────────────────────────────────────────────────
            if tool_calls and total_tool_calls < max_tool_calls:
                if not allowed_tool_names:
                    disallowed_tool_attempts += 1
                    self.trace_cb(
                        "tool_calls_blocked_no_schema",
                        {"step": step + 1, "tool_calls": tool_calls, "attempt": disallowed_tool_attempts},
                    )
                    messages.append({
                        "role": "system",
                        "content": (
                            "[SYSTEM NOTICE] Tool calls were requested but no tools are allowed this turn. "
                            "Do not call tools. Provide a direct answer or ask a clarification question."
                        ),
                    })
                    if disallowed_tool_attempts >= 2:
                        final_response = (
                            "I could not execute tool calls for this request because no tools were allowed by policy. "
                            "Please rephrase the request or enable the required tool category."
                        )
                        break
                    continue

                # ── Loop Detection ──
                try:
                    current_hash = hash(json.dumps(tool_calls, sort_keys=True))
                    if current_hash == last_tool_hash:
                        repeat_count += 1
                    else:
                        repeat_count = 0
                    last_tool_hash = current_hash
                except Exception:
                    pass

                if repeat_count >= 2:
                    self.status_cb("⚠️  Loop detected: repeating tool calls. Breaking.")
                    messages.append({
                        "role": "user",
                        "content": (
                            "[SYSTEM NOTICE] You appear to be repeating the same tool call in a loop. "
                            "Stop immediately. State clearly what has been accomplished so far, "
                            "what is still missing, and ask the user how to proceed."
                        ),
                    })
                    final_response = content or "I seem to be caught in a loop. Let me know how you'd like to proceed."
                    break

                max_per_step = self.config.get("max_tool_calls_per_step", OP_DEFAULTS["max_tool_calls_per_step"])
                calls_this_step = tool_calls[:max_per_step]

                self.status_cb(f"⚙️  Executing {len(calls_this_step)} tool(s)...")
                trace.add_step("tool_calls", {"count": len(calls_this_step), "tools": [tc["function"]["name"] for tc in calls_this_step]})

                # Execute tools (parallelized)
                async def _exec_one(tc: dict) -> dict:
                    nonlocal disallowed_tool_attempts
                    name = tc["function"]["name"]
                    raw_args = tc["function"].get("arguments", {})
                    self.trace_cb("tool_call_received", {"step": step + 1, "name": name, "raw_args": raw_args, "tool_call": tc})
                    if isinstance(raw_args, str):
                        try:
                            raw_args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            return {
                                "tool_call_id": tc["id"],
                                "role": "tool",
                                "name": name,
                                "content": f"{GATEWAY_ERROR_PREFIX} Invalid JSON arguments. [HINT]: Correct the JSON syntax.",
                            }

                    if name not in allowed_tool_names:
                        disallowed_tool_attempts += 1
                        allowed_preview = ", ".join(sorted(allowed_tool_names)[:12]) or "(none)"
                        blocked_msg = (
                            f"{GATEWAY_ERROR_PREFIX} Tool '{name}' is not allowed for this turn. "
                            f"[HINT]: Use one of: {allowed_preview}"
                        )
                        if disallowed_tool_attempts >= 2:
                            messages.append({
                                "role": "system",
                                "content": (
                                    "[SYSTEM NOTICE] You are repeatedly requesting disallowed tools. "
                                    "Stop calling tools not in the contract and answer using allowed tools only."
                                ),
                            })
                        return {
                            "tool_call_id": tc["id"],
                            "role": "tool",
                            "name": name,
                            "content": blocked_msg,
                        }

                    if name in multimodal_tool_names and not multimodal_allowed:
                        return {
                            "tool_call_id": tc["id"],
                            "role": "tool",
                            "name": name,
                            "content": (
                                f"{GATEWAY_ERROR_PREFIX} Multimodal tool '{name}' blocked for this request. "
                                "[HINT]: Use multimodal tools only when user explicitly asks for image/audio/vision tasks."
                            ),
                        }

                    ok, resolved_args, err = self.gateway.validate_and_resolve(name, raw_args)
                    self.trace_cb(
                        "tool_call_validated",
                        {
                            "step": step + 1,
                            "name": name,
                            "ok": ok,
                            "resolved_args": resolved_args if ok else {},
                            "error": "" if ok else err,
                        },
                    )
                    if not ok:
                        return {"tool_call_id": tc["id"], "role": "tool", "name": name, "content": err}

                    # ── Firewall Check ──
                    action, reason = self.firewall.check(name, resolved_args)
                    self.trace_cb(
                        "tool_firewall_decision",
                        {"step": step + 1, "name": name, "action": action, "reason": reason, "args": resolved_args},
                    )
                    
                    if action == FirewallAction.BLOCK:
                        self.status_cb(f"🛡️  Firewall BLOCKED: {name} ({reason})")
                        return {
                            "tool_call_id": tc["id"],
                            "role": "tool",
                            "name": name,
                            "content": f"🛡️ [FIREWALL BLOCK] This tool call was rejected by the system policy: {reason}",
                        }
                    
                    if action == FirewallAction.ANALYZE:
                        self.status_cb(f"🧐 Firewall ANALYZE: {name} ({reason})")
                        # For now, analyze just logs and proceeds, or could trigger a meta-reasoning step
                        pass
                    
                    if action == FirewallAction.ASK and self.confirm_cb:
                        self.status_cb(f"🛡️  Firewall REQUEST: {name} ({reason})")
                        confirmed = await self.confirm_cb(name, reason, resolved_args)
                        if not confirmed:
                            return {
                                "tool_call_id": tc["id"],
                                "role": "tool",
                                "name": name,
                                "content": "🛡️ [FIREWALL CANCEL] Tool execution cancelled by the user.",
                            }

                    raw_result = await asyncio.get_event_loop().run_in_executor(
                        None, self.executor.execute, name, resolved_args, False
                    )
                    result_str = await self._compress_tool_result_if_needed(name, raw_result)
                    trace.add_step("tool_execution_result", {"name": name, "args": resolved_args, "result": result_str})
                    self.trace_cb(
                        "tool_execution_result",
                        {"step": step + 1, "name": name, "args": resolved_args, "result": result_str},
                    )
                    return {"tool_call_id": tc["id"], "role": "tool", "name": name, "content": result_str}

                tool_results = await asyncio.gather(*[_exec_one(tc) for tc in calls_this_step])
                messages.extend(tool_results)
                total_tool_calls += len(calls_this_step)
                trace.total_tool_calls = total_tool_calls

                # Build compact tool assessments for the next reasoning step.
                assessments: list[dict[str, str]] = []
                for tc, tr in zip(calls_this_step, tool_results):
                    tool_name = tc.get("function", {}).get("name", "unknown_tool")
                    tool_text = tr.get("content", "")
                    assessments.append(self._assess_tool_result(tool_name, tool_text))

                reflection_note = self._build_tool_reflection_note(step + 1, assessments)
                messages.append({"role": "system", "content": reflection_note})
                self.trace_cb(
                    "tool_reflection_note",
                    {
                        "step": step + 1,
                        "assessments": assessments,
                        "note": reflection_note,
                    },
                )

                # Keep a rolling run ledger in scratchpad for continuity/debug.
                step_ledger.append(
                    {
                        "step": step + 1,
                        "assessments": assessments,
                        "tool_calls": [tc.get("function", {}).get("name", "") for tc in calls_this_step],
                    }
                )
                try:
                    self.scratchpad.save(
                        "run_step_ledger",
                        json.dumps(step_ledger[-12:], ensure_ascii=False, indent=2),
                        description="Rolling tool-step assessments for current run",
                    )
                except Exception:
                    pass
                continue  # Loop back for next reasoning step

            # ── No more tool calls — we have a final answer ───────────────────
            final_response = self._strip_nonlimit_status_banner(content)
            trace.add_step("final_answer", {"length": len(content), "finish_reason": finish_reason})
            self.trace_cb("final_answer", {"content": final_response, "finish_reason": finish_reason, "step": step + 1})
            break

        # ── Step-limit recovery ───────────────────────────────────────────────
        if not final_response:
            step_limit_reached = True
            self.status_cb(f"⏱️  Step limit ({max_steps}) reached — requesting self-assessment...")
            trace.add_step("step_limit_reached", {"max_steps": max_steps, "total_tool_calls": total_tool_calls})
            try:
                limit_messages = messages + [{
                    "role": "user",
                    "content": (
                        f"[SYSTEM NOTICE] You have reached the maximum step limit ({max_steps} steps). "
                        "You MUST now provide a final response to the user — do NOT call any more tools. "
                        "In your response you MUST:\n"
                        "1. Clearly state whether the user's original goal was FULLY ACHIEVED, PARTIALLY ACHIEVED, or NOT ACHIEVED.\n"
                        "2. Summarize concisely what was accomplished so far.\n"
                        "3. If the goal was not fully achieved, list exactly what remains to be done.\n"
                        "4. Ask the user if they would like to continue in a new turn.\n"
                        "Do NOT invent results. Do NOT hallucinate. Only report what was actually done."
                    ),
                }]
                limit_result = await self.api_client.chat(
                    messages=limit_messages,
                    model=self.config.get("model_text"),
                    temperature=0.1,
                    tools=None,   # no tools — force text answer
                    max_tokens=1024,
                )
                final_response = limit_result.get("content", "").strip()
                self.trace_cb("step_limit_self_assessment_response", {"content": final_response})
            except Exception as e:
                final_response = (
                    f"⚠️ I reached the maximum step limit ({max_steps} steps) without fully completing your request. "
                    f"Here is where I stopped: the last tool calls are visible in the trace above. "
                    f"Please reply to continue where I left off."
                )

        trace.finish()
        self.trace_cb(
            "trace_summary",
            {
                "steps": trace.steps,
                "total_tool_calls": trace.total_tool_calls,
                "elapsed_seconds": trace.elapsed_seconds,
            },
        )
        job.steps = len([s for s in trace.steps if s["type"] == "react_step_start"])
        job.tool_calls = trace.total_tool_calls
        job.tool_calls_list = getattr(trace, "all_tool_calls_executed", [])
        job.step_limit_reached = step_limit_reached
        job.routed_categories = list(categories)
        job.goal_status_banner = self._looks_like_goal_status(final_response)

        # ── Phase 5: Memory Update ───────────────────────────────────────────
        persist_memory = self._should_persist_memory(user_input)
        self.status_cb("🚀  Phase 5 · Memory ingestion...")
        self.trace_cb(
            "memory_update_request",
            {
                "user_input": user_input,
                "assistant_response": final_response,
                "persist_memory": persist_memory,
            },
        )
        if persist_memory:
            await self.memoria.update(user_input, final_response)
            self.trace_cb("memory_update_done", {"persisted": True})
        else:
            self.trace_cb("memory_update_done", {"persisted": False, "reason": "non-durable message"})

        auto_refs = bool(self.config.get("auto_save_important_refs", True))
        should_save_session_ref = (
            auto_refs
            and bool(final_response.strip())
            and (
                self._should_persist_memory(user_input)
                or total_tool_calls > 0
            )
        )
        if should_save_session_ref:
            ref = self._save_important_ref_memory(user_input, final_response)
            self.trace_cb(
                "important_ref_saved",
                {
                    "enabled": auto_refs,
                    "saved": bool(ref),
                    "reference": ref or "",
                },
            )

        return final_response

    # ── Auto Title Generation ─────────────────────────────────────────────────

    async def generate_title(self, session: Session) -> str:
        """Generate a session title from the content using the dash-separated 12-word logic."""
        if not session.messages:
            return "New Session"
        
        try:
            # Get rank/count for unique prefix
            all_sessions = Session.list_all()
            unique_num = f"{len(all_sessions) + 1:04d}"
            
            content = session.get_sandwich_content(max_chars=1200) # Fast preview
            prompt = SESSION_RE_TITLE_PROMPT.format(unique_id=unique_num, content=content)
            
            result = await self.api_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.get("model_compress"),
                temperature=0.0,
            )
            title = result.get("content", "").strip().strip('"').strip("'").lower()
            return title or f"{unique_num}-new-session-untitled-conversation-thread-management-system-log"
        except Exception:
            return f"session-{int(time.time())}"
