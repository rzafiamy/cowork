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
from .prompts import AGENT_CHAT_SYSTEM_PROMPT, AGENT_SYSTEM_PROMPT, COMPRESS_PROMPT, TITLE_GENERATION_PROMPT
from .memoria import Memoria
from .router import MetaRouter
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
# Import: AGENT_SYSTEM_PROMPT, COMPRESS_PROMPT, TITLE_GENERATION_PROMPT

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
        summary_message = {
            "role": "system",
            "content": (
                f"[CONVERSATION SUMMARY]\n"
                f"{f'Source archived at {source_ref}\\n' if source_ref else ''}"
                f"{combined}"
            ),
        }

        # ALWAYS keep original system prompt at index 0 if it was role: system
        system_msg = messages[0] if messages and messages[0].get("role") == "system" else {"role": "system", "content": system_prompt}

        return [system_msg, summary_message] + protected


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
        self.gateway = ExecutionGateway(scratchpad)
        self.executor = ToolExecutor(scratchpad, config, status_callback=self.status_cb)
        self.firewall = FirewallManager()

    def _is_simple_conversational_turn(self, text: str) -> bool:
        """
        Heuristic fast-path:
        short conceptual questions with no obvious action/external-data verbs.
        """
        t = text.strip().lower()
        if not t or len(t) > 220:
            return False
        action_verbs = [
            "search", "find", "look up", "latest", "today", "current", "news",
            "weather", "price", "stock", "scrape", "crawl", "fetch", "download",
            "send", "email", "post", "publish", "save", "store", "schedule",
            "book", "create file", "write file", "build", "develop", "implement",
            "website", "landing page", "frontend", "backend", "#coding", "#code",
        ]
        if any(v in t for v in action_verbs):
            return False
        return "?" in t or len(t.split()) <= 20

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
        """
        text = user_input.strip().lower()
        if not text:
            return False
        durable_patterns = [
            r"\bi am\b", r"\bmy name is\b", r"\bi live in\b", r"\bi work as\b",
            r"\bi prefer\b", r"\bi like\b", r"\bi dislike\b", r"\balways\b", r"\bnever\b",
            r"\bmy goal is\b", r"\bi'm working on\b", r"\bwe are building\b",
            r"\bremember\b", r"\bsave this\b", r"\bfor future\b", r"\bimportant\b", r"\bnote this\b",
        ]
        return any(re.search(p, text) for p in durable_patterns)

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
                "tool_probability": 1.0,
            }
        elif self._is_simple_conversational_turn(processed_input):
            categories = ["CONVERSATIONAL_ONLY"]
            routing_info = {
                "categories": categories,
                "confidence": 0.95,
                "reasoning": "Fast-path conversational turn (skipped full router).",
                "tool_probability": 0.1,
            }
            self.status_cb("⚡ Fast-path: conversational-only turn.")
        else:
            self.status_cb("🧭  Phase 2 · Meta-Routing intent classification...")
            self.trace_cb("router_request", {"prompt": processed_input})
            routing_info = await self.router.classify(processed_input)
            categories = routing_info["categories"]
            display = self.router.get_category_display(categories)
            self.status_cb(f"🎯  Routed to: {display} (confidence: {routing_info['confidence']:.0%})")

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
        trace.categories = categories
        job.categories = categories

        # ── Memory Context Retrieval ───────────────────────────────────────────
        memory_context = ""
        if "CONVERSATIONAL_ONLY" not in categories:
            self.status_cb("🧠  Retrieving memory context...")
            memory_context = self.memoria.get_fused_context(processed_input)
            self.trace_cb("memory_context", {"memory_context": memory_context})
        else:
            self.trace_cb("memory_context", {"memory_context": "", "skipped": True})

        # ── Build Tool Schema (Filters out unconfigured paid tools) ───────────
        tools_schema = [] if "CONVERSATIONAL_ONLY" in categories else get_available_tools_for_categories(categories)
        self.trace_cb(
            "tools_schema_selected",
            {
                "categories": categories,
                "tool_names": [t["function"]["name"] for t in tools_schema],
                "tools_schema": tools_schema,
                "bypass_tool_schema": "CONVERSATIONAL_ONLY" in categories,
            },
        )

        if tools_schema:
            premium_tools = [t["function"]["name"] for t in tools_schema if t["category"] in categories and t["category"] != "CONVERSATIONAL"]
            if premium_tools:
                self.status_cb(f"🔌 Enabled {len(premium_tools)} tool(s) for this task.")

        # ── Build System Prompt ───────────────────────────────────────────────
        current_dt = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
        if "CONVERSATIONAL_ONLY" in categories:
            system_prompt = AGENT_CHAT_SYSTEM_PROMPT.format(
                current_datetime=current_dt,
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
            )

        # ── Build Messages ────────────────────────────────────────────────────
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
                                "content": f"{GATEWAY_ERROR_PREFIX} Invalid JSON arguments. [HINT]: Correct the JSON syntax.",
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
                        return {"tool_call_id": tc["id"], "role": "tool", "content": err}

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
                    return {"tool_call_id": tc["id"], "role": "tool", "content": result_str}

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
        """Generate a session title from the first exchange."""
        if len(session.messages) < 2:
            return "New Session"
        first_user = next((m["content"] for m in session.messages if m["role"] == "user"), "")
        try:
            result = await self.api_client.chat(
                messages=[{
                    "role": "user",
                    "content": TITLE_GENERATION_PROMPT.format(first_user=first_user[:200]),
                }],
                model=self.config.get("model_text"),
                temperature=OP_DEFAULTS["temperature_chat"],
                max_tokens=20,
            )
            return result.get("content", "").strip() or "New Session"
        except Exception:
            return first_user[:40] + "..." if len(first_user) > 40 else first_user
