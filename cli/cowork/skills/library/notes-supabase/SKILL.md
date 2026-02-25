---
name: notes-supabase
description: Create, read, update, and delete notes in the Supabase notes_app database.
triggers:
  - note
  - notes
  - memo
  - remember
  - write down
  - jot
  - summary
  - take note
trust_tier: 3
tool_categories:
  - SUPABASE_TOOLS
permissions:
  categories:
    - SUPABASE_TOOLS
  tools:
    - supabase_select
    - supabase_insert
    - supabase_update
    - supabase_delete
---
# Notes (Supabase) Skill

Purpose: CRUD operations on the user's personal notes stored in a Supabase `notes_app.notes` table.

## Table Schema

```
Schema: notes_app
Table:  notes
```

| Column       | Type          | Constraints                              |
|-------------|---------------|------------------------------------------|
| `id`        | UUID          | PRIMARY KEY, auto-generated              |
| `user_id`   | UUID          | NOT NULL, auto-injected from env         |
| `title`     | TEXT          | NOT NULL                                 |
| `content`   | TEXT          | nullable                                 |
| `summary`   | TEXT          | nullable                                 |
| `category`  | TEXT          | nullable                                 |
| `tags`      | TEXT[]        | nullable, Postgres array                 |
| `created_at`| TIMESTAMPTZ   | default NOW()                            |
| `updated_at`| TIMESTAMPTZ   | default NOW()                            |

**Important**: `user_id` is auto-injected by the tool from `SUPABASE_USER_ID` env var — do NOT ask the user for it.

## Workflow

### Create a note
```
supabase_insert(
  table="notes",
  schema="notes_app",
  rows='{"title": "...", "content": "...", "category": "...", "tags": ["tag1", "tag2"]}'
)
```
- `title` is required.
- `content`, `summary`, `category`, `tags` are optional.
- `user_id` is auto-injected — never include it manually.
- `id`, `created_at`, `updated_at` are auto-generated.

### List / search notes
```
supabase_select(
  table="notes",
  schema="notes_app",
  columns="id,title,category,tags,created_at",
  order="created_at.desc",
  limit=20
)
```
- To filter by category: `filters="category=eq.work"`
- To search by title: `filters="title=ilike.*keyword*"`
- To filter by tag: `filters="tags=cs.{tag1}"`

### Read a specific note
```
supabase_select(
  table="notes",
  schema="notes_app",
  filters="id=eq.<uuid>"
)
```

### Update a note
```
supabase_update(
  table="notes",
  schema="notes_app",
  filters="id=eq.<uuid>",
  updates='{"title": "new title", "content": "updated content", "updated_at": "now()"}'
)
```

### Delete a note
```
supabase_delete(
  table="notes",
  schema="notes_app",
  filters="id=eq.<uuid>"
)
```

## Key Rules
1. **Always pass `schema="notes_app"`** — this table is NOT in the public schema.
2. **Never ask for `user_id`** — it is auto-injected from `SUPABASE_USER_ID`.
3. When creating a note from user conversation, extract a meaningful `title` and put the full content in `content`.
4. If the user asks to "remember" or "note" something, generate an appropriate `summary` field.
5. Use `tags` as a Postgres text array: `["tag1", "tag2"]`.
6. Always order by `created_at.desc` when listing unless the user specifies otherwise.

## Guardrails
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
- Confirm delete operations before executing.
