---
name: diary-supabase
description: Manage calendars and events in the Supabase calendar database (create calendars, schedule events, recurring events).
triggers:
  - calendar
  - event
  - meeting
  - appointment
  - schedule
  - diary
  - agenda
  - remind
  - recurring
  - plan
  - book
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
# Diary / Calendar (Supabase) Skill

Purpose: CRUD operations on the user's calendars and events stored in the Supabase `calendar` schema.

## Table Schemas

### `calendar.calendars`

| Column       | Type        | Constraints                                       |
|-------------|-------------|---------------------------------------------------|
| `id`        | UUID        | PRIMARY KEY, auto-generated                       |
| `user_id`   | UUID        | NOT NULL, auto-injected from env                  |
| `name`      | TEXT        | NOT NULL, unique per user                         |
| `color`     | TEXT        | NOT NULL (e.g. `#3B82F6`)                         |
| `created_at`| TIMESTAMPTZ | default NOW()                                     |
| `updated_at`| TIMESTAMPTZ | default NOW()                                     |

### `calendar.events`

| Column                       | Type           | Constraints / Notes                                                     |
|------------------------------|----------------|-------------------------------------------------------------------------|
| `id`                         | UUID           | PRIMARY KEY, auto-generated                                             |
| `calendar_id`                | UUID           | NOT NULL, FK → calendars.id                                             |
| `user_id`                    | UUID           | NOT NULL, auto-injected from env                                        |
| `title`                      | TEXT           | NOT NULL                                                                |
| `description`                | TEXT           | nullable                                                                |
| `start_time`                 | TIMESTAMPTZ    | NOT NULL                                                                |
| `end_time`                   | TIMESTAMPTZ    | NOT NULL, must be >= start_time                                         |
| `location`                   | TEXT           | nullable                                                                |
| `participants`               | JSONB          | Array: `[{"email":"a@b.com","name":"A","rsvp":"accepted"}]`             |
| `tags`                       | JSONB          | nullable                                                                |
| `priority`                   | TEXT           | default `medium`                                                        |
| `rrule`                      | TEXT           | iCalendar RRULE for recurring events (e.g. `FREQ=WEEKLY;BYDAY=MO`)     |
| `parent_event_id`            | UUID           | FK → events.id, for recurring series                                    |
| `recurrence_exception_dates` | TIMESTAMPTZ[]  | Dates excluded from recurrence                                          |
| `created_at`                 | TIMESTAMPTZ    | default NOW()                                                           |
| `updated_at`                 | TIMESTAMPTZ    | default NOW()                                                           |

**Important**: `user_id` is auto-injected from `SUPABASE_USER_ID` — do NOT ask the user for it.

## Workflow

### Create a calendar
```
supabase_insert(
  table="calendars",
  schema="calendar",
  rows='{"name": "Work", "color": "#3B82F6"}'
)
```

### List user's calendars
```
supabase_select(
  table="calendars",
  schema="calendar",
  columns="id,name,color",
  order="name.asc"
)
```

### Create an event
```
supabase_insert(
  table="events",
  schema="calendar",
  rows='{"calendar_id": "<calendar-uuid>", "title": "Team standup", "start_time": "2026-02-26T09:00:00+01:00", "end_time": "2026-02-26T09:30:00+01:00", "location": "Room A", "priority": "high"}'
)
```
- `calendar_id` is required — first list calendars to get the ID, or create one.
- `start_time` and `end_time` are required, use ISO 8601 with timezone.
- `participants` is JSONB: `[{"email": "alice@example.com", "name": "Alice", "rsvp": "pending"}]`

### Create a recurring event
```
supabase_insert(
  table="events",
  schema="calendar",
  rows='{"calendar_id": "<uuid>", "title": "Weekly standup", "start_time": "2026-02-26T09:00:00+01:00", "end_time": "2026-02-26T09:30:00+01:00", "rrule": "FREQ=WEEKLY;BYDAY=MO,WE,FR"}'
)
```

### List upcoming events
```
supabase_select(
  table="events",
  schema="calendar",
  columns="id,title,start_time,end_time,location,priority",
  filters="start_time=gte.2026-02-25T00:00:00Z",
  order="start_time.asc",
  limit=20
)
```

### Filter events by calendar
```
supabase_select(
  table="events",
  schema="calendar",
  filters="calendar_id=eq.<calendar-uuid>",
  order="start_time.asc"
)
```

### Update an event
```
supabase_update(
  table="events",
  schema="calendar",
  filters="id=eq.<event-uuid>",
  updates='{"title": "Updated title", "end_time": "2026-02-26T10:30:00+01:00", "updated_at": "now()"}'
)
```

### Delete an event
```
supabase_delete(
  table="events",
  schema="calendar",
  filters="id=eq.<event-uuid>"
)
```

## Key Rules
1. **Always pass `schema="calendar"`** — these tables are NOT in the public schema.
2. **Never ask for `user_id`** — it is auto-injected from `SUPABASE_USER_ID`.
3. When creating events, always use ISO 8601 timestamps with timezone.
4. If the user doesn't specify a calendar, list calendars first to pick the default one.
5. For recurring events, use standard iCalendar RRULE format.
6. Always order events by `start_time.asc` unless the user specifies otherwise.

## Guardrails
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
- Confirm delete operations before executing.
