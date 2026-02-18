"""
📡 API Client
Async wrapper around any OpenAI-compatible endpoint.
Supports streaming, tool calls, exponential backoff, and JSON mode.
"""

import asyncio
import json
import time
from typing import Any, AsyncIterator, Callable, Optional

import httpx

from .theme import OP_DEFAULTS


class APIError(Exception):
    """Raised when the API returns an unrecoverable error."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class APIClient:
    """
    Async HTTP client for OpenAI-compatible inference endpoints.
    Implements exponential backoff (3 attempts) for fatal network errors.
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds

    def __init__(self, endpoint: str, api_key: str, timeout: float = 60.0) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Core Chat Completion ──────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.4,
        tools: Optional[list[dict]] = None,
        tool_choice: str = "auto",
        response_format: Optional[dict] = None,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Non-streaming chat completion. Returns the assistant message dict.
        Implements exponential backoff on failure.
        """
        payload: dict[str, Any] = {
            "model": model or "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        if response_format:
            payload["response_format"] = response_format

        last_error: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES):
            try:
                client = self._get_client()
                resp = await client.post("/chat/completions", json=payload)
                if resp.status_code == 429:
                    # Rate limit — back off
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                if resp.status_code >= 500:
                    raise APIError(f"Server error {resp.status_code}", resp.status_code)
                if resp.status_code >= 400:
                    body = resp.text
                    raise APIError(f"Client error {resp.status_code}: {body}", resp.status_code)

                data = resp.json()
                choice = data["choices"][0]
                msg = choice["message"]
                return {
                    "role": msg.get("role", "assistant"),
                    "content": msg.get("content") or "",
                    "tool_calls": msg.get("tool_calls") or [],
                    "finish_reason": choice.get("finish_reason", "stop"),
                    "usage": data.get("usage", {}),
                }
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
                last_error = e
                delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
            except APIError:
                raise
            except Exception as e:
                last_error = e
                break

        raise APIError(f"API call failed after {self.MAX_RETRIES} attempts: {last_error}")

    # ── Streaming Chat Completion ─────────────────────────────────────────────

    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.4,
        tools: Optional[list[dict]] = None,
        tool_choice: str = "auto",
        max_tokens: int = 4096,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """
        Streaming chat completion.
        Calls on_chunk(text) for each streamed token.
        Returns the full assembled message dict when done.
        """
        payload: dict[str, Any] = {
            "model": model or "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        full_content = ""
        tool_calls_raw: dict[int, dict] = {}
        finish_reason = "stop"

        client = self._get_client()
        async with client.stream("POST", "/chat/completions", json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise APIError(f"Stream error {resp.status_code}: {body.decode()}", resp.status_code)

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                finish_reason = choice.get("finish_reason") or finish_reason

                # Accumulate text content
                if delta.get("content"):
                    token = delta["content"]
                    full_content += token
                    if on_chunk:
                        on_chunk(token)

                # Accumulate tool calls
                for tc in delta.get("tool_calls", []):
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_raw:
                        tool_calls_raw[idx] = {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    fn = tc.get("function", {})
                    if fn.get("name"):
                        tool_calls_raw[idx]["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        tool_calls_raw[idx]["function"]["arguments"] += fn["arguments"]
                    if tc.get("id"):
                        tool_calls_raw[idx]["id"] = tc["id"]

        # Parse assembled tool calls
        tool_calls = []
        for idx in sorted(tool_calls_raw.keys()):
            tc = tool_calls_raw[idx]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": args,
                },
            })

        return {
            "role": "assistant",
            "content": full_content,
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
        }

    # ── Model Listing ─────────────────────────────────────────────────────────

    async def list_models(self) -> list[str]:
        """Fetch available model IDs from the endpoint."""
        try:
            client = self._get_client()
            resp = await client.get("/models")
            if resp.status_code == 200:
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            pass
        return []

    # ── Health Check ──────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Quick connectivity check."""
        try:
            client = self._get_client()
            resp = await client.get("/models", timeout=5.0)
            return resp.status_code < 500
        except Exception:
            return False
