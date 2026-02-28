"""
cowork/slash_commands/ai_cmd.py
────────────────────────────────
Handlers for /ai, /model, and /mm slash commands.
"""

from __future__ import annotations

from typing import Optional

from ..config import Session
from ..ui import (
    ThinkingSpinner,
    console,
    render_ai_profiles,
    render_current_models,
    render_error,
    render_model_list,
    render_success,
    render_warning,
)
from ..core import _config, _ai_profiles


async def handle_ai(
    cmd: str,
    parts: list[str],
) -> tuple[bool, Optional[Session], bool]:
    """Handle /ai command."""
    sub = parts[1].lower() if len(parts) > 1 else ""

    if not sub or sub == "list":
        render_ai_profiles(_ai_profiles.list_all())

    elif sub == "add":
        raw = cmd.split(maxsplit=5)
        if len(raw) < 5:
            render_error(
                "Usage: /ai add <name> <endpoint> <model> [description]",
                hint="Example: /ai add gpt4 https://api.openai.com/v1 gpt-4o My GPT-4 profile",
            )
        else:
            name, endpoint, model = raw[2], raw[3], raw[4]
            description = raw[5] if len(raw) > 5 else ""
            _ai_profiles.add(name=name, endpoint=endpoint, model=model, description=description)
            render_success(f"✅ AI profile '{name}' saved ({model} @ {endpoint})")

    elif sub == "switch":
        if len(parts) < 3:
            render_error("Usage: /ai switch <name>")
        else:
            name = parts[2]
            profile = _ai_profiles.switch(name)
            if profile:
                render_success(
                    f"🤖 Switched to profile '[highlight]{name}[/highlight]'\n"
                    f"   Model: {profile.model}\n"
                    f"   Endpoint: {profile.endpoint}"
                )
                return True, None, True  # needs_rebuild = True
            else:
                render_error(f"Profile '{name}' not found.", hint="Use /ai to list available profiles.")

    elif sub == "remove":
        if len(parts) < 3:
            render_error("Usage: /ai remove <name>")
        else:
            name = parts[2]
            if _ai_profiles.remove(name):
                render_success(f"🗑️  Profile '{name}' removed.")
            else:
                render_error(f"Profile '{name}' not found.")

    elif sub == "save":
        name = parts[2] if len(parts) > 2 else "default"
        _ai_profiles.snapshot_current(_config, name)
        render_success(
            f"💾 Saved current config as profile '[highlight]{name}[/highlight]'\n"
            f"   Model: {_config.model_text}\n"
            f"   Endpoint: {_config.api_endpoint}"
        )

    else:
        render_warning(f"Unknown /ai subcommand: {sub}. Use /ai, /ai add, /ai switch, /ai remove, /ai save.")

    return True, None, False


async def handle_model(
    parts: list[str],
    api_client,
) -> tuple[bool, Optional[Session], bool]:
    """Handle /model command."""
    if len(parts) > 1:
        sub = parts[1].lower()
        if sub == "list":
            with ThinkingSpinner("Fetching models"):
                models = await api_client.list_models()
            render_model_list(models, _config.model_text)
            return True, None, False

        new_model = parts[1]
        _config.set_core_models(new_model)

        render_success(f"🤖 Core models (text, router, compress) switched to: [highlight]{new_model}[/highlight]")
        return True, None, True  # needs_rebuild = True
    else:
        # Show current configuration
        render_current_models(_config.all())

    return True, None, False


async def handle_mm(
    cmd: str,
    parts: list[str],
) -> tuple[bool, Optional[Session], bool]:
    """Handle /mm command."""
    from rich.table import Table
    from rich import box

    mm_parts = cmd.strip().split(maxsplit=3)
    sub = mm_parts[1].lower() if len(mm_parts) > 1 else "status"
    MM_SERVICES = {
        "vision": ("mm_vision_endpoint", "mm_vision_token", "mm_vision_model", "👁️  Vision (Image Analysis)"),
        "images": ("mm_image_endpoint",  "mm_image_token",  "mm_image_model",  "🎨 Image Generation"),
        "asr":    ("mm_asr_endpoint",    "mm_asr_token",    "mm_asr_model",    "🎤 Speech-to-Text (ASR)"),
        "tts":    ("mm_tts_endpoint",    "mm_tts_token",    "mm_tts_model",    "🔊 Text-to-Speech (TTS)"),
    }

    if sub == "status" or sub not in MM_SERVICES:
        table = Table(title="🎨 Multi-Modal Services", box=box.ROUNDED, border_style="primary")
        table.add_column("Service", style="highlight", min_width=28)
        table.add_column("Endpoint", style="text")
        table.add_column("Model", style="muted")
        table.add_column("Token", style="success", justify="center")
        for svc_key, (ep_key, tok_key, mdl_key, label) in MM_SERVICES.items():
            ep  = _config.get(ep_key, "") or ""
            tok = _config.get(tok_key, "") or ""
            mdl = _config.get(mdl_key, "") or ""
            table.add_row(
                label,
                ep[:50] if ep else "[muted]—[/muted]",
                mdl if mdl else "[muted]—[/muted]",
                "✅" if (ep and tok) else "❌",
            )
        console.print(table)
        console.print()
        console.print("[dim_text]  Usage:[/dim_text]")
        console.print("[dim_text]  /mm vision endpoint <url>   — set vision endpoint[/dim_text]")
        console.print("[dim_text]  /mm vision token <key>      — set vision API key[/dim_text]")
        console.print("[dim_text]  /mm vision model <name>     — set vision model[/dim_text]")
        console.print("[dim_text]  /mm images|asr|tts ...      — same for other services[/dim_text]")

    elif sub in MM_SERVICES:
        ep_key, tok_key, mdl_key, label = MM_SERVICES[sub]
        if len(mm_parts) < 4:
            render_error(
                f"Usage: /mm {sub} <endpoint|token|model> <value>",
                hint=f"Example: /mm {sub} endpoint https://api.openai.com/v1",
            )
        else:
            field = mm_parts[2].lower()
            value = mm_parts[3].strip() if len(mm_parts) > 3 else ""
            if field == "endpoint":
                _config.set(ep_key, value.rstrip("/"))
                render_success(f"✅ {label} endpoint set to: {value}")
            elif field in ("token", "key"):
                _config.set(tok_key, value)
                render_success(f"✅ {label} token updated. (stored in memory, not persisted to disk)")
            elif field == "model":
                _config.set(mdl_key, value)
                render_success(f"✅ {label} model set to: {value}")
            else:
                render_error(f"Unknown field '{field}'. Use: endpoint, token, model.")

    return True, None, False
