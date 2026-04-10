# Session Auth — Filter by User Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the security bug where `GET /sessions` and `GET /history/{id}` expose every user's chat history by scoping sessions to their owning user.

**Architecture:** Add a `user_id` column to the `sessions` table via an idempotent `ALTER TABLE` migration; update `HistoryStore` with filtered read methods; pass `user_id` through `run_turn_stream → save_session`; auth-gate both REST endpoints; update the React sidebar to send the token.

**Tech Stack:** Python/FastAPI, SQLite (via `HistoryStore` in `zeus_agent.py`), React 18, pytest + FastAPI TestClient.

---

## File Map

| Action | Path | What changes |
|--------|------|--------------|
| Modify | `backend/zeus_agent.py` | `_init_db` migration, `save_session` signature, new `list_sessions_for_user`, new `get_transcript_if_owner`, `run_turn_stream` call site |
| Modify | `backend/main.py` | `GET /sessions` + `GET /history/{id}` — add auth, call new methods |
| Create | `backend/tests/test_session_auth.py` | Unit + endpoint tests |
| Modify | `web/src/components/SessionSidebar.jsx` | Pass `Authorization` header on `/sessions` fetch |

---

### Task 1: Migrate `sessions` table and update `HistoryStore`

**Files:**
- Modify: `backend/zeus_agent.py:1114-1207`

- [ ] **Step 1: Add `user_id` migration to `_init_db`**

In `backend/zeus_agent.py`, find `_init_db` (line ~1114). After the `conn.executescript(...)` call, add the migration block inside the same `with self._conn() as conn:` block:

```python
def _init_db(self) -> None:
    with self._conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id      TEXT PRIMARY KEY,
                started TEXT NOT NULL,
                turns   INTEGER NOT NULL DEFAULT 0,
                preview TEXT NOT NULL DEFAULT '',
                updated TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS turns (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                turn       INTEGER NOT NULL,
                role       TEXT NOT NULL,
                text       TEXT NOT NULL,
                created    TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_turns_session ON turns (session_id);
            CREATE TABLE IF NOT EXISTS messages (
                session_id TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                updated    TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'general',
                content  TEXT NOT NULL,
                created  TEXT NOT NULL,
                updated  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memory_cat ON memory (category);
            CREATE TABLE IF NOT EXISTS clients (
                name       TEXT PRIMARY KEY,
                industry   TEXT,
                location   TEXT,
                email      TEXT,
                style_pref TEXT,
                notes      TEXT,
                created    TEXT NOT NULL,
                updated    TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projects (
                name        TEXT PRIMARY KEY,
                client_name TEXT,
                status      TEXT NOT NULL DEFAULT 'active',
                url         TEXT,
                folder      TEXT,
                budget      REAL,
                notes       TEXT,
                created     TEXT NOT NULL,
                updated     TEXT NOT NULL
            );
        """)
        # Idempotent migration: add user_id to sessions
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
        except Exception:
            pass  # column already exists
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id)"
            )
        except Exception:
            pass
```

- [ ] **Step 2: Update `save_session` to accept and store `user_id`**

Replace the existing `save_session` method (line ~1178):

```python
def save_session(self, session_id: str, started: datetime,
                 turns: int, preview: str,
                 user_id: str | None = None) -> None:
    with self._conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, started, turns, preview, updated, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                turns   = excluded.turns,
                preview = excluded.preview,
                updated = excluded.updated
            """,
            (session_id, started.isoformat(), turns,
             preview[:80], datetime.now().isoformat(), user_id),
        )
```

Note: `ON CONFLICT` deliberately does not update `user_id` — once a session has an owner it keeps it.

- [ ] **Step 3: Add `list_sessions_for_user` method**

After the existing `list_sessions` method, add:

```python
def list_sessions_for_user(self, user_id: str) -> list:
    with self._conn() as conn:
        rows = conn.execute(
            "SELECT id, started, turns, preview FROM sessions "
            "WHERE user_id = ? ORDER BY updated DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Add `get_transcript_if_owner` method**

After the existing `get_transcript` method, add:

```python
def get_transcript_if_owner(self, session_id: str, user_id: str) -> list | None:
    """Return transcript if the session belongs to user_id, else None."""
    with self._conn() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if row is None:
            return None
        rows = conn.execute(
            "SELECT turn, role, text FROM turns WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 5: Verify the module still imports cleanly**

```bash
cd backend && python -c "from zeus_agent import HistoryStore; print('ok')"
```

Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add backend/zeus_agent.py
git commit -m "feat: add user_id to sessions table and filtered HistoryStore methods"
```

---

### Task 2: Pass `user_id` to `save_session` in `run_turn_stream`

**Files:**
- Modify: `backend/zeus_agent.py` (line ~2075)

- [ ] **Step 1: Update the `save_session` call**

Find the line (around line 2075) that reads:

```python
                history.save_session(session_id, session_start, turn_count, prompt)
```

Change it to:

```python
                history.save_session(session_id, session_start, turn_count, prompt, user_id=user_id)
```

`user_id` is already a parameter of `run_turn_stream` so no other changes needed.

- [ ] **Step 2: Verify import is still clean**

```bash
cd backend && python -c "from zeus_agent import run_turn_stream; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/zeus_agent.py
git commit -m "feat: pass user_id to save_session in run_turn_stream"
```

---

### Task 3: Auth-gate the REST endpoints in `main.py`

**Files:**
- Modify: `backend/main.py` (lines ~622-636)

- [ ] **Step 1: Update `GET /sessions`**

Find:

```python
@app.get("/sessions")
async def get_sessions():
    if history is None:
        return []
    return history.list_sessions()
```

Replace with:

```python
@app.get("/sessions")
async def get_sessions(current_user: dict = Depends(auth.get_current_user)):
    if history is None:
        return []
    return history.list_sessions_for_user(current_user["id"])
```

- [ ] **Step 2: Update `GET /history/{session_id}`**

Find:

```python
@app.get("/history/{session_id}")
async def get_history(session_id: str):
    if history is None:
        raise HTTPException(status_code=503, detail="Server still initialising")
    try:
        return history.get_transcript(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

Replace with:

```python
@app.get("/history/{session_id}")
async def get_history(session_id: str, current_user: dict = Depends(auth.get_current_user)):
    if history is None:
        raise HTTPException(status_code=503, detail="Server still initialising")
    transcript = history.get_transcript_if_owner(session_id, current_user["id"])
    if transcript is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return transcript
```

- [ ] **Step 3: Verify imports clean**

```bash
cd backend && python -c "import main; print('ok')" 2>&1 | grep -E "^zeus|ok|Error"
```

Expected output includes `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "fix: auth-gate GET /sessions and GET /history/{id}, filter by user"
```

---

### Task 4: Write tests for the security fix

**Files:**
- Create: `backend/tests/test_session_auth.py`

- [ ] **Step 1: Create the test file**

```python
"""
Tests for the session auth security fix:
- GET /sessions requires auth and returns only the calling user's sessions
- GET /history/{id} requires auth and returns 404 for sessions owned by other users
- HistoryStore.list_sessions_for_user filters correctly
- HistoryStore.get_transcript_if_owner enforces ownership
"""
import os
import pathlib
import sys
import tempfile
from datetime import datetime
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


# ── HistoryStore unit tests ───────────────────────────────────────────────────

def _make_store(tmp_path):
    """Create a HistoryStore pointed at a temp directory."""
    from zeus_agent import HistoryStore
    store = object.__new__(HistoryStore)
    store.dir = pathlib.Path(tmp_path)
    store.db_path = store.dir / "zeus.db"
    store._init_db()
    return store


def test_list_sessions_for_user_filters_by_owner(tmp_path):
    store = _make_store(tmp_path)
    t = datetime(2026, 1, 1, 12, 0)

    store.save_session("sess-alice", t, 2, "Hello", user_id="user-alice")
    store.save_session("sess-bob",   t, 3, "World", user_id="user-bob")
    store.save_session("sess-anon",  t, 1, "Anon")   # no user_id

    result = store.list_sessions_for_user("user-alice")
    ids = [r["id"] for r in result]
    assert ids == ["sess-alice"], f"Expected only alice's session, got {ids}"


def test_list_sessions_for_user_empty_when_no_sessions(tmp_path):
    store = _make_store(tmp_path)
    result = store.list_sessions_for_user("user-nobody")
    assert result == []


def test_get_transcript_if_owner_returns_transcript_for_correct_user(tmp_path):
    store = _make_store(tmp_path)
    t = datetime(2026, 1, 1, 12, 0)
    store.save_session("sess-1", t, 1, "Hi", user_id="user-a")
    store.log_turn("sess-1", 1, "user", "Hi there")
    store.log_turn("sess-1", 1, "zeus", "Hello!")

    result = store.get_transcript_if_owner("sess-1", "user-a")
    assert result is not None
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "zeus"


def test_get_transcript_if_owner_returns_none_for_wrong_user(tmp_path):
    store = _make_store(tmp_path)
    t = datetime(2026, 1, 1, 12, 0)
    store.save_session("sess-1", t, 1, "Hi", user_id="user-a")
    store.log_turn("sess-1", 1, "user", "Hi there")

    result = store.get_transcript_if_owner("sess-1", "user-b")
    assert result is None


def test_get_transcript_if_owner_returns_none_for_orphan_session(tmp_path):
    """Sessions with no user_id should not be accessible by any user."""
    store = _make_store(tmp_path)
    t = datetime(2026, 1, 1, 12, 0)
    store.save_session("sess-orphan", t, 1, "Old session")  # no user_id
    store.log_turn("sess-orphan", 1, "user", "Old message")

    result = store.get_transcript_if_owner("sess-orphan", "user-a")
    assert result is None


# ── Endpoint tests ────────────────────────────────────────────────────────────

def _make_user(user_id="user-1"):
    return {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "subscription_status": "active",
        "subscription_plan": "pro",
        "password_hash": "x",
        "name": "Test",
        "is_admin": 0,
    }


def test_sessions_endpoint_requires_auth():
    import auth
    from main import app
    from fastapi.testclient import TestClient

    app.dependency_overrides.pop(auth.get_current_user, None)
    with TestClient(app) as client:
        resp = client.get("/sessions")
    assert resp.status_code == 401


def test_sessions_endpoint_returns_only_users_sessions():
    import auth
    from main import app
    from fastapi.testclient import TestClient

    mock_store = MagicMock()
    mock_store.list_sessions_for_user.return_value = [
        {"id": "sess-1", "started": "2026-01-01T12:00:00", "turns": 2, "preview": "Hi"}
    ]

    app.dependency_overrides[auth.get_current_user] = lambda: _make_user("user-1")
    import main as _main
    original_history = _main.history
    _main.history = mock_store
    try:
        with TestClient(app) as client:
            resp = client.get("/sessions", headers={"Authorization": "Bearer fake"})
    finally:
        _main.history = original_history
        app.dependency_overrides.pop(auth.get_current_user, None)

    assert resp.status_code == 200
    mock_store.list_sessions_for_user.assert_called_once_with("user-1")
    assert len(resp.json()) == 1


def test_history_endpoint_requires_auth():
    import auth
    from main import app
    from fastapi.testclient import TestClient

    app.dependency_overrides.pop(auth.get_current_user, None)
    with TestClient(app) as client:
        resp = client.get("/history/some-session-id")
    assert resp.status_code == 401


def test_history_endpoint_returns_404_for_wrong_user():
    import auth
    from main import app
    from fastapi.testclient import TestClient

    mock_store = MagicMock()
    mock_store.get_transcript_if_owner.return_value = None  # not owner

    app.dependency_overrides[auth.get_current_user] = lambda: _make_user("user-2")
    import main as _main
    original_history = _main.history
    _main.history = mock_store
    try:
        with TestClient(app) as client:
            resp = client.get(
                "/history/sess-owned-by-user-1",
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        _main.history = original_history
        app.dependency_overrides.pop(auth.get_current_user, None)

    assert resp.status_code == 404


def test_history_endpoint_returns_transcript_for_owner():
    import auth
    from main import app
    from fastapi.testclient import TestClient

    mock_store = MagicMock()
    mock_store.get_transcript_if_owner.return_value = [
        {"turn": 1, "role": "user", "text": "Hello"},
        {"turn": 1, "role": "zeus", "text": "Hi!"},
    ]

    app.dependency_overrides[auth.get_current_user] = lambda: _make_user("user-1")
    import main as _main
    original_history = _main.history
    _main.history = mock_store
    try:
        with TestClient(app) as client:
            resp = client.get(
                "/history/sess-owned-by-user-1",
                headers={"Authorization": "Bearer fake"},
            )
    finally:
        _main.history = original_history
        app.dependency_overrides.pop(auth.get_current_user, None)

    assert resp.status_code == 200
    assert len(resp.json()) == 2
```

- [ ] **Step 2: Run tests — expect failures (endpoints not yet changed)**

```bash
cd backend && python -m pytest tests/test_session_auth.py -v 2>&1 | tail -20
```

Expected: several FAILED (the endpoint tests will fail because auth isn't added yet — Tasks 1-3 must be done first). If you're running this after Tasks 1-3 are complete, all should pass.

- [ ] **Step 3: Run full test suite to confirm no regressions**

```bash
cd backend && python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_session_auth.py
git commit -m "test: session auth — ownership filtering and endpoint auth checks"
```

---

### Task 5: Fix `SessionSidebar.jsx` to send auth token

**Files:**
- Modify: `web/src/components/SessionSidebar.jsx`

- [ ] **Step 1: Add token to the `/sessions` fetch**

Replace the entire file content:

```jsx
import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export function SessionSidebar({ currentSessionId, onNewSession, onResumeSession }) {
  const [sessions, setSessions] = useState([]);
  const [tunnelUrl, setTunnelUrl] = useState(null);
  const { token } = useAuth();

  const refresh = useCallback(() => {
    if (!token) {
      setSessions([]);
      return;
    }
    fetch(`${BACKEND_URL}/sessions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : [])
      .then(setSessions)
      .catch(() => {});
    fetch(`${BACKEND_URL}/tunnel-url`)
      .then(r => r.json())
      .then(d => setTunnelUrl(d.url))
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    refresh();
  }, [currentSessionId, refresh]);

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="zeus-logo">
          <span className="zeus-icon">⚡</span>
          <span className="zeus-title">ZEUS</span>
        </div>
      </div>

      <button className="new-session-btn" onClick={onNewSession}>
        + New Session
      </button>

      <div className="session-list">
        <div className="session-list-label">RECENT</div>
        {sessions.map(s => (
          <div
            key={s.id}
            className={`session-item ${s.id === currentSessionId ? 'active' : ''}`}
            onClick={() => onResumeSession(s.id)}
            title={s.id}
          >
            <div className="session-preview">{s.preview || 'Session'}</div>
            <div className="session-meta">
              {s.turns} turn{s.turns !== 1 ? 's' : ''}
            </div>
          </div>
        ))}
      </div>

      <div className="tunnel-status">
        <span className={`status-dot ${tunnelUrl ? 'active' : 'inactive'}`}>●</span>
        {tunnelUrl ? 'Tunnel active' : 'No tunnel'}
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Verify the frontend builds**

```bash
cd web && npm run build 2>&1 | tail -5
```

Expected: `✓ built in Xs`

- [ ] **Step 3: Commit**

```bash
git add web/src/components/SessionSidebar.jsx
git commit -m "fix: send auth token in SessionSidebar /sessions fetch"
```
