# Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a protected `/admin` page where `is_admin=1` users can view all users and change any user's plan or subscription status via inline dropdowns.

**Architecture:** Two new FastAPI endpoints (`GET /admin/users`, `PATCH /admin/users/{user_id}`) gated by `is_admin` check; a new `AdminPage.jsx` that renders a live-updating table with inline `<select>` controls; the `/admin` route added to `App.jsx` and a conditional nav link added to `Navbar.jsx`.

**Tech Stack:** FastAPI, SQLite (via existing `db.py`), React 18, React Router v6, plain CSS following existing `index.css` patterns.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/db.py` | Add `get_all_users()` |
| Modify | `backend/main.py` | Add `GET /admin/users` + `PATCH /admin/users/{user_id}` + `AdminUserPatchRequest` model |
| Create | `web/src/pages/AdminPage.jsx` | Admin user table with inline dropdowns |
| Modify | `web/src/App.jsx` | Add `/admin` route |
| Modify | `web/src/components/Navbar.jsx` | Add admin nav link |
| Modify | `web/src/index.css` | Add admin page styles |

---

### Task 1: Add `get_all_users()` to `db.py`

**Files:**
- Modify: `backend/db.py` (append after `delete_task`)

- [ ] **Step 1: Add the function**

Open `backend/db.py`. After the `fail_stale_tasks` function at the bottom, add:

```python
def get_all_users(db_path: pathlib.Path) -> list:
    """Return all users ordered by creation date descending."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 2: Verify the function is importable**

Run from the `backend/` directory:

```bash
python -c "import db; print(db.get_all_users(db.get_db_path()))"
```

Expected: prints a list of user dicts (may be empty `[]` in a fresh DB — that is fine).

- [ ] **Step 3: Commit**

```bash
git add backend/db.py
git commit -m "feat: add get_all_users() to db"
```

---

### Task 2: Add admin endpoints to `main.py`

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add the Pydantic request model**

In `backend/main.py`, in the "Pydantic request models" section (around line 256), add after `SetEnterpriseRequest`:

```python
class AdminUserPatchRequest(BaseModel):
    field: str   # "subscription_plan" or "subscription_status"
    value: str
```

- [ ] **Step 2: Add `GET /admin/users` endpoint**

In `backend/main.py`, in the "Admin endpoints" section (around line 562, after the existing `admin_set_enterprise` endpoint), add:

```python
@app.get("/admin/users")
async def admin_list_users(current_user: dict = Depends(auth.get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    db_path = db.get_db_path()
    users = db.get_all_users(db_path)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    for u in users:
        u.pop("password_hash", None)
        u["messages_this_month"] = db.get_monthly_usage(db_path, u["id"], month)
    return users
```

- [ ] **Step 3: Add `PATCH /admin/users/{user_id}` endpoint**

Immediately after the `admin_list_users` endpoint, add:

```python
_ALLOWED_ADMIN_FIELDS = {
    "subscription_plan": {"free", "pro", "agency", "enterprise"},
    "subscription_status": {"free", "active", "cancelled"},
}

@app.patch("/admin/users/{user_id}")
async def admin_patch_user(
    user_id: str,
    body: AdminUserPatchRequest,
    current_user: dict = Depends(auth.get_current_user),
):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    allowed_values = _ALLOWED_ADMIN_FIELDS.get(body.field)
    if allowed_values is None:
        raise HTTPException(status_code=400, detail=f"Field '{body.field}' is not editable")
    if body.value not in allowed_values:
        raise HTTPException(
            status_code=400,
            detail=f"Value '{body.value}' not allowed for '{body.field}'. Allowed: {sorted(allowed_values)}",
        )
    db_path = db.get_db_path()
    target = db.get_user_by_id(db_path, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    db.update_user(db_path, user_id, **{body.field: body.value})
    log.info("admin_patch_user: set %s.%s = %s (by admin %s)", user_id, body.field, body.value, current_user["id"])
    return {"ok": True}
```

- [ ] **Step 4: Start the backend and smoke-test**

```bash
cd backend && uvicorn main:app --reload --port 8000
```

In a second terminal — replace `<TOKEN>` with a JWT from `/auth/login` for an admin user:

```bash
curl -s -H "Authorization: Bearer <TOKEN>" http://localhost:8000/admin/users | python -m json.tool
```

Expected: JSON array of user objects each with `messages_this_month` field and no `password_hash`.

Try a non-admin token — expected: `{"detail":"Admin access required"}` with status 403.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: add GET /admin/users and PATCH /admin/users/{id} endpoints"
```

---

### Task 3: Create `AdminPage.jsx`

**Files:**
- Create: `web/src/pages/AdminPage.jsx`

- [ ] **Step 1: Create the file**

Create `web/src/pages/AdminPage.jsx` with the following content:

```jsx
import { useEffect, useState, useCallback } from 'react';
import { Navbar } from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const PLAN_OPTIONS = ['free', 'pro', 'agency', 'enterprise'];
const STATUS_OPTIONS = ['free', 'active', 'cancelled'];

function AdminCell({ userId, field, value, token, onSaved }) {
  const [current, setCurrent] = useState(value);
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(null); // 'ok' | 'err'

  const options = field === 'subscription_plan' ? PLAN_OPTIONS : STATUS_OPTIONS;

  const handleChange = useCallback(async (e) => {
    const newVal = e.target.value;
    const prev = current;
    setCurrent(newVal);
    setSaving(true);
    setFlash(null);
    try {
      const res = await fetch(`${BACKEND_URL}/admin/users/${userId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ field, value: newVal }),
      });
      if (!res.ok) {
        setCurrent(prev);
        setFlash('err');
      } else {
        setFlash('ok');
        onSaved(userId, field, newVal);
      }
    } catch {
      setCurrent(prev);
      setFlash('err');
    } finally {
      setSaving(false);
      setTimeout(() => setFlash(null), 2000);
    }
  }, [current, field, token, userId, onSaved]);

  return (
    <td className={`admin-cell${saving ? ' admin-cell--saving' : ''}${flash === 'ok' ? ' admin-cell--saved' : ''}${flash === 'err' ? ' admin-cell--error' : ''}`}>
      <select
        className="admin-select"
        value={current}
        onChange={handleChange}
        disabled={saving}
      >
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
      {flash === 'ok' && <span className="admin-flash admin-flash--ok">✓</span>}
      {flash === 'err' && <span className="admin-flash admin-flash--err">✗</span>}
    </td>
  );
}

export default function AdminPage() {
  const { user, token } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) return;
    fetch(`${BACKEND_URL}/admin/users`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (res.status === 403) { setError('forbidden'); return; }
        if (!res.ok) throw new Error('Failed to load users');
        setUsers(await res.json());
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  const handleSaved = useCallback((userId, field, newVal) => {
    setUsers((prev) =>
      prev.map((u) => (u.id === userId ? { ...u, [field]: newVal } : u))
    );
  }, []);

  if (!user?.is_admin) {
    return (
      <div className="admin-page">
        <Navbar />
        <div className="page admin-page-inner">
          <p className="admin-denied">Access denied.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <Navbar />
      <div className="page admin-page-inner">
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-1" />
          <div className="orb orb-2" />
        </div>

        <div className="section-label" style={{ textAlign: 'center' }}>Internal</div>
        <h1 className="section-title" style={{ textAlign: 'center', marginBottom: '2rem' }}>
          Admin Dashboard
        </h1>

        {error === 'forbidden' && (
          <p className="admin-denied">403 — Admin access required.</p>
        )}
        {error && error !== 'forbidden' && (
          <div className="form-error form-error--banner">{error}</div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem' }}>
            <span className="spinner" />
          </div>
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Plan</th>
                  <th>Status</th>
                  <th>Msgs (month)</th>
                  <th>Created</th>
                  <th>Admin</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="admin-email">{u.email}</td>
                    <td>{u.name || '—'}</td>
                    <AdminCell
                      userId={u.id}
                      field="subscription_plan"
                      value={u.subscription_plan || 'free'}
                      token={token}
                      onSaved={handleSaved}
                    />
                    <AdminCell
                      userId={u.id}
                      field="subscription_status"
                      value={u.subscription_status || 'free'}
                      token={token}
                      onSaved={handleSaved}
                    />
                    <td style={{ textAlign: 'center' }}>{u.messages_this_month ?? 0}</td>
                    <td className="admin-date">{new Date(u.created_at).toLocaleDateString()}</td>
                    <td style={{ textAlign: 'center' }}>{u.is_admin ? '✓' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="admin-count">{users.length} user{users.length !== 1 ? 's' : ''}</p>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/pages/AdminPage.jsx
git commit -m "feat: AdminPage with inline plan/status dropdowns"
```

---

### Task 4: Wire up route and navbar link

**Files:**
- Modify: `web/src/App.jsx`
- Modify: `web/src/components/Navbar.jsx`

- [ ] **Step 1: Add import and route to `App.jsx`**

In `web/src/App.jsx`:

Add the import after the `TasksPage` import line (line 11):
```jsx
import AdminPage from './pages/AdminPage';
```

Add the route after the `/tasks` route block (after line 51):
```jsx
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminPage />
              </ProtectedRoute>
            }
          />
```

The full updated `App.jsx` should look like:

```jsx
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import CookieBanner from './components/CookieBanner';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import PricingPage from './pages/PricingPage';
import DashboardPage from './pages/DashboardPage';
import BillingPage from './pages/BillingPage';
import TasksPage from './pages/TasksPage';
import AdminPage from './pages/AdminPage';
import TermsPage from './pages/TermsPage';
import PrivacyPage from './pages/PrivacyPage';
import './index.css';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <CookieBanner />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/billing"
            element={
              <ProtectedRoute>
                <BillingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/tasks"
            element={
              <ProtectedRoute>
                <TasksPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
```

- [ ] **Step 2: Add admin nav link to `Navbar.jsx`**

In `web/src/components/Navbar.jsx`, in the `{user ? (... ) : (...)}` block, add the admin link after the Tasks link (after line 43):

```jsx
              {user.is_admin && (
                <Link to="/admin" className="btn btn-sm btn-ghost">Admin</Link>
              )}
```

The updated auth block should look like:

```jsx
        <div className="navbar-auth">
          {user ? (
            <>
              <Link to="/dashboard" className="btn btn-sm btn-ghost">Dashboard</Link>
              {(user.is_admin || (user.subscription_plan === 'enterprise' && user.subscription_status === 'active')) && (
                <Link to="/tasks" className="btn btn-sm btn-ghost">Tasks</Link>
              )}
              {user.is_admin && (
                <Link to="/admin" className="btn btn-sm btn-ghost">Admin</Link>
              )}
              <button className="btn btn-sm btn-outline" onClick={handleLogout}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn btn-sm btn-ghost">Login</Link>
              <Link to="/register" className="btn btn-sm btn-primary">Get Started</Link>
            </>
          )}
        </div>
```

- [ ] **Step 3: Commit**

```bash
git add web/src/App.jsx web/src/components/Navbar.jsx
git commit -m "feat: add /admin route and navbar link for admin users"
```

---

### Task 5: Add admin CSS to `index.css`

**Files:**
- Modify: `web/src/index.css`

- [ ] **Step 1: Append admin styles**

At the very end of `web/src/index.css`, append:

```css
/* ── Admin page ──────────────────────────────────────────── */
.admin-page { background: #0a0818; min-height: 100vh; position: relative; }
.admin-page-inner { position: relative; z-index: 1; }
.admin-denied { text-align: center; color: var(--text-dim); padding: 4rem 0; font-size: 18px; }
.admin-count { color: var(--text-faint); font-size: 13px; margin-top: 12px; text-align: right; }

.admin-table-wrap {
  overflow-x: auto;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--surface);
}
.admin-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.admin-table th {
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.admin-table td {
  padding: 10px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  vertical-align: middle;
}
.admin-table tr:last-child td { border-bottom: none; }
.admin-table tr:hover td { background: rgba(255,255,255,0.02); }

.admin-email { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.admin-date  { color: var(--text-dim); white-space: nowrap; }

.admin-select {
  background: rgba(255,255,255,0.06);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  outline: none;
}
.admin-select:focus { border-color: var(--accent); }
.admin-select:disabled { opacity: 0.5; cursor: not-allowed; }

.admin-cell { position: relative; }
.admin-cell--saving { opacity: 0.6; }
.admin-cell--saved .admin-select  { border-color: #34d399; }
.admin-cell--error .admin-select  { border-color: #f87171; }

.admin-flash {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 700;
  vertical-align: middle;
}
.admin-flash--ok  { color: #34d399; }
.admin-flash--err { color: #f87171; }
```

- [ ] **Step 2: Verify styles compile**

```bash
cd web && npm run build 2>&1 | tail -5
```

Expected: build output ending with no errors, e.g.:
```
✓ built in Xs
```

- [ ] **Step 3: Commit**

```bash
git add web/src/index.css
git commit -m "feat: admin page CSS"
```

---

### Task 6: End-to-end smoke test

- [ ] **Step 1: Start the stack**

Terminal 1 — backend:
```bash
cd backend && uvicorn main:app --reload --port 8000
```

Terminal 2 — frontend:
```bash
cd web && npm run dev
```

- [ ] **Step 2: Log in as admin user and verify**

1. Open `http://localhost:5173` and log in with an `is_admin=1` account (e.g. `dominic.rowle@yahoo.com` — it is auto-promoted to admin+enterprise on startup in `lifespan`).
2. Confirm "Admin" link appears in the navbar.
3. Navigate to `/admin` — table of users should load.
4. Change a user's plan dropdown — the cell border should turn green briefly.
5. Reload the page — confirm the new value persisted.

- [ ] **Step 3: Verify non-admin access is blocked**

Log out, log in as a non-admin user, navigate to `/admin` — page should show "Access denied."

- [ ] **Step 4: Final commit (if any fixups were needed)**

```bash
git add -p
git commit -m "fix: admin dashboard post-smoke-test fixups"
```
