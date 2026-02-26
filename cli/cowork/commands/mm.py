"""
cowork/commands/mm.py
─────────────────────
CLI command: `mm` group (multi-modal services).
"""

from __future__ import annotations

import click

from ..ui import print_banner, render_success
from ..core import _config


@click.group()
def mm() -> None:
    """Manage multi-modal service endpoints (vision, images, ASR, TTS)."""
    pass


@mm.command(name="status")
def mm_status() -> None:
    """Show current multi-modal service configuration."""
    print_banner()
    from rich.table import Table
    from rich import box
    from ..ui import console

    MM_SERVICES = {
        "vision": ("mm_vision_endpoint", "mm_vision_token", "mm_vision_model", "👁️  Vision (Image Analysis)"),
        "images": ("mm_image_endpoint",  "mm_image_token",  "mm_image_model",  "🎨 Image Generation"),
        "asr":    ("mm_asr_endpoint",    "mm_asr_token",    "mm_asr_model",    "🎤 Speech-to-Text (ASR)"),
        "tts":    ("mm_tts_endpoint",    "mm_tts_token",    "mm_tts_model",    "🔊 Text-to-Speech (TTS)"),
    }
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
            ep[:55] if ep else "[muted]—[/muted]",
            mdl if mdl else "[muted]—[/muted]",
            "✅" if (ep and tok) else "❌",
        )
    console.print(table)


@mm.command(name="set")
@click.argument("service", type=click.Choice(["vision", "images", "asr", "tts"]))
@click.argument("field", type=click.Choice(["endpoint", "token", "model"]))
@click.argument("value")
def mm_set(service: str, field: str, value: str) -> None:
    """Set a multi-modal service property (endpoint/token/model)."""
    MM_KEYS = {
        "vision": ("mm_vision_endpoint", "mm_vision_token", "mm_vision_model", "👁️  Vision"),
        "images": ("mm_image_endpoint",  "mm_image_token",  "mm_image_model",  "🎨 Image Generation"),
        "asr":    ("mm_asr_endpoint",    "mm_asr_token",    "mm_asr_model",    "🎤 ASR"),
        "tts":    ("mm_tts_endpoint",    "mm_tts_token",    "mm_tts_model",    "🔊 TTS"),
    }
    ep_key, tok_key, mdl_key, label = MM_KEYS[service]
    if field == "endpoint":
        _config.set(ep_key, value.rstrip("/"))
        render_success(f"✅ {label} endpoint set to: {value}")
    elif field == "token":
        _config.set(tok_key, value)
        render_success(f"✅ {label} token updated. (stored in memory, not persisted to disk)")
    elif field == "model":
        _config.set(mdl_key, value)
        render_success(f"✅ {label} model set to: {value}")
