"""
🗄️ Supabase Tools
Implementations for interacting with a Supabase (or self-hosted) PostgreSQL
database via the PostgREST API.

Required env vars:
  SUPABASE_URL             – Base URL, e.g. http://your-host:8000
  SUPABASE_ANON_KEY        – anon / service_role key from your Supabase project

Optional env vars:
  SUPABASE_LONG_LIVED_KEY  – Long-lived API key (JWT) you generated for
                             authenticated requests (overrides anon key in
                             the Authorization header)
  SUPABASE_USER_ID         – Default user UUID used when inserting rows into
                             tables with a user_id column
"""

import json
import urllib.parse
import urllib.request
from typing import Any, Optional

from .utils import _env, _missing_key, json_to_markdown


# ─── Credentials ──────────────────────────────────────────────────────────────

def _get_supabase_creds() -> tuple[dict | None, str | None]:
    """Return (creds_dict, error_string)."""
    url = _env("SUPABASE_URL")
    anon_key = _env("SUPABASE_ANON_KEY")

    if not url:
        return None, _missing_key("supabase", "SUPABASE_URL")
    if not anon_key:
        return None, _missing_key("supabase", "SUPABASE_ANON_KEY")

    return {
        "url": url.rstrip("/"),
        "anon_key": anon_key,
        "long_lived_key": _env("SUPABASE_LONG_LIVED_KEY"),   # may be None
        "user_id": _env("SUPABASE_USER_ID"),                 # may be None
    }, None


def _headers(creds: dict, *, prefer: str | None = None, schema: str | None = None, write: bool = False) -> dict[str, str]:
    """Build common PostgREST headers.

    Args:
        prefer: PostgREST Prefer header value.
        schema: If set, adds Accept-Profile / Content-Profile for non-public schemas.
        write:  If True, sets Content-Profile (for POST/PATCH/DELETE).
                If False, sets Accept-Profile (for GET).
    """
    token = creds["long_lived_key"] or creds["anon_key"]
    h: dict[str, str] = {
        "apikey": creds["anon_key"],
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    if schema:
        if write:
            h["Content-Profile"] = schema
        else:
            h["Accept-Profile"] = schema
        # Both headers are often needed together for mixed read/write
        h["Accept-Profile"] = schema
        h["Content-Profile"] = schema
    return h


def _rest_url(creds: dict, path: str) -> str:
    """Build a PostgREST REST URL from the Supabase base URL."""
    base = creds["url"]
    return f"{base}/rest/v1/{path.lstrip('/')}"


# ─── Low-level HTTP helpers ───────────────────────────────────────────────────

def _do_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None = None,
    timeout: int = 20,
) -> tuple[int, Any]:
    """Execute an HTTP request and return (status_code, parsed_json_or_text)."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore") if e.fp else str(e)
        status = e.code
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = raw
    return status, data


# ─── Tool implementations ────────────────────────────────────────────────────

def supabase_list_tables() -> str:
    """
    List all user-visible tables & views in the public schema.
    Uses the PostgREST OpenAPI endpoint (/) to introspect the schema.
    """
    creds, err = _get_supabase_creds()
    if err:
        return err

    # PostgREST exposes an OpenAPI spec at its root
    openapi_url = f"{creds['url']}/rest/v1/"
    headers = _headers(creds)
    # Accept OpenAPI JSON
    headers["Accept"] = "application/openapi+json"

    status, data = _do_request("GET", openapi_url, headers)

    if status >= 400:
        # Fallback: try the root without special accept
        headers["Accept"] = "application/json"
        status, data = _do_request("GET", openapi_url, headers)

    if status >= 400:
        return f"❌ Failed to list tables (HTTP {status}): {data}"

    if isinstance(data, dict):
        definitions = data.get("definitions") or data.get("components", {}).get("schemas", {})
        if definitions:
            lines = ["🗄️ **Supabase Tables / Views** (public schema)\n"]
            for name, schema in sorted(definitions.items()):
                desc = schema.get("description", "")
                required = schema.get("required", [])
                props = schema.get("properties", {})
                cols = ", ".join(f"`{c}`" for c in list(props.keys())[:8])
                if len(props) > 8:
                    cols += f", … (+{len(props) - 8})"
                lines.append(f"- **{name}** — {len(props)} column(s): {cols}")
                if desc:
                    lines.append(f"   {desc}")
            return "\n".join(lines)

    # If we got an array or unexpected shape, just dump it
    return f"🗄️ Supabase schema response:\n{json.dumps(data, indent=2)[:3000]}"


def supabase_describe_table(table: str) -> str:
    """
    Describe columns of a specific table by inspecting the OpenAPI spec.
    """
    creds, err = _get_supabase_creds()
    if err:
        return err

    openapi_url = f"{creds['url']}/rest/v1/"
    headers = _headers(creds)
    headers["Accept"] = "application/openapi+json"

    status, data = _do_request("GET", openapi_url, headers)
    if status >= 400:
        headers["Accept"] = "application/json"
        status, data = _do_request("GET", openapi_url, headers)

    if status >= 400:
        return f"❌ Could not fetch schema (HTTP {status}): {data}"

    definitions = {}
    if isinstance(data, dict):
        definitions = data.get("definitions") or data.get("components", {}).get("schemas", {})

    table_schema = definitions.get(table)
    if not table_schema:
        available = ", ".join(sorted(definitions.keys())[:30])
        return f"❌ Table `{table}` not found. Available: {available}"

    lines = [f"📋 **Table: `{table}`**\n"]
    desc = table_schema.get("description", "")
    if desc:
        lines.append(f"_{desc}_\n")

    required = set(table_schema.get("required", []))
    props = table_schema.get("properties", {})
    for col_name, col_spec in props.items():
        col_type = col_spec.get("type", col_spec.get("format", "unknown"))
        fmt = col_spec.get("format", "")
        default = col_spec.get("default", "")
        nullable = "nullable" if col_type == "string" and col_spec.get("nullable") else ""
        pk = col_spec.get("description", "")
        parts = [f"  - **`{col_name}`**: `{col_type}`"]
        if fmt:
            parts.append(f"(format: {fmt})")
        if col_name in required:
            parts.append("**required**")
        if default:
            parts.append(f"default=`{default}`")
        if pk:
            parts.append(f" — {pk}")
        lines.append(" ".join(parts))

    return "\n".join(lines)


def supabase_select(
    table: str,
    columns: str = "*",
    filters: str = "",
    order: str = "",
    limit: int = 50,
    schema: str = "",
) -> str:
    """
    SELECT rows from a Supabase table via PostgREST.

    Args:
        table:    Table name (required).
        columns:  Comma-separated column names or '*' for all.
        filters:  PostgREST filter string, e.g. "age=gte.18&status=eq.active".
        order:    PostgREST order, e.g. "created_at.desc".
        limit:    Max rows to return (default 50, max 1000).
        schema:   Database schema (e.g. 'notes_app'). Empty = public.
    """
    creds, err = _get_supabase_creds()
    if err:
        return err

    limit = max(1, min(int(limit), 1000))
    params: dict[str, str] = {"select": columns, "limit": str(limit)}
    if order:
        params["order"] = order

    qs = urllib.parse.urlencode(params)
    # Filters are appended raw (PostgREST syntax)
    if filters:
        qs += "&" + filters

    url = _rest_url(creds, table) + "?" + qs
    headers = _headers(creds, schema=schema or None)

    status, data = _do_request("GET", url, headers)
    if status >= 400:
        return f"❌ SELECT failed (HTTP {status}): {json.dumps(data) if isinstance(data, (dict, list)) else data}"

    if isinstance(data, list):
        if not data:
            return f"ℹ️ No rows found in `{table}` matching the given filters."
        lines = [f"📊 **{len(data)} row(s)** from `{table}`\n"]
        lines.append(json_to_markdown(data))
        return "\n".join(lines)

    return f"📊 Result:\n{json.dumps(data, indent=2)[:3000]}"


def supabase_insert(table: str, rows: str, schema: str = "") -> str:
    """
    INSERT one or multiple rows into a Supabase table.

    Args:
        table:   Table name (required).
        rows:    JSON string — a single object or an array of objects.
        schema:  Database schema (e.g. 'notes_app'). Empty = public.
    """
    creds, err = _get_supabase_creds()
    if err:
        return err

    try:
        parsed = json.loads(rows) if isinstance(rows, str) else rows
    except json.JSONDecodeError as exc:
        return f"❌ Invalid JSON for rows: {exc}"

    # Auto-inject user_id if configured and not provided
    user_id = creds.get("user_id")
    if user_id:
        if isinstance(parsed, dict) and "user_id" not in parsed:
            parsed["user_id"] = user_id
        elif isinstance(parsed, list):
            for row in parsed:
                if isinstance(row, dict) and "user_id" not in row:
                    row["user_id"] = user_id

    url = _rest_url(creds, table)
    headers = _headers(creds, prefer="return=representation", schema=schema or None, write=True)
    body = json.dumps(parsed).encode("utf-8")

    status, data = _do_request("POST", url, headers, body)
    if status >= 400:
        return f"❌ INSERT failed (HTTP {status}): {json.dumps(data) if isinstance(data, (dict, list)) else data}"

    count = len(data) if isinstance(data, list) else 1
    return f"✅ Inserted {count} row(s) into `{table}`.\n{json_to_markdown(data)}"


def supabase_update(table: str, filters: str, updates: str, schema: str = "") -> str:
    """
    UPDATE rows in a Supabase table matching the given PostgREST filters.

    Args:
        table:    Table name (required).
        filters:  PostgREST filter string, e.g. "id=eq.42".
                  At least one filter is REQUIRED to prevent full-table updates.
        updates:  JSON object with the columns to update, e.g. '{"status":"done"}'.
        schema:   Database schema (e.g. 'notes_app'). Empty = public.
    """
    creds, err = _get_supabase_creds()
    if err:
        return err

    if not filters or not filters.strip():
        return "❌ Safety guard: `filters` cannot be empty for UPDATE. Provide at least one filter (e.g. id=eq.42)."

    try:
        parsed = json.loads(updates) if isinstance(updates, str) else updates
    except json.JSONDecodeError as exc:
        return f"❌ Invalid JSON for updates: {exc}"

    url = _rest_url(creds, table) + "?" + filters
    headers = _headers(creds, prefer="return=representation", schema=schema or None, write=True)
    body = json.dumps(parsed).encode("utf-8")

    status, data = _do_request("PATCH", url, headers, body)
    if status >= 400:
        return f"❌ UPDATE failed (HTTP {status}): {json.dumps(data) if isinstance(data, (dict, list)) else data}"

    count = len(data) if isinstance(data, list) else 1
    return f"✅ Updated {count} row(s) in `{table}`.\n{json_to_markdown(data)}"


def supabase_delete(table: str, filters: str, schema: str = "") -> str:
    """
    DELETE rows from a Supabase table matching the given PostgREST filters.

    Args:
        table:    Table name (required).
        filters:  PostgREST filter string, e.g. "id=eq.42".
                  At least one filter is REQUIRED to prevent full-table deletes.
        schema:   Database schema (e.g. 'notes_app'). Empty = public.
    """
    creds, err = _get_supabase_creds()
    if err:
        return err

    if not filters or not filters.strip():
        return "❌ Safety guard: `filters` cannot be empty for DELETE. Provide at least one filter (e.g. id=eq.42)."

    url = _rest_url(creds, table) + "?" + filters
    headers = _headers(creds, prefer="return=representation", schema=schema or None, write=True)

    status, data = _do_request("DELETE", url, headers)
    if status >= 400:
        return f"❌ DELETE failed (HTTP {status}): {json.dumps(data) if isinstance(data, (dict, list)) else data}"

    count = len(data) if isinstance(data, list) else 1
    return f"✅ Deleted {count} row(s) from `{table}`.\n{json_to_markdown(data)}"


def supabase_rpc(function_name: str, params: str = "{}") -> str:
    """
    Call a Supabase/PostgREST RPC (stored function).

    Args:
        function_name:  Name of the Postgres function.
        params:         JSON object with function arguments.
    """
    creds, err = _get_supabase_creds()
    if err:
        return err

    try:
        parsed = json.loads(params) if isinstance(params, str) else params
    except json.JSONDecodeError as exc:
        return f"❌ Invalid JSON for params: {exc}"

    url = _rest_url(creds, f"rpc/{function_name}")
    headers = _headers(creds)
    body = json.dumps(parsed).encode("utf-8")

    status, data = _do_request("POST", url, headers, body)
    if status >= 400:
        return f"❌ RPC `{function_name}` failed (HTTP {status}): {json.dumps(data) if isinstance(data, (dict, list)) else data}"

    return f"✅ RPC `{function_name}` result:\n{json_to_markdown(data)}"


# ─── Tool schemas ─────────────────────────────────────────────────────────────

TOOLS = [
    {
        "category": "SUPABASE_TOOLS",
        "type": "function",
        "function": {
            "name": "supabase_list_tables",
            "description": "List all tables and views in the Supabase public schema with their columns.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "category": "SUPABASE_TOOLS",
        "type": "function",
        "function": {
            "name": "supabase_describe_table",
            "description": "Show column names, types, and constraints for a specific Supabase table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Name of the table to describe"},
                },
                "required": ["table"],
            },
        },
    },
    {
        "category": "SUPABASE_TOOLS",
        "type": "function",
        "function": {
            "name": "supabase_select",
            "description": (
                "SELECT rows from a Supabase table using PostgREST syntax. "
                "Supports column selection, filters (e.g. 'age=gte.18&status=eq.active'), "
                "ordering, and limit."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "columns": {
                        "type": "string",
                        "description": "Comma-separated columns or '*' for all (default '*')",
                    },
                    "filters": {
                        "type": "string",
                        "description": (
                            "PostgREST filter string, e.g. 'age=gte.18&status=eq.active'. "
                            "Operators: eq, neq, gt, gte, lt, lte, like, ilike, in, is"
                        ),
                    },
                    "order": {
                        "type": "string",
                        "description": "PostgREST order, e.g. 'created_at.desc'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows (default 50, max 1000)",
                    },
                    "schema": {
                        "type": "string",
                        "description": "Database schema (e.g. 'notes_app'). Omit for public schema.",
                    },
                },
                "required": ["table"],
            },
        },
    },
    {
        "category": "SUPABASE_TOOLS",
        "type": "function",
        "function": {
            "name": "supabase_insert",
            "description": (
                "INSERT one or more rows into a Supabase table. "
                "Provide rows as a JSON string (single object or array of objects)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "rows": {
                        "type": "string",
                        "description": 'JSON object or array, e.g. \'{"name":"Alice","age":30}\' or \'[{"name":"Bob"},{"name":"Eve"}]\'',
                    },
                    "schema": {
                        "type": "string",
                        "description": "Database schema (e.g. 'notes_app'). Omit for public schema.",
                    },
                },
                "required": ["table", "rows"],
            },
        },
    },
    {
        "category": "SUPABASE_TOOLS",
        "type": "function",
        "function": {
            "name": "supabase_update",
            "description": (
                "UPDATE rows in a Supabase table matching the given filters. "
                "At least one filter is required for safety."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "filters": {
                        "type": "string",
                        "description": "PostgREST filter, e.g. 'id=eq.42'. REQUIRED for safety.",
                    },
                    "updates": {
                        "type": "string",
                        "description": 'JSON object with columns to update, e.g. \'{"status":"done"}\'',
                    },
                    "schema": {
                        "type": "string",
                        "description": "Database schema (e.g. 'notes_app'). Omit for public schema.",
                    },
                },
                "required": ["table", "filters", "updates"],
            },
        },
    },
    {
        "category": "SUPABASE_TOOLS",
        "type": "function",
        "function": {
            "name": "supabase_delete",
            "description": (
                "DELETE rows from a Supabase table matching the given filters. "
                "At least one filter is required for safety."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Table name"},
                    "filters": {
                        "type": "string",
                        "description": "PostgREST filter, e.g. 'id=eq.42'. REQUIRED for safety.",
                    },
                    "schema": {
                        "type": "string",
                        "description": "Database schema (e.g. 'notes_app'). Omit for public schema.",
                    },
                },
                "required": ["table", "filters"],
            },
        },
    },
    {
        "category": "SUPABASE_TOOLS",
        "type": "function",
        "function": {
            "name": "supabase_rpc",
            "description": (
                "Call a Supabase/PostgREST RPC (stored Postgres function). "
                "Provide function name and JSON parameters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "function_name": {"type": "string", "description": "Name of the Postgres function to call"},
                    "params": {
                        "type": "string",
                        "description": 'JSON object with function arguments, e.g. \'{"user_id": 1}\'',
                    },
                },
                "required": ["function_name"],
            },
        },
    },
]
