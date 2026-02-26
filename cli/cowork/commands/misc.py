"""
cowork/commands/misc.py
───────────────────────
CLI commands: `setup`, `ping`, `tokens`, `reset`.
"""

from __future__ import annotations

import asyncio
import click

from ..ui import print_banner, render_error, render_success, render_token_usage, run_setup_wizard, console
from ..core import _config, _token_tracker, make_api_client, reset_all_cowork_state


@click.command()
def setup() -> None:
    """Run the interactive setup wizard."""
    print_banner()
    run_setup_wizard(_config)


@click.command()
def ping() -> None:
    """Test connectivity to the configured API endpoint."""
    print_banner()
    if not _config.is_configured():
        render_error("Not configured. Run 'cowork setup' first.")
        return

    api_client = make_api_client()

    async def _ping() -> None:
        console.print(f"[muted]Pinging {_config.api_endpoint}...[/muted]")
        ok = await api_client.ping()
        if ok:
            render_success(f"✅ Connected to {_config.api_endpoint}")
            models = await api_client.list_models()
            if models:
                console.print(f"[muted]Available models: {', '.join(models[:5])}{'...' if len(models) > 5 else ''}[/muted]")
        else:
            render_error(f"Cannot reach {_config.api_endpoint}", hint="Check your endpoint URL and network connection.")
        await api_client.close()

    asyncio.run(_ping())


@click.command()
@click.option("--reset", is_flag=True, help="Reset all token usage counters")
def tokens(reset: bool) -> None:
    """Show cumulative token usage per model/endpoint."""
    print_banner()
    if reset:
        if click.confirm("Reset all token usage counters?", default=False):
            _token_tracker.reset()
            render_success("🧹 Token usage counters reset.")
    else:
        render_token_usage(_token_tracker.get_all(), _token_tracker.get_totals())


@click.command()
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def reset(yes: bool) -> None:
    """Destroy all ~/.cowork/* state and start fresh."""
    from ..ui import ThinkingSpinner
    print_banner()
    if not yes and not click.confirm("⚠️  Delete ALL data in ~/.cowork/* ? This cannot be undone.", default=False):
        console.print("[muted]Reset cancelled.[/muted]")
        return

    with ThinkingSpinner("Resetting Cowork state"):
        reset_all_cowork_state()
    render_success("🧹 Reset complete. All ~/.cowork/* data has been deleted.")
