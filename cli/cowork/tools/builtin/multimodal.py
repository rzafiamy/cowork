"""
🎨 Multi-Modal Tools
Vision/image analysis, image generation, speech-to-text (ASR), and text-to-speech (TTS).
All file I/O is routed through file_manager (ACL-enforced).

Each tool uses its own configurable endpoint + API key so users can point them at any
OpenAI-compatible multi-modal service (OpenAI, Together AI, Replicate, local Whisper, etc.).

Configuration keys (set via /mm or /config set):
  mm_vision_endpoint    e.g. https://api.openai.com/v1
  mm_vision_token       API key for the vision service
  mm_vision_model       Default model (e.g. gpt-4o, llava-1.5-7b)

  mm_image_endpoint     e.g. https://api.openai.com/v1
  mm_image_token        API key for the image generation service
  mm_image_model        Default model (e.g. dall-e-3, stable-diffusion-xl)

  mm_asr_endpoint       e.g. https://api.openai.com/v1
  mm_asr_token          API key for the ASR (Whisper) service
  mm_asr_model          Default model (e.g. whisper-1)

  mm_tts_endpoint       e.g. https://api.openai.com/v1
  mm_tts_token          API key for the TTS service
  mm_tts_model          Default model (e.g. tts-1, tts-1-hd)
  mm_tts_voice          Forced voice (e.g. alloy, echo, fable, onyx, nova, shimmer)

API Design (OpenAI-compatible):
  POST /v1/recognize                — Vision / Image analysis
  POST /v1/images/generations       — Image generation
  POST /v1/audio/transcriptions     — Speech-to-Text (STT/ASR)
  POST /v1/audio/speech             — Text-to-Speech (TTS)
"""

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import BaseTool
from .utility import sanitize_for_audio
from ...workspace import workspace_manager, WORKSPACE_ROOT
from ...acl import file_manager


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_artifacts_dir(scratchpad) -> Path:
    """Return the workspace artifacts/ path, falling back to WORKSPACE_ROOT."""
    if scratchpad:
        ws = workspace_manager.get_by_session_id(scratchpad.session_id)
        if ws:
            return ws.artifacts_path
    return WORKSPACE_ROOT / "artifacts"


def _safe_filename(name: str) -> str:
    """Strip path traversal, keep only the base name."""
    return Path(name).name


def _cfg(config, key: str, fallback: str = "", global_key: str = "") -> str:
    """
    Read a config value with priority:
    1. The specific MM key (e.g. mm_vision_endpoint)
    2. The global agent key if specific is missing (e.g. api_endpoint)
    3. The hardcoded fallback string.
    """
    if config is None:
        return fallback
    
    # 1. Try specific MM key
    val = str(config.get(key, "")).strip()
    
    # 2. Try global fallback if MM key is empty
    if not val and global_key:
        val = str(config.get(global_key, "")).strip()
        
    return val or fallback


def _post_json(endpoint: str, token: str, path: str, payload: dict) -> dict:
    """
    Synchronous HTTP POST with JSON body — used for image generation and TTS
    where we receive JSON back. Returns parsed response dict.
    Raises RuntimeError on HTTP or network errors.
    """
    import httpx
    url = endpoint.rstrip("/") + path
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120) as client:
        resp = client.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _post_multipart(endpoint: str, token: str, path: str, fields: dict, file_bytes: bytes, filename: str, mime: str) -> dict:
    """
    Synchronous multipart/form-data POST — used for vision (image file) and ASR (audio file).
    Returns parsed JSON response.
    Raises RuntimeError on HTTP or network errors.
    """
    import httpx
    url = endpoint.rstrip("/") + path
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, file_bytes, mime)}
    with httpx.Client(timeout=120) as client:
        resp = client.post(url, data=fields, files=files, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _post_binary(endpoint: str, token: str, path: str, payload: dict) -> bytes:
    """
    Synchronous HTTP POST returning raw bytes — used for TTS audio download.
    Raises RuntimeError on HTTP or network errors.
    """
    import httpx
    url = endpoint.rstrip("/") + path
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=120) as client:
        resp = client.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.content


# ─── Vision / Image Analysis ─────────────────────────────────────────────────

class VisionAnalyzeTool(BaseTool):
    """
    Analyse an image file using a vision-capable model.

    Calls POST /v1/recognize with multipart/form-data:
        file    — the image file
        model   — vision model name
        prompt  — instruction / question about the image
    """

    @property
    def name(self) -> str:
        return "vision_analyze"

    @property
    def description(self) -> str:
        return (
            "Analyze or describe the content of an image file using a vision model. "
            "Pass the path to a local image file (JPEG, PNG, GIF, WEBP). "
            "Optionally specify a prompt (question or instruction) and model. "
            "Returns a textual description or answer. "
            "Requires mm_vision_endpoint and mm_vision_token to be configured."
        )

    @property
    def category(self) -> str:
        return "MULTIMODAL_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or workspace-relative path to the image file to analyze.",
                },
                "prompt": {
                    "type": "string",
                    "description": "Question or instruction for the vision model, e.g. 'Describe this image in detail.' (optional)",
                },
            },
            "required": ["file_path"],
        }

    def execute(self, file_path: str, prompt: str = "Describe this image in detail.") -> str:
        endpoint = _cfg(self.config, "mm_vision_endpoint", global_key="api_endpoint")
        token    = _cfg(self.config, "mm_vision_token",    global_key="api_key")
        
        if not endpoint or not token:
            return (
                "❌ Vision service not configured and no global AI endpoint/key found.\n"
                "[HINT]: Set mm_vision_endpoint or ensure your main AI provider is active."
            )

        model = _cfg(self.config, "mm_vision_model", fallback="gpt-4o", global_key="model_text")
        self._emit(f"👁️  Analyzing image: '{Path(file_path).name}'...")

        # Resolve file path
        p = Path(file_path)
        if not p.is_absolute():
            p = WORKSPACE_ROOT / file_path
        if not file_manager.exists(p):
            return f"❌ File not found: {p}"

        file_bytes = file_manager.read_bytes(p, reason=f"vision_analyze: {p.name}")
        mime = mimetypes.guess_type(str(p))[0] or "image/jpeg"

        try:
            result = _post_multipart(
                endpoint=endpoint,
                token=token,
                path="/v1/recognize",
                fields={"model": model, "prompt": prompt},
                file_bytes=file_bytes,
                filename=p.name,
                mime=mime,
            )
        except RuntimeError as e:
            return f"❌ Vision API error: {e}"
        except Exception as e:
            return f"❌ Unexpected error: {e}"

        # Extract text from response (OpenAI-style or vendor-specific)
        text = (
            result.get("text")  # simple flat response
            or result.get("content")
            or (result.get("choices", [{}])[0].get("message", {}).get("content", ""))
            or json.dumps(result, indent=2)
        )
        return f"🖼️  Vision Analysis — `{p.name}`\n\n{text}"


# ─── Image Generation ─────────────────────────────────────────────────────────

class ImageGenerateTool(BaseTool):
    """
    Generate an image from a text prompt.

    Calls POST /v1/images/generations and saves the result to the workspace
    artifacts folder. Returns the saved file path.
    """

    @property
    def name(self) -> str:
        return "image_generate"

    @property
    def description(self) -> str:
        return (
            "Generate one or more images from a text prompt using an image generation model. "
            "Saves the result to the workspace artifacts folder and returns the file path(s). "
            "Requires mm_image_endpoint and mm_image_token to be configured."
        )

    @property
    def category(self) -> str:
        return "MULTIMODAL_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text description of the image to generate.",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of images to generate (default: 1, max: 10).",
                },
                "size": {
                    "type": "string",
                    "description": "Image dimensions, e.g. '1024x1024', '1792x1024', '512x512' (model-dependent).",
                },
                "response_format": {
                    "type": "string",
                    "description": "Response format: 'url' (link only) or 'b64_json' (base64, saved to file). Default: 'b64_json'.",
                },
                "filename_prefix": {
                    "type": "string",
                    "description": "Optional prefix for saved files, e.g. 'banner'. Files are saved as prefix_0.png, etc.",
                },
            },
            "required": ["prompt"],
        }

    def execute(
        self,
        prompt: str,
        n: int = 1,
        size: str = "1024x1024",
        response_format: str = "b64_json",
        filename_prefix: str = "generated",
    ) -> str:
        endpoint = _cfg(self.config, "mm_image_endpoint", global_key="api_endpoint")
        token    = _cfg(self.config, "mm_image_token",    global_key="api_key")
        
        if not endpoint or not token:
            return (
                "❌ Image generation service not configured and no global AI endpoint/key found.\n"
                "[HINT]: Set mm_image_endpoint or ensure your main AI provider is active."
            )

        model = _cfg(self.config, "mm_image_model", fallback="dall-e-3")
        n = max(1, min(n, 10))
        response_format = response_format if response_format in ("url", "b64_json") else "b64_json"

        self._emit(f"🎨 Generating {n} image(s) with {model}...")

        payload: dict = {
            "prompt": prompt,
            "model": model,
            "n": n,
            "size": size,
            "response_format": response_format,
        }

        try:
            result = _post_json(endpoint, token, "/v1/images/generations", payload)
        except RuntimeError as e:
            return f"❌ Image generation API error: {e}"
        except Exception as e:
            return f"❌ Unexpected error: {e}"

        images = result.get("data", [])
        if not images:
            return f"❌ No images returned. Full response:\n{json.dumps(result, indent=2)}"

        artifacts_dir = _get_artifacts_dir(self.scratchpad)
        saved_paths = []
        urls = []

        for i, img in enumerate(images):
            if response_format == "b64_json" and img.get("b64_json"):
                raw = base64.b64decode(img["b64_json"])
                safe_prefix = _safe_filename(filename_prefix) or "generated"
                fname = f"{safe_prefix}_{i}.png"
                out_path = artifacts_dir / fname
                file_manager.write_bytes(out_path, raw, reason=f"image_generate: {fname}")
                saved_paths.append(str(out_path))
            elif img.get("url"):
                urls.append(img["url"])

        lines = [f"✅ Image generation complete — model: `{model}`"]
        if saved_paths:
            lines.append(f"• Saved {len(saved_paths)} file(s):")
            for p in saved_paths:
                lines.append(f"  - `{p}`")
        if urls:
            lines.append(f"• Image URL(s):")
            for u in urls:
                lines.append(f"  - {u}")
        if not saved_paths and not urls:
            lines.append(f"• Raw response:\n{json.dumps(result, indent=2)}")

        return "\n".join(lines)


# ─── Speech-to-Text (ASR / Transcription) ────────────────────────────────────

class SpeechToTextTool(BaseTool):
    """
    Transcribe an audio file to text using a Whisper-compatible ASR service.

    Calls POST /v1/audio/transcriptions with multipart/form-data:
        file      — audio file
        model     — ASR model name
        language  — optional ISO-639-1 language code
    """

    @property
    def name(self) -> str:
        return "speech_to_text"

    @property
    def description(self) -> str:
        return (
            "Transcribe an audio file (MP3, WAV, M4A, FLAC, OGG, WEBM) to text using a "
            "Whisper-compatible ASR service. Returns the transcription text. "
            "Requires mm_asr_endpoint and mm_asr_token to be configured."
        )

    @property
    def category(self) -> str:
        return "MULTIMODAL_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or workspace-relative path to the audio file.",
                },
                "language": {
                    "type": "string",
                    "description": "Optional ISO-639-1 language code (e.g. 'en', 'fr', 'de'). Auto-detected if omitted.",
                },
            },
            "required": ["file_path"],
        }

    def execute(self, file_path: str, language: str = "") -> str:
        endpoint = _cfg(self.config, "mm_asr_endpoint", global_key="api_endpoint")
        token    = _cfg(self.config, "mm_asr_token",    global_key="api_key")
        
        if not endpoint or not token:
            return (
                "❌ ASR service not configured and no global AI endpoint/key found.\n"
                "[HINT]: Set mm_asr_endpoint or ensure your main AI provider is active."
            )

        model = _cfg(self.config, "mm_asr_model", fallback="whisper-1")

        # Resolve file path
        p = Path(file_path)
        if not p.is_absolute():
            p = WORKSPACE_ROOT / file_path
        if not file_manager.exists(p):
            return f"❌ File not found: {p}"

        self._emit(f"🎤 Transcribing audio: '{p.name}'...")

        file_bytes = file_manager.read_bytes(p, reason=f"speech_to_text: {p.name}")
        mime = mimetypes.guess_type(str(p))[0] or "audio/mpeg"

        fields: dict = {"model": model}
        if language:
            fields["language"] = language

        try:
            result = _post_multipart(
                endpoint=endpoint,
                token=token,
                path="/v1/audio/transcriptions",
                fields=fields,
                file_bytes=file_bytes,
                filename=p.name,
                mime=mime,
            )
        except RuntimeError as e:
            return f"❌ ASR API error: {e}"
        except Exception as e:
            return f"❌ Unexpected error: {e}"

        text = result.get("text", "") or json.dumps(result, indent=2)
        duration = result.get("duration")
        lang_detected = result.get("language", language or "auto")

        lines = [f"🎤 Transcription — `{p.name}`"]
        if duration:
            lines.append(f"• Duration: {duration:.1f}s | Language: {lang_detected}")
        lines.append("")
        lines.append(text)
        return "\n".join(lines)


# ─── Text-to-Speech (TTS) ─────────────────────────────────────────────────────

class TextToSpeechTool(BaseTool):
    """
    Convert text to speech audio using a TTS service.

    Calls POST /v1/audio/speech and saves the audio to the workspace artifacts folder.
    """

    @property
    def name(self) -> str:
        return "text_to_speech"

    @property
    def description(self) -> str:
        return (
            "Convert text to speech audio and save to the workspace artifacts folder. "
            "Returns the path to the saved audio file. "
            "Uses voice from mm_tts_voice config/env (LLM cannot override it). "
            "Requires mm_tts_endpoint and mm_tts_token to be configured."
        )

    @property
    def category(self) -> str:
        return "MULTIMODAL_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "The text to convert to speech (max ~4096 characters).",
                },
                "input_ref": {
                    "type": "string",
                    "description": "Optional scratchpad reference or text fallback. Use ref:last_assistant_response for exact replay.",
                },
                "response_format": {
                    "type": "string",
                    "description": "Output format: 'mp3' (default), 'opus', 'aac', 'flac', 'wav', or 'pcm'.",
                },
                "filename": {
                    "type": "string",
                    "description": "Output filename, e.g. 'speech.mp3'. Auto-generated if omitted.",
                },
            },
            "required": [],
        }

    def execute(
        self,
        input: str = "",
        input_ref: str = "",
        response_format: str = "mp3",
        filename: str = "",
        voice: str = "",
    ) -> str:
        endpoint = _cfg(self.config, "mm_tts_endpoint", global_key="api_endpoint")
        token    = _cfg(self.config, "mm_tts_token",    global_key="api_key")
        
        if not endpoint or not token:
            return (
                "❌ TTS service not configured and no global AI endpoint/key found.\n"
                "[HINT]: Set mm_tts_endpoint or ensure your main AI provider is active."
            )

        model = _cfg(self.config, "mm_tts_model", fallback="tts-1")
        forced_voice = _cfg(self.config, "mm_tts_voice", fallback="")
        valid_formats = ("mp3", "opus", "aac", "flac", "wav", "pcm")
        response_format = response_format if response_format in valid_formats else "mp3"
        source_text = (input or "").strip() or (input_ref or "").strip()
        sanitized_input = sanitize_for_audio(source_text)
        if not sanitized_input:
            return "❌ TTS input is empty after sanitization."

        self._emit(f"🔊 Generating TTS audio (voice: {forced_voice}, model: {model})...")

        payload = {
            "model": model,
            "input": sanitized_input[:4096],  # Safety clamp
            "voice": forced_voice,
            "response_format": response_format,
        }

        try:
            audio_bytes = _post_binary(endpoint, token, "/v1/audio/speech", payload)
        except RuntimeError as e:
            return f"❌ TTS API error: {e}"
        except Exception as e:
            return f"❌ Unexpected error: {e}"

        # Save to workspace artifacts
        artifacts_dir = _get_artifacts_dir(self.scratchpad)
        if filename:
            safe_name = _safe_filename(filename)
            # Ensure correct extension
            if not safe_name.endswith(f".{response_format}"):
                safe_name = f"{Path(safe_name).stem}.{response_format}"
        else:
            import time as _time
            safe_name = f"speech_{int(_time.time())}.{response_format}"

        out_path = artifacts_dir / safe_name
        file_manager.write_bytes(out_path, audio_bytes, reason=f"text_to_speech: {safe_name}")
        size_kb = out_path.stat().st_size // 1024

        return (
            f"✅ TTS audio generated!\n"
            f"• File: `{out_path.name}`\n"
            f"• Path: `{out_path}`\n"
            f"• Size: {size_kb} KB\n"
            f"• Voice: {forced_voice} | Model: {model} | Format: {response_format}\n"
            f"• Characters: {len(sanitized_input)}"
        )
