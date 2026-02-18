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
from .config import AgentJob, ConfigManager, JobManager, Scratchpad, Session
from .memoria import Memoria
from .router import MetaRouter
from .theme import (
    GATEWAY_ERROR_PREFIX,
    OP_DEFAULTS,
    TELEMETRY_STEPS,
    TOOL_ERROR_PREFIX,
)
from .tools import ExecutionGateway, ToolExecutor, get_tools_for_categories

# ─── Agent System Prompt ──────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are **Cowork**, a powerful enterprise AI coworker built on the Makix Agentic Architecture.

## 🎭 Persona: The Manager-Worker
You are a **coordinator**, not a verbose assistant. You:
- Think step-by-step before acting
- Use tools efficiently (parallel when possible)
- Never dump raw data — always synthesize insights
- Fail loudly with actionable hints, then self-correct

## 🧠 Core Principles
- **Context is Currency**: Don't waste tokens on raw data
- **Precision over Creativity**: Be deterministic when routing/compressing
- **Parallel-First**: Execute independent tools simultaneously
- **Fail Forward**: On error, self-correct → pivot → ask user → graceful exit

## ⚙️ Tool Usage Rules
1. Call tools when you need real-time data, calculations, or workspace actions
2. For large outputs, use scratchpad_save + ref:key pattern
3. Always check scratchpad_list before assuming data is unavailable
4. On [GATEWAY ERROR]: fix arguments and retry immediately
5. On [TOOL ERROR]: try an alternative tool or inform the user

## 📅 Temporal Context
Current date/time: {current_datetime}

## 🧩 Memory Context
{memory_context}

## 📋 Session Context
Session ID: {session_id}
Messages in context: {message_count}"""

# ─── Context Compressor ───────────────────────────────────────────────────────

class ContextCompressor:
    """
    Manages context window size via Map-Reduce compression.
    Runs at Temperature 0.1 to preserve factual integrity.
    """

    COMPRESS_PROMPT = """You are a context compression engine. Summarize the following conversation history into a concise, information-dense block. Preserve all key facts, decisions, tool results, and user preferences. Remove conversational filler.

Conversation to compress:
{history}

Return a dense summary block starting with: [CONVERSATION SUMMARY]"""

    def __init__(self, api_client: APIClient, config: ConfigManager) -> None:
        self.api_client = api_client
        self.config = config

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
    ) -> list[dict]:
        """
        Optimize context window. Returns compressed messages list.
        Protects: system prompt + last 2 human messages.
        """
        limit = self.config.get("context_limit_tokens", OP_DEFAULTS["context_limit_tokens"])
        estimated = self._estimate_tokens(messages)

        if estimated <= limit:
            return messages

        if status_cb:
            status_cb("🖇️  Context window full — running Map-Reduce compression...")

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
            if m.get("content")
        )

        # Map phase: chunk and summarize
        chunks = self._smart_chunk(history_text, chunk_size=3000)
        summaries = []
        for chunk in chunks:
            try:
                result = await self.api_client.chat(
                    messages=[{"role": "user", "content": self.COMPRESS_PROMPT.format(history=chunk)}],
                    model=self.config.get("model_compress"),
                    temperature=OP_DEFAULTS["temperature_compress"],
                    max_tokens=600,
                )
                summaries.append(result.get("content", ""))
            except Exception:
                summaries.append(chunk[:500] + "... [truncated]")

        # Reduce phase: combine summaries
        combined = "\n\n".join(summaries)
        summary_message = {
            "role": "system",
            "content": f"[CONVERSATION SUMMARY]\n{combined}",
        }

        return [summary_message] + protected


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
    ) -> None:
        self.api_client = api_client
        self.config = config
        self.scratchpad = scratchpad
        self.memoria = memoria
        self.job_manager = job_manager
        self.status_cb = status_callback or (lambda msg: None)
        self.stream_cb = stream_callback or (lambda token: None)

        self.router = MetaRouter(api_client)
        self.compressor = ContextCompressor(api_client, config)
        self.gateway = ExecutionGateway(scratchpad)
        self.executor = ToolExecutor(scratchpad, config, status_callback=self.status_cb)

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
        max_steps = self.config.get("max_steps", OP_DEFAULTS["max_steps"])
        max_tool_calls = self.config.get("max_total_tool_calls", OP_DEFAULTS["max_total_tool_calls"])
        total_tool_calls = 0

        # ── Phase 1: Input Gatekeeper ─────────────────────────────────────────
        self.status_cb("🛡️  Phase 1 · Input Gatekeeper...")
        processed_input = self._gatekeeper(user_input, session)
        trace.add_step("gatekeeper", {"original_len": len(user_input), "processed_len": len(processed_input)})

        # ── Phase 2: Meta-Routing (Brain) ─────────────────────────────────────
        if action_mode:
            # Fast-track: skip router, use predefined categories
            categories = action_mode.get("categories", ["ALL_TOOLS"])
            self.status_cb(f"⚡ Action Mode — bypassing router, using: {', '.join(categories)}")
            routing_info = {"categories": categories, "confidence": 1.0, "reasoning": "Action mode"}
        else:
            self.status_cb("🧭  Phase 2 · Meta-Routing intent classification...")
            routing_info = await self.router.classify(processed_input)
            categories = routing_info["categories"]
            display = self.router.get_category_display(categories)
            self.status_cb(f"🎯  Routed to: {display} (confidence: {routing_info['confidence']:.0%})")

        trace.add_step("routing", routing_info)
        trace.categories = categories
        job.categories = categories

        # ── Memory Context Retrieval ───────────────────────────────────────────
        self.status_cb("🧠  Retrieving memory context...")
        memory_context = self.memoria.get_fused_context(processed_input)

        # ── Build Tool Schema ─────────────────────────────────────────────────
        tools_schema = get_tools_for_categories(categories)

        # ── Build System Prompt ───────────────────────────────────────────────
        system_prompt = AGENT_SYSTEM_PROMPT.format(
            current_datetime=dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            memory_context=memory_context or "(No memory context yet)",
            session_id=session.session_id[:8],
            message_count=len(session.messages),
        )

        # ── Build Messages ────────────────────────────────────────────────────
        chat_history = session.get_chat_messages()
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            *chat_history,
            {"role": "user", "content": processed_input},
        ]

        # ── Phase 3: REACT Loop ───────────────────────────────────────────────
        self.status_cb("🤖  Phase 3 · REACT Execution Loop...")
        final_response = ""

        for step in range(max_steps):
            # Context compression check
            messages = await self.compressor.optimize(messages, system_prompt, self.status_cb)

            self.status_cb(f"🔄  Step {step + 1}/{max_steps} · Reasoning...")
            trace.add_step("react_step_start", {"step": step + 1})

            # LLM call
            try:
                use_stream = self.config.get("stream", True) and bool(self.stream_cb)
                if use_stream and tools_schema:
                    # With tools: non-streaming (tools + streaming is tricky)
                    result = await self.api_client.chat(
                        messages=messages,
                        model=self.config.get("model_text"),
                        temperature=self.config.get("temperature_agent", OP_DEFAULTS["temperature_agent"]),
                        tools=tools_schema if tools_schema else None,
                        max_tokens=4096,
                    )
                elif use_stream and not tools_schema:
                    # Pure text: stream it
                    result = await self.api_client.chat_stream(
                        messages=messages,
                        model=self.config.get("model_text"),
                        temperature=self.config.get("temperature_agent", OP_DEFAULTS["temperature_agent"]),
                        on_chunk=self.stream_cb,
                    )
                else:
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
                return error_msg

            content = result.get("content", "")
            tool_calls = result.get("tool_calls", [])
            finish_reason = result.get("finish_reason", "stop")

            # Append assistant message to context
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            # ── Tool Execution ────────────────────────────────────────────────
            if tool_calls and total_tool_calls < max_tool_calls:
                max_per_step = self.config.get("max_tool_calls_per_step", OP_DEFAULTS["max_tool_calls_per_step"])
                calls_this_step = tool_calls[:max_per_step]

                self.status_cb(f"⚙️  Executing {len(calls_this_step)} tool(s)...")
                trace.add_step("tool_calls", {"count": len(calls_this_step), "tools": [tc["function"]["name"] for tc in calls_this_step]})

                # Execute tools (parallelized)
                async def _exec_one(tc: dict) -> dict:
                    name = tc["function"]["name"]
                    raw_args = tc["function"].get("arguments", {})
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
                    if not ok:
                        return {"tool_call_id": tc["id"], "role": "tool", "content": err}

                    result_str = await asyncio.get_event_loop().run_in_executor(
                        None, self.executor.execute, name, resolved_args
                    )
                    return {"tool_call_id": tc["id"], "role": "tool", "content": result_str}

                tool_results = await asyncio.gather(*[_exec_one(tc) for tc in calls_this_step])
                messages.extend(tool_results)
                total_tool_calls += len(calls_this_step)
                trace.total_tool_calls = total_tool_calls
                continue  # Loop back for next reasoning step

            # ── No more tool calls — we have a final answer ───────────────────
            final_response = content
            trace.add_step("final_answer", {"length": len(content), "finish_reason": finish_reason})
            break

        if not final_response:
            final_response = "I've completed the requested operations. Please let me know if you need anything else."

        trace.finish()
        job.steps = len([s for s in trace.steps if s["type"] == "react_step_start"])
        job.tool_calls = trace.total_tool_calls

        # ── Phase 5: Background Memory Update ────────────────────────────────
        self.status_cb("🚀  Phase 5 · Background memory ingestion...")
        asyncio.create_task(self.memoria.update(user_input, final_response))

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
                    "content": f"Generate a short, descriptive title (max 6 words) for a conversation that starts with: '{first_user[:200]}'. Return ONLY the title, no quotes.",
                }],
                model=self.config.get("model_text"),
                temperature=OP_DEFAULTS["temperature_chat"],
                max_tokens=20,
            )
            return result.get("content", "").strip() or "New Session"
        except Exception:
            return first_user[:40] + "..." if len(first_user) > 40 else first_user
