---
name: Admin Dashboard
description: Internal admin page at /admin for managing all users — view usage, set plan and subscription status
type: project
---

# Admin Dashboard Design

## Goal

Build a protected `/admin` route accessible only to users with `is_admin=1`. The page shows a table of all users with their plan, subscription status, current-month message usage, and creation date. Admins can change any user's plan or subscription status via inline dropdowns that save immediately on change.

## Architecture

### Backend

**`GET /admin/users`**
- Auth: `Depends(auth.get_current_user)` + `is_admin` check (403 if not admin)
- Returns: list of user objects with an additional `messages_this_month` field
- Implementation: `db.get_all_users()` fetches all users ordered by `created_at DESC`; for each user, calls existing `db.get_monthly_usage(db_path, user_id, current_month)` to attach usage count

**`PATCH /admin/users/{user_id}`**
- Auth: same admin gate
- Body: `{ "field": "subscription_plan" | "subscription_status", "value": "<new_value>" }`
- Allowed values:
  - `subscription_plan`: `"free"`, `"pro"`, `"agency"`, `"enterprise"`
  - `subscription_status`: `"active"`, `"cancelled"`, `"free"`
- Implementation: validates field/value, calls existing `db.update_user(db_path, user_id, **{field: value})`
- Returns: `{ "ok": true }`

**`backend/db.py` — new function**
```python
def get_all_users(db_path: pathlib.Path) -> list:
    conn = _conn(db_path)
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

### Frontend

**`web/src/pages/AdminPage.jsx`** (new file)
- Fetches `GET /admin/users` on mount with Bearer token
- If 403 → renders "Access denied" message
- Renders a `<table>` with columns: Email | Name | Plan | Status | Msgs (month) | Created
- Plan and Status columns render `<select>` elements with current value pre-selected
- On `<select onChange>`: fires `PATCH /admin/users/{id}` with `{ field, value }`; during the request, adds a CSS class to show a spinner on that cell; on success shows ✓ briefly; on error reverts the select to its prior value and shows an error message

**`web/src/App.jsx`**
- Import `AdminPage` and add:
  ```jsx
  <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
  ```

**`web/src/components/Navbar.jsx`**
- Add a link visible only to admin users:
  ```jsx
  {user?.is_admin && <Link to="/admin">Admin</Link>}
  ```

**`web/src/index.css`**
- `.admin-table` — full-width table with bordered cells, follows existing card/table patterns
- `.admin-select` — compact select matching existing form input styles
- `.admin-cell--saving` — muted opacity + spinner indicator while PATCH is in-flight
- `.admin-cell--saved` — brief green tick after successful save

## Data Flow

```
AdminPage mount
  → GET /admin/users (with JWT)
    → backend: is_admin check → get_all_users() + get_monthly_usage() per user
    → returns [{id, email, name, subscription_plan, subscription_status, messages_this_month, created_at}, ...]
  → renders table

User changes a <select>
  → PATCH /admin/users/{id} { field, value }
    → backend: is_admin check → validate → update_user()
    → returns { ok: true }
  → cell shows ✓, local state updated
```

## Error Handling

- 403 on page load: render "Access denied — admin only" (no table)
- PATCH failure: revert `<select>` to previous value, show inline error text on that row
- Network error: same revert + error

## Out of Scope

- Pagination (not needed at current scale)
- Delete user functionality
- Impersonate user
- Audit log of admin changes
