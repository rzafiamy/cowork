---
name: supabase-tools
description: Query and manage data in Supabase / PostgREST databases (CRUD, schema introspection, RPC).
triggers:
  - supabase
  - database
  - table
  - query
  - sql
  - postgrest
  - crud
  - insert
  - select
  - update
  - delete
trust_tier: 4
tool_categories:
  - SUPABASE_TOOLS
permissions:
  categories:
    - SUPABASE_TOOLS
  tools:
    - supabase_list_tables
    - supabase_describe_table
    - supabase_select
    - supabase_insert
    - supabase_update
    - supabase_delete
    - supabase_rpc
---
# Supabase Tools Skill

Purpose: Query and manage data in any Supabase (or self-hosted PostgREST) database.

## Setup

Configure `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and optionally `SUPABASE_LONG_LIVED_KEY` in your `.env` file.
See `.env.example` for details.

**PostgREST schema exposure**: Ensure your PostgREST config exposes all needed schemas:
```
PGRST_DB_SCHEMAS=public,notes_app,calendar,kanban
```

## PostgREST Filter Syntax Quick Reference

| Operator | Meaning            | Example                        |
|----------|--------------------|--------------------------------|
| `eq`     | Equals             | `status=eq.active`             |
| `neq`    | Not equal           | `status=neq.deleted`           |
| `gt`     | Greater than        | `age=gt.18`                    |
| `gte`    | Greater or equal    | `age=gte.18`                   |
| `lt`     | Less than           | `price=lt.100`                 |
| `lte`    | Less or equal       | `price=lte.100`                |
| `like`   | LIKE (% wildcard)   | `name=like.*alice*`            |
| `ilike`  | Case-insensitive    | `name=ilike.*alice*`           |
| `in`     | IN list             | `id=in.(1,2,3)`               |
| `is`     | IS (null/true/false)| `deleted_at=is.null`           |

Combine filters with `&`: `age=gte.18&status=eq.active`

## Workflow

1. **Discover schema**: Use `supabase_list_tables` to see available tables, then `supabase_describe_table` for column details.
2. **Read data**: Use `supabase_select` with appropriate filters, ordering, and limits.
3. **Write data**: Use `supabase_insert` for new rows.
4. **Modify data**: Use `supabase_update` with mandatory filters to update specific rows.
5. **Remove data**: Use `supabase_delete` with mandatory filters.
6. **Call functions**: Use `supabase_rpc` for stored Postgres functions.

### Safety Rules
- `supabase_update` and `supabase_delete` **always require a filter** to prevent accidental full-table modifications.
- Validate required arguments before execution.
- If a tool returns an error, repair arguments or switch to a safer fallback.
- Synthesize concise results and stop tool usage once the user goal is met.

## Guardrails
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
- Always confirm destructive operations (update/delete) with the user when operating on production data.
