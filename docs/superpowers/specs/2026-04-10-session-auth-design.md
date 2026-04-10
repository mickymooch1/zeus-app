---
name: Session Auth — filter sessions by user
description: Fix security bug where GET /sessions and GET /history/{id} expose all users' chat history
type: project
---

# Session Auth Design

## Goal

Scope chat sessions to their owning user so no user can see another user's sessions or transcripts. Fix the two unauthenticated endpoints that currently return all data.

## Bugs Being Fixed

- `GET /sessions` — no auth, returns every session in the DB
- `GET /history/{session_id}` — no auth, any transcript readable by guessing an ID
- `sessions` table has no `user_id` column, so filtering is impossible without a schema change

## Architecture

### Schema change — `sessions` table

Add a `user_id TEXT` column via `ALTER TABLE ... ADD COLUMN` migration (idempotent, wrapped in try/except). Existing rows get `user_id = NULL` and become invisible to regular users.

```sql
ALTER TABLE sessions ADD COLUMN user_id TEXT;
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id);
```

### HistoryStore changes (`backend/zeus_agent.py`)

**`_init_db()`** — run the migration after the CREATE TABLE block.

**`save_session(session_id, started, turns, preview, user_id=None)`** — add `user_id` parameter, write it to the row.

**`list_sessions_for_user(user_id)`** — new method, `SELECT ... WHERE user_id = ?`.

**`get_transcript_if_owner(session_id, user_id)`** — new method, fetches transcript only if the session's `user_id` matches; returns `None` if not found or not owned.

### `run_turn_stream` — pass `user_id` to `save_session`

`user_id` is already a parameter of `run_turn_stream`. The `history.save_session(...)` call on line ~2075 just needs `user_id=user_id` added.

### Endpoint changes (`backend/main.py`)

**`GET /sessions`**
- Add `Depends(auth.get_current_user)` 
- Call `history.list_sessions_for_user(current_user["id"])` instead of `history.list_sessions()`

**`GET /history/{session_id}`**
- Add `Depends(auth.get_current_user)`
- Call `history.get_transcript_if_owner(session_id, current_user["id"])`
- Return 404 if `None` (not found or not owned — don't leak existence)

## Data Flow

```
WebSocket chat completes
  → run_turn_stream calls history.save_session(session_id, ..., user_id=user_id)
  → sessions row written with user_id

GET /sessions (with JWT)
  → auth.get_current_user → user dict
  → history.list_sessions_for_user(user["id"])
  → returns only that user's sessions

GET /history/{session_id} (with JWT)
  → auth.get_current_user → user dict
  → history.get_transcript_if_owner(session_id, user["id"])
  → 404 if not owned, transcript if owned
```

## Migration safety

`ALTER TABLE sessions ADD COLUMN user_id TEXT` is wrapped in try/except so it's safe to run repeatedly. Existing NULL rows remain in the DB but are never returned by the new filtered queries.

## Out of Scope

- Backfilling `user_id` on existing sessions (they're orphaned, not deleted)
- Admin endpoint to view all sessions
- The WebSocket `/chat` endpoint itself (already has auth)
