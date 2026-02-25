---
name: kanban-supabase
description: Manage Kanban boards, columns, and tasks in the Supabase kanban database.
triggers:
  - kanban
  - board
  - task
  - todo
  - column
  - backlog
  - sprint
  - project
  - assign
  - priority
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
# Kanban (Supabase) Skill

Purpose: CRUD operations on the user's Kanban boards, columns, and tasks stored in the Supabase `kanban` schema.

## Table Schemas

### `kanban.boards`

| Column        | Type        | Constraints                         |
|--------------|-------------|-------------------------------------|
| `id`         | UUID        | PRIMARY KEY, auto-generated         |
| `user_id`    | UUID        | NOT NULL, auto-injected from env    |
| `name`       | TEXT        | NOT NULL                            |
| `description`| TEXT        | nullable                            |
| `color`      | TEXT        | default `#000000`                   |
| `created_at` | TIMESTAMPTZ | default NOW()                       |
| `last_used_at`| TIMESTAMPTZ| default NOW()                       |

### `kanban.columns`

| Column      | Type        | Constraints                    |
|------------|-------------|--------------------------------|
| `id`       | UUID        | PRIMARY KEY, auto-generated    |
| `board_id` | UUID        | FK → boards.id                 |
| `name`     | TEXT        | NOT NULL                       |
| `position` | INT         | NOT NULL (ordering)            |
| `created_at`| TIMESTAMPTZ| default NOW()                  |

### `kanban.tasks`

| Column       | Type        | Constraints                                       |
|-------------|-------------|---------------------------------------------------|
| `id`        | UUID        | PRIMARY KEY, auto-generated                       |
| `column_id` | UUID        | FK → columns.id                                   |
| `title`     | TEXT        | NOT NULL                                          |
| `description`| TEXT       | nullable                                          |
| `due_date`  | DATE        | nullable                                          |
| `priority`  | TEXT        | CHECK: `Low`, `Medium`, `High` (default `Medium`) |
| `labels`    | TEXT[]      | nullable, Postgres array                          |
| `position`  | INT         | NOT NULL (ordering within column)                 |
| `created_at`| TIMESTAMPTZ | default NOW()                                     |

**Important**: `user_id` on boards is auto-injected from `SUPABASE_USER_ID` — do NOT ask the user for it.

## Workflow

### Create a board
```
supabase_insert(
  table="boards",
  schema="kanban",
  rows='{"name": "My Project", "description": "Sprint tasks", "color": "#10B981"}'
)
```

### List boards
```
supabase_select(
  table="boards",
  schema="kanban",
  columns="id,name,description,color,last_used_at",
  order="last_used_at.desc"
)
```

### Create default columns for a board
```
supabase_insert(
  table="columns",
  schema="kanban",
  rows='[{"board_id": "<board-uuid>", "name": "To Do", "position": 0}, {"board_id": "<board-uuid>", "name": "In Progress", "position": 1}, {"board_id": "<board-uuid>", "name": "Done", "position": 2}]'
)
```

### List columns of a board
```
supabase_select(
  table="columns",
  schema="kanban",
  filters="board_id=eq.<board-uuid>",
  order="position.asc"
)
```

### Add a task to a column
```
supabase_insert(
  table="tasks",
  schema="kanban",
  rows='{"column_id": "<column-uuid>", "title": "Fix login bug", "priority": "High", "labels": ["bug", "frontend"], "position": 0}'
)
```
- `column_id` is required — first list columns to get the right ID.
- `position` is required — use 0 for top, or query existing tasks to find the next position.

### List tasks in a column
```
supabase_select(
  table="tasks",
  schema="kanban",
  filters="column_id=eq.<column-uuid>",
  order="position.asc"
)
```

### List all tasks on a board (join via column)
To see all tasks on a board, first get the column IDs from `kanban.columns`, then query tasks for each column. Alternatively, filter by multiple column IDs:
```
supabase_select(
  table="tasks",
  schema="kanban",
  filters="column_id=in.(<col1-uuid>,<col2-uuid>,<col3-uuid>)",
  order="position.asc"
)
```

### Move a task (change column or position)
```
supabase_update(
  table="tasks",
  schema="kanban",
  filters="id=eq.<task-uuid>",
  updates='{"column_id": "<new-column-uuid>", "position": 0}'
)
```

### Update task priority / details
```
supabase_update(
  table="tasks",
  schema="kanban",
  filters="id=eq.<task-uuid>",
  updates='{"priority": "High", "due_date": "2026-03-01", "labels": ["urgent", "backend"]}'
)
```

### Delete a task
```
supabase_delete(
  table="tasks",
  schema="kanban",
  filters="id=eq.<task-uuid>"
)
```

### Delete a board (cascades to columns and tasks)
```
supabase_delete(
  table="boards",
  schema="kanban",
  filters="id=eq.<board-uuid>"
)
```

## Key Rules
1. **Always pass `schema="kanban"`** — these tables are NOT in the public schema.
2. **Never ask for `user_id`** — it is auto-injected from `SUPABASE_USER_ID` for boards.
3. When creating a new board, also create default columns (`To Do`, `In Progress`, `Done`) unless the user specifies different columns.
4. When adding tasks, determine the correct `position` by counting existing tasks in the target column.
5. `priority` must be exactly `Low`, `Medium`, or `High` (case-sensitive).
6. `labels` is a Postgres text array: `["label1", "label2"]`.

## Guardrails
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
- Confirm delete operations on boards (cascade deletes all columns and tasks).
