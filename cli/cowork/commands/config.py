"""
cowork/commands/config.py
─────────────────────────
CLI command: `config`.
"""

from __future__ import annotations

import click

from ..config import is_sensitive_key
from ..ui import print_banner, render_config, render_success
from ..core import _config


@click.command()
@click.option("--set", "set_values", nargs=2, multiple=True, metavar="KEY VALUE", help="Set a config value")
def config(set_values: tuple) -> None:
    """Show or update configuration."""
    print_banner()
    if set_values:
        for key, value in set_values:
            try:
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                elif "." in value:
                    value = float(value)
                else:
                    value = int(value)
            except (ValueError, AttributeError):
                pass
            _config.set(key, value)
            shown_value = "●●●●●●●●" if is_sensitive_key(key) and value else value
            render_success(f"Set {key} = {shown_value}")
    else:
        render_config(_config.all())
