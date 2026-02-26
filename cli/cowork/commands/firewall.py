"""
cowork/commands/firewall.py
───────────────────────────
CLI command: `firewall`.
"""

from __future__ import annotations

import click
import yaml
from ..config import FirewallManager, FIREWALL_FILE, FirewallAction
from ..ui import print_banner, render_success, render_error, console
from rich.table import Table
from rich.panel import Panel

@click.group(invoke_without_command=True)
@click.pass_context
def firewall(ctx: click.Context) -> None:
    """🛡️ Manage the tool execution firewall."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_rules)

@firewall.command(name="list")
def list_rules() -> None:
    """List all firewall rules."""
    print_banner()
    fw = FirewallManager()
    rules = fw._rules
    
    # Global Policy
    policy = rules.get("policy", {})
    default_action = str(policy.get("default_action", "ask")).lower()
    
    action_color = "success" if default_action == "allow" else "warning" if default_action == "ask" else "error"
    console.print(f"  [bold]Global Policy: [{action_color}]{default_action.upper()}[/{action_color}][/bold]")
    console.print()
    
    # Blacklist
    blacklist = rules.get("blacklist", [])
    if blacklist:
        table = Table(title="🚫 Blacklisted Tools", border_style="error")
        table.add_column("Tool Name", style="error")
        for t in blacklist:
            table.add_row(t)
        console.print(table)
        console.print()
    
    # Whitelist
    whitelist = rules.get("whitelist", [])
    if whitelist:
        table = Table(title="✅ Whitelisted Tools", border_style="success")
        table.add_column("Tool Name", style="success")
        for t in whitelist:
            table.add_row(t)
        console.print(table)
        console.print()
        
    # Tool Specific Rules
    tools = rules.get("tools", [])
    if tools:
        table = Table(title="🛡️ Tool Specific Rules", border_style="primary")
        table.add_column("Tool Pattern", style="cyan")
        table.add_column("Action", style="yellow")
        table.add_column("Description")
        table.add_column("Condition (Regex)", style="dim")
        
        for t in tools:
            name = t.get("name", "*")
            action = str(t.get("action", "ask")).upper()
            desc = t.get("description", "")
            
            sub_rules = t.get("rules", [])
            cond_str = ""
            if sub_rules:
                for sr in sub_rules:
                    f = sr.get("field")
                    r = sr.get("regex")
                    a = str(sr.get("action", action.lower())).upper()
                    cond_str += f"{f} ~ /{r}/ -> {a}\n"
            
            table.add_row(name, action, desc, cond_str.strip())
        console.print(table)
    else:
        console.print("  [dim_text]No tool-specific rules defined.[/dim_text]")

@firewall.command()
def edit() -> None:
    """Open the firewall configuration in your default editor."""
    if not FIREWALL_FILE.exists():
        FirewallManager()._create_default()
    click.edit(filename=str(FIREWALL_FILE))
    render_success(f"Firewall configuration updated: [dim_text]{FIREWALL_FILE}[/dim_text]")

@firewall.command()
def status() -> None:
    """Verify firewall configuration integrity."""
    fw = FirewallManager()
    ok, reason = fw.is_integrity_ok()
    if ok:
        render_success("Firewall integrity check: [success]PASS[/success]")
    else:
        render_error(f"Firewall integrity check: [error]FAILED[/error]", hint=reason)

@firewall.command()
@click.confirmation_option(prompt="This will overwrite your existing firewall rules. Continue?")
def reset() -> None:
    """Restore default firewall configuration."""
    fw = FirewallManager()
    fw._create_default()
    render_success("Firewall configuration reset to defaults.")
