# Credits Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the current Anthropic API credit balance to admin users in the bottom-right corner of the chat interface.

**Architecture:** A new `GET /admin/credits` FastAPI endpoint calls the Anthropic billing API using the existing `ANTHROPIC_API_KEY`, gracefully returning `null` if the key lacks billing scope. A new `CreditsIndicator` React component fetches this endpoint once on mount and renders a small pill in the chat window corner, visible to admins only.

**Tech Stack:** FastAPI, httpx, React 18, CSS custom properties (existing design system)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `zeus-app/backend/main.py` | Add `GET /admin/credits` endpoint |
| Create | `zeus-app/backend/tests/test_credits_endpoint.py` | Backend unit tests |
| Create | `zeus-app/web/src/components/CreditsIndicator.jsx` | Self-contained credit pill component |
| Modify | `zeus-app/web/src/components/ChatWindow.jsx` | Accept + render `CreditsIndicator` |
| Modify | `zeus-app/web/src/pages/DashboardPage.jsx` | Pass `isAdmin` + `token` to `ChatWindow` |
| Modify | `zeus-app/web/src/index.css` | Add `.credits-indicator` styles + `position: relative` to `.chat-window` |

---

### Task 1: Backend endpoint with tests

**Files:**
- Modify: `zeus-app/backend/main.py` (after the existing `/admin/users` block, around line 613)
- Create: `zeus-app/backend/tests/test_credits_endpoint.py`

- [ ] **Step 1: Write the failing tests**

Create `zeus-app/backend/tests/test_credits_endpoint.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


def _admin_user():
    return {
        "id": "admin-1",
        "email": "admin@example.com",
        "subscription_status": "active",
        "subscription_plan": "enterprise",
        "password_hash": "x",
        "name": "Admin",
        "is_admin": 1,
    }


def _regular_user():
    return {
        "id": "user-1",
        "email": "user@example.com",
        "subscription_status": "active",
        "subscription_plan": "pro",
        "password_hash": "x",
        "name": "User",
        "is_admin": 0,
    }


class TestCreditsEndpoint:
    def test_non_admin_gets_403(self):
        import auth
        import main as _main
        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _regular_user
        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/admin/credits",
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_admin_gets_balance_on_success(self):
        import auth
        import main as _main
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"balance": {"available": [{"amount": 1234, "currency": "USD"}]}}

        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _admin_user
        try:
            with patch("main.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client
                with TestClient(app) as client:
                    resp = client.get(
                        "/admin/credits",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["balance"] is not None
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_admin_gets_unavailable_on_anthropic_error(self):
        import auth
        import main as _main

        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _admin_user
        try:
            with patch("main.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(side_effect=Exception("connection failed"))
                mock_client_cls.return_value = mock_client
                with TestClient(app) as client:
                    resp = client.get(
                        "/admin/credits",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["balance"] is None
                    assert "unavailable" in data["message"].lower()
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_admin_gets_unavailable_on_403_from_anthropic(self):
        import auth
        import main as _main

        mock_response = MagicMock()
        mock_response.status_code = 403

        app = _main.app
        app.dependency_overrides[auth.get_current_user] = _admin_user
        try:
            with patch("main.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client
                with TestClient(app) as client:
                    resp = client.get(
                        "/admin/credits",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["balance"] is None
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_credits_endpoint.py -v
```

Expected: 4 failures — `404` or `AttributeError` because the endpoint doesn't exist yet.

- [ ] **Step 3: Add the endpoint to `main.py`**

Add this block after the `admin_patch_user` endpoint (around line 636), before the `/tasks` endpoint:

```python
@app.get("/admin/credits")
async def admin_credits(current_user: dict = Depends(auth.get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return {"balance": None, "message": "Balance unavailable"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.anthropic.com/v1/organizations/credits/balance",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=10,
            )
        if resp.status_code != 200:
            return {"balance": None, "message": "Balance unavailable"}
        data = resp.json()
        # Response shape: {"balance": {"available": [{"amount": 1234, "currency": "USD"}]}}
        available = data.get("balance", {}).get("available", [])
        if available:
            amount_cents = available[0].get("amount", 0)
            currency = available[0].get("currency", "USD")
            return {"balance": round(amount_cents / 100, 2), "currency": currency}
        return {"balance": None, "message": "Balance unavailable"}
    except Exception:
        return {"balance": None, "message": "Balance unavailable"}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd zeus-app/backend && python -m pytest tests/test_credits_endpoint.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd zeus-app
git add backend/main.py backend/tests/test_credits_endpoint.py
git commit -m "feat: add GET /admin/credits endpoint"
```

---

### Task 2: CreditsIndicator component

**Files:**
- Create: `zeus-app/web/src/components/CreditsIndicator.jsx`

- [ ] **Step 1: Create the component**

Create `zeus-app/web/src/components/CreditsIndicator.jsx`:

```jsx
import { useEffect, useState } from 'react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export function CreditsIndicator({ token, isAdmin }) {
  const [state, setState] = useState({ loading: true, balance: null, message: null });

  useEffect(() => {
    if (!isAdmin || !token) return;
    fetch(`${BACKEND_URL}/admin/credits`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => setState({ loading: false, balance: data.balance, message: data.message || null }))
      .catch(() => setState({ loading: false, balance: null, message: 'Balance unavailable' }));
  }, [token, isAdmin]);

  if (!isAdmin) return null;
  if (state.loading) return null;

  const label = state.balance !== null
    ? `⚡ $${state.balance.toFixed(2)} credits`
    : 'Balance unavailable';

  return (
    <div className="credits-indicator" title="Anthropic API credit balance">
      {label}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd zeus-app
git add web/src/components/CreditsIndicator.jsx
git commit -m "feat: add CreditsIndicator component"
```

---

### Task 3: Wire CreditsIndicator into ChatWindow and DashboardPage

**Files:**
- Modify: `zeus-app/web/src/components/ChatWindow.jsx`
- Modify: `zeus-app/web/src/pages/DashboardPage.jsx`

- [ ] **Step 1: Update `ChatWindow.jsx` to accept and render `CreditsIndicator`**

Replace the full contents of `zeus-app/web/src/components/ChatWindow.jsx`:

```jsx
import { useEffect, useRef, useState } from 'react';
import { MessageBubble } from './MessageBubble';
import { InputBar } from './InputBar';
import { Toolbar } from './Toolbar';
import { CreditsIndicator } from './CreditsIndicator';

export function ChatWindow({ messages, streaming, onSend, isAdmin, token }) {
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const [inputValue, setInputValue] = useState('');
  const [grammarMode, setGrammarMode] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleChipClick = (starter) => {
    setInputValue(starter);
    textareaRef.current?.focus();
  };

  return (
    <main className="chat-window">
      <div className="message-list">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">⚡</div>
            <div className="empty-title">Ask Zeus anything.</div>
            <div className="empty-sub">Websites · Writing · Research · Business</div>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreaming={
              streaming &&
              i === messages.length - 1 &&
              msg.role === 'zeus'
            }
          />
        ))}
        <div ref={bottomRef} />
      </div>
      <Toolbar onChipClick={handleChipClick} />
      <InputBar
        onSend={onSend}
        disabled={streaming}
        value={inputValue}
        setValue={setInputValue}
        grammarMode={grammarMode}
        setGrammarMode={setGrammarMode}
        textareaRef={textareaRef}
      />
      <CreditsIndicator token={token} isAdmin={isAdmin} />
    </main>
  );
}
```

- [ ] **Step 2: Update `DashboardPage.jsx` to pass `isAdmin` and `token` to `ChatWindow`**

In `DashboardPage.jsx`, find this block:

```jsx
        <ChatWindow
          messages={messages}
          streaming={streaming}
          onSend={sendMessage}
        />
```

Replace it with:

```jsx
        <ChatWindow
          messages={messages}
          streaming={streaming}
          onSend={sendMessage}
          isAdmin={!!user?.is_admin}
          token={token}
        />
```

- [ ] **Step 3: Commit**

```bash
cd zeus-app
git add web/src/components/ChatWindow.jsx web/src/pages/DashboardPage.jsx
git commit -m "feat: wire CreditsIndicator into ChatWindow and DashboardPage"
```

---

### Task 4: Add CSS styles

**Files:**
- Modify: `zeus-app/web/src/index.css`

- [ ] **Step 1: Add `position: relative` to `.chat-window` and the indicator styles**

In `index.css`, find this line:

```css
.chat-window { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
```

Replace it with:

```css
.chat-window { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
```

Then append the following at the end of `index.css`:

```css
/* ── Credits indicator ───────────────────── */
.credits-indicator {
  position: absolute;
  bottom: 4.5rem;
  right: 1rem;
  font-size: 11px;
  color: var(--text-faint);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 3px 10px;
  pointer-events: none;
  user-select: none;
  white-space: nowrap;
}
```

> Note: `bottom: 4.5rem` clears the InputBar. Adjust if the input bar height changes.

- [ ] **Step 2: Commit**

```bash
cd zeus-app
git add web/src/index.css
git commit -m "feat: add credits indicator styles"
```

---

### Task 5: Smoke test end-to-end

- [ ] **Step 1: Run all backend tests to confirm no regressions**

```bash
cd zeus-app/backend && python -m pytest tests/ -v
```

Expected: all tests pass including the 4 new credits tests.

- [ ] **Step 2: Start the dev server and verify visually**

```bash
cd zeus-app/web && npm run dev
```

- Log in as the admin account (`dominic.rowle@yahoo.com`).
- Open the chat dashboard. The indicator should appear in the bottom-right corner of the chat window showing either `⚡ $XX.XX credits` or `Balance unavailable`.
- Log in as a non-admin account — the indicator must not appear.

- [ ] **Step 3: Confirm indicator is absent for non-admin**

In browser devtools, confirm the `.credits-indicator` element is not present in the DOM when logged in as a non-admin user.
