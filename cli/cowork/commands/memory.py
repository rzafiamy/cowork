"""
cowork/commands/memory.py
──────────────────────────
CLI commands: `memory` and `vector` groups.
"""

from __future__ import annotations

import click

from ..memoria import Memoria
from ..ui import (
    console,
    print_banner,
    render_error,
    render_memory_status,
    render_memory_search_results,
    render_success,
)
from ..core import _config, get_memory_user_id, make_api_client


@click.group(invoke_without_command=True)
@click.pass_context
def memory(ctx: click.Context) -> None:
    """Manage Memoria (long-term memory)."""
    if ctx.invoked_subcommand is not None:
        return

    print_banner()
    if not _config.is_configured():
        render_error("Not configured.")
        return
    api_client = make_api_client()
    user_id = get_memory_user_id()
    mem = Memoria(user_id, "status_check", api_client, _config)
    render_memory_status(mem.get_triplet_count(), mem.get_summary(), mem.kg_limit)

    if mem.is_semantic_search_available():
        console.print(
            "  [green]🔍 Local RAG:[/green] [dim]sqlite-vec + all-MiniLM-L6-v2 (semantic search active)[/dim]"
        )
    else:
        console.print(
            "  [yellow]🔍 Local RAG:[/yellow] [dim]keyword fallback "
            "(install sentence-transformers + sqlite-vec for semantic search)[/dim]"
        )


@memory.command(name="search")
@click.argument("query")
def memory_search(query: str) -> None:
    """Perform a semantic search for facts."""
    api_client = make_api_client()
    user_id = get_memory_user_id()
    mem = Memoria(user_id, "search_check", api_client, _config)
    results = mem.search_triplets(query)
    render_memory_search_results(query, results)


@memory.command(name="add")
@click.argument("subject")
@click.argument("predicate")
@click.argument("object")
def memory_add(subject: str, predicate: str, object: str) -> None:
    """Manually add a knowledge fact."""
    api_client = make_api_client()
    user_id = get_memory_user_id()
    mem = Memoria(user_id, "add_check", api_client, _config)
    tid = mem.add_triplet(subject, predicate, object)
    render_success(f"✅ Added knowledge fact: {tid[:8]}")


@click.group(name="vector", invoke_without_command=True)
@click.pass_context
def vector(ctx: click.Context) -> None:
    """Alias for memory management."""
    ctx.invoke(memory)


@vector.command(name="search")
@click.argument("query")
@click.pass_context
def vector_search(ctx: click.Context, query: str) -> None:
    ctx.invoke(memory_search, query=query)


@vector.command(name="add")
@click.argument("subject")
@click.argument("predicate")
@click.argument("object")
@click.pass_context
def vector_add(ctx: click.Context, subject: str, predicate: str, object: str) -> None:
    ctx.invoke(memory_add, subject=subject, predicate=predicate, object=object)
