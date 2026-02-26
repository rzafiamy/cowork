"""
cowork/slash_commands
─────────────────────
Handlers for interactive slash commands (typed inside the REPL).
Each module handles a logical group of /commands.
"""

from .handler import handle_command

__all__ = ["handle_command"]
