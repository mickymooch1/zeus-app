# Zeus Baby Beats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully kid-safe `/kids` route inside web-beats with parent PIN-switch (standard accounts) and school-only accounts that are permanently locked to kids mode.

**Architecture:** A `KidsShell` component renders a completely separate light/rainbow UI at `/kids` — no adult components imported. Safety is enforced at three layers: server-side (explicit forced false, mixer blocked for school accounts), route guard in `App.jsx`, and sessionStorage flag for parent PIN sessions. Three new DB columns added via the existing migration pattern in `db.py`.

**Tech Stack:** React + React Router (frontend), FastAPI + SQLite (backend), bcrypt (PIN hashing via existing `auth.py`), Tailwind-style inline styles + `kids.css` light theme.

---

## File Map

**Backend — create/modify:**
- `backend/db.py` — add 3 columns + helper functions for PIN + school registration
- `backend/main.py` — add 4 endpoints: school register, PIN set, PIN verify, safety guard

**Frontend — create:**
- `web-beats/src/kids.css` — light theme (no dark/neon)
- `web-beats/src/components/KidsShell.jsx` — layout wrapper + Ziggy mascot
- `web-beats/src/components/ParentPINGate.jsx` — 4-digit PIN modal
- `web-beats/src/pages/kids/KidsHomePage.jsx` — two big buttons
- `web-beats/src/pages/kids/KidsSongMode.jsx` — simplified song creation
- `web-beats/src/pages/kids/KidsStoryMode.jsx` — story creation, kids wrapper
- `web-beats/src/pages/SchoolRegisterPage.jsx` — school registration form

**Frontend — modify:**
- `web-beats/src/App.jsx` — add `/kids/*` routes + school account route guard
- `web-beats/src/components/ProtectedRoute.jsx` — add `SchoolRoute` variant
- `web-beats/src/pages/SongsPage.jsx` — add "Switch to Zeus Baby Beats" button
- `web-beats/src/pages/PrivacyPage.jsx` — add Children's Data section

---

## Task 1: DB migrations — account_type, kids_pin_hash, school_verified

**Files:**
- Modify: `backend/db.py` (migration list + helper functions)

- [ ] **Step 1: Add the three migrations to the existing migration list**

In `backend/db.py`, find the list of `ALTER TABLE` migrations (around line 237). Add these three entries at the end of the list, before the closing `]`:

```python
            "ALTER TABLE users ADD COLUMN account_type TEXT NOT NULL DEFAULT 'standard'",
            "ALTER TABLE users ADD COLUMN kids_pin_hash TEXT",
            "ALTER TABLE users ADD COLUMN school_verified INTEGER NOT NULL DEFAULT 0",
```

The existing migration runner wraps each in `try/except` so re-running is safe.

- [ ] **Step 2: Add PIN helper functions to `db.py`**

After the `update_user_by_email` function (around line 438), add:

```python
def set_kids_pin(db_path: pathlib.Path, user_id: str, pin_hash: str) -> None:
    """Store a bcrypt-hashed 4-digit PIN for kids mode."""
    update_user(db_path, user_id, kids_pin_hash=pin_hash)


def get_kids_pin_hash(db_path: pathlib.Path, user_id: str) -> str | None:
    """Return the stored PIN hash, or None if not set."""
    user = get_user_by_id(db_path, user_id)
    return user.get("kids_pin_hash") if user else None


def set_school_verified(db_path: pathlib.Path, user_id: str, verified: bool) -> None:
    update_user(db_path, user_id, school_verified=1 if verified else 0)
```

- [ ] **Step 3: Verify syntax**

```bash
python -c "import ast, sys; ast.parse(open('backend/db.py', encoding='utf-8').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/db.py
git commit -m "feat(db): add account_type, kids_pin_hash, school_verified columns"
```

---

## Task 2: Backend — school registration endpoint

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add `SchoolRegisterRequest` model**

Find the existing `RegisterRequest` model in `main.py` (search for `class RegisterRequest`). Add this new model directly after it:

```python
class SchoolRegisterRequest(BaseModel):
    school_name: str
    teacher_name: str
    email: str
    password: str
    year_group: str          # e.g. "Reception–Year 2", "Year 3–6"
    country: str = "UK"
```

- [ ] **Step 2: Add school domain checker and `_SCHOOL_DOMAINS` constant**

After `_BLOCKED_EMAIL_DOMAINS` (search for that constant), add:

```python
# Domains that auto-verify as genuine school accounts
_SCHOOL_DOMAINS = {".sch.uk", ".edu", ".ac.uk", ".school", ".k12.us", ".k12"}

def _is_school_domain(email: str) -> bool:
    domain = email.split("@")[-1].lower() if "@" in email else ""
    return any(domain.endswith(s) for s in _SCHOOL_DOMAINS)
```

- [ ] **Step 3: Add `/auth/register/school` endpoint**

Add this endpoint after the existing `/auth/register` endpoint:

```python
@app.post("/auth/register/school")
@limiter.limit("5/minute")
async def register_school(request: Request, body: SchoolRegisterRequest):
    if not body.email or "@" not in body.email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not body.school_name.strip():
        raise HTTPException(status_code=400, detail="School name is required")

    db_path = db.get_db_path()
    if db.get_user_by_email(db_path, body.email):
        raise HTTPException(status_code=409, detail="An account with that email already exists")

    password_hash = auth.hash_password(body.password)
    now = datetime.now(timezone.utc).isoformat()

    user = db.create_user(
        db_path,
        email=body.email,
        password_hash=password_hash,
        name=body.teacher_name.strip(),
        tc_accepted_at=now,
    )
    # Mark as school account
    db.update_user(db_path, user["id"], account_type="school", artist_name=body.school_name.strip())

    verified = _is_school_domain(body.email)
    db.set_school_verified(db_path, user["id"], verified)

    # Give school accounts a generous song credit allowance (free tier)
    db.ensure_free_song_credits(db_path, user["id"], balance=20, monthly_allowance=20)

    if not verified:
        try:
            from telegram_admin import parse_and_run
            parse_and_run(
                f"New school signup needs review: {body.email} (school: {body.school_name}). "
                f"Personal email domain — please verify it's a real school.",
                chat_id="",
            )
        except Exception:
            log.warning("register_school: could not send Telegram alert for %s", body.email)

    token = auth.create_token(user["id"], user["email"], is_admin=False)
    safe_user = {k: v for k, v in db.get_user_by_id(db_path, user["id"]).items() if k != "password_hash"}
    log.info("register_school: new school account email=%s verified=%s", body.email, verified)
    return {"token": token, "user": safe_user}
```

- [ ] **Step 4: Verify syntax**

```bash
python -c "import ast, sys; ast.parse(open('backend/main.py', encoding='utf-8').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat(backend): school registration endpoint with domain auto-verify"
```

---

## Task 3: Backend — Kids PIN set/verify endpoints + safety enforcement

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add PIN request models**

After `SchoolRegisterRequest`, add:

```python
class KidsPINSetRequest(BaseModel):
    pin: str   # 4-digit string

class KidsPINVerifyRequest(BaseModel):
    pin: str
```

- [ ] **Step 2: Add `POST /kids/pin/set` endpoint**

```python
@app.post("/kids/pin/set")
async def kids_pin_set(body: KidsPINSetRequest, current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("account_type") == "school":
        raise HTTPException(status_code=403, detail="School accounts do not use a PIN")
    if not body.pin or not body.pin.isdigit() or len(body.pin) != 4:
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    db_path = db.get_db_path()
    pin_hash = auth.hash_password(body.pin)
    db.set_kids_pin(db_path, current_user["id"], pin_hash)
    return {"ok": True}
```

- [ ] **Step 3: Add `POST /kids/pin/verify` endpoint**

```python
@app.post("/kids/pin/verify")
async def kids_pin_verify(body: KidsPINVerifyRequest, current_user: dict = Depends(auth.get_current_user)):
    if current_user.get("account_type") == "school":
        raise HTTPException(status_code=403, detail="School accounts do not use a PIN")
    db_path = db.get_db_path()
    stored_hash = db.get_kids_pin_hash(db_path, current_user["id"])
    if not stored_hash:
        raise HTTPException(status_code=404, detail="No PIN set — please set a PIN in account settings first")
    if not auth.verify_password(body.pin, stored_hash):
        raise HTTPException(status_code=401, detail="Incorrect PIN")
    return {"ok": True}
```

- [ ] **Step 4: Add school account safety enforcement**

Find the `generate` endpoint (search for `@app.post("/generate")`). Add this check near the top of the function body, after `db_path = db.get_db_path()`:

```python
    # School accounts: enforce safe content regardless of request
    if current_user.get("account_type") == "school":
        body.explicit = False
```

Find the mixer endpoint (search for `@app.post("/mixer")`). Add at the top of the handler:

```python
    if current_user.get("account_type") == "school":
        raise HTTPException(status_code=403, detail="Mixer is not available on school accounts")
```

- [ ] **Step 5: Verify syntax**

```bash
python -c "import ast, sys; ast.parse(open('backend/main.py', encoding='utf-8').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/main.py
git commit -m "feat(backend): kids PIN endpoints + school account safety enforcement"
```

---

## Task 4: Frontend — `kids.css` light theme

**Files:**
- Create: `web-beats/src/kids.css`

- [ ] **Step 1: Create the kids CSS file**

Create `web-beats/src/kids.css` with this content:

```css
/* ── Zeus Baby Beats — light theme ──────────────────────────
   Scoped to .kids-shell. Never leaks into adult UI.
   ──────────────────────────────────────────────────────────── */

@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap');

.kids-shell {
  min-height: 100dvh;
  background: linear-gradient(160deg, #fff9e6 0%, #e0f4ff 60%, #fce4f0 100%);
  font-family: 'Nunito', ui-rounded, system-ui, sans-serif;
  color: #1a2b4a;
  position: relative;
  overflow-x: hidden;
}

/* ── Typography ──────────────────────────────────────────── */
.kids-shell h1, .kids-shell h2, .kids-shell h3 {
  font-family: 'Nunito', ui-rounded, system-ui, sans-serif;
  font-weight: 900;
  color: #1a2b4a;
}

/* ── Buttons ─────────────────────────────────────────────── */
.kids-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 72px;
  min-width: 260px;
  border-radius: 36px;
  border: none;
  font-family: 'Nunito', ui-rounded, system-ui, sans-serif;
  font-size: 20px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  padding: 0 32px;
  letter-spacing: 0.01em;
}
.kids-btn:hover { transform: scale(1.05); }
.kids-btn:active { transform: scale(0.97); }

.kids-btn-primary {
  background: linear-gradient(135deg, #fbd155 0%, #ffa726 100%);
  color: #1a2b4a;
  box-shadow: 0 6px 24px rgba(251,209,85,0.5);
}
.kids-btn-primary:hover { box-shadow: 0 10px 32px rgba(251,209,85,0.65); }

.kids-btn-coral {
  background: linear-gradient(135deg, #ff6b9d 0%, #ff4081 100%);
  color: #fff;
  box-shadow: 0 6px 24px rgba(255,107,157,0.45);
}
.kids-btn-coral:hover { box-shadow: 0 10px 32px rgba(255,107,157,0.6); }

.kids-btn-mint {
  background: linear-gradient(135deg, #4ecdc4 0%, #26a69a 100%);
  color: #fff;
  box-shadow: 0 6px 24px rgba(78,205,196,0.45);
}
.kids-btn-ghost {
  background: rgba(255,255,255,0.7);
  color: #45b7d1;
  border: 2px solid #45b7d1;
  box-shadow: none;
}

/* ── Theme tiles (emoji pickers) ─────────────────────────── */
.kids-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 88px;
  height: 88px;
  border-radius: 20px;
  border: 3px solid transparent;
  background: rgba(255,255,255,0.8);
  cursor: pointer;
  transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
  font-size: 32px;
}
.kids-tile span { font-size: 11px; font-weight: 700; color: #1a2b4a; }
.kids-tile:hover { transform: scale(1.08); }
.kids-tile.selected {
  border-color: #fbd155;
  background: rgba(251,209,85,0.18);
  box-shadow: 0 0 0 4px rgba(251,209,85,0.25);
}

/* ── PIN pad ─────────────────────────────────────────────── */
.kids-pin-dot {
  width: 18px; height: 18px;
  border-radius: 50%;
  background: #cbd5e1;
  transition: background 0.15s;
}
.kids-pin-dot.filled { background: #fbd155; }

.kids-pin-key {
  width: 72px; height: 72px;
  border-radius: 50%;
  border: 2px solid rgba(69,183,209,0.4);
  background: rgba(255,255,255,0.85);
  font-family: 'Nunito', sans-serif;
  font-size: 26px;
  font-weight: 800;
  color: #1a2b4a;
  cursor: pointer;
  transition: transform 0.1s, background 0.1s;
  display: flex; align-items: center; justify-content: center;
}
.kids-pin-key:hover { transform: scale(1.08); background: rgba(69,183,209,0.12); }
.kids-pin-key:active { transform: scale(0.94); }

/* ── Cards ───────────────────────────────────────────────── */
.kids-card {
  background: rgba(255,255,255,0.85);
  border-radius: 24px;
  padding: 28px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

/* ── Form inputs ─────────────────────────────────────────── */
.kids-input {
  width: 100%;
  padding: 14px 18px;
  border-radius: 16px;
  border: 2px solid rgba(69,183,209,0.35);
  background: rgba(255,255,255,0.9);
  font-family: 'Nunito', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: #1a2b4a;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.kids-input:focus { border-color: #45b7d1; }

.kids-select {
  width: 100%;
  padding: 14px 18px;
  border-radius: 16px;
  border: 2px solid rgba(69,183,209,0.35);
  background: rgba(255,255,255,0.9);
  font-family: 'Nunito', sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: #1a2b4a;
  outline: none;
  cursor: pointer;
  appearance: none;
}

/* ── Ziggy bounce ────────────────────────────────────────── */
@keyframes ziggyBounce {
  0%, 100% { transform: translateY(0); }
  40%       { transform: translateY(-12px); }
  60%       { transform: translateY(-6px); }
}
.ziggy-bounce { animation: ziggyBounce 2s ease-in-out infinite; }

/* ── Rainbow shimmer on title ────────────────────────────── */
@keyframes rainbowShift {
  0%   { background-position: 0% 50%; }
  100% { background-position: 200% 50%; }
}
.kids-rainbow-text {
  background: linear-gradient(90deg, #ff6b9d, #fbd155, #4ecdc4, #45b7d1, #a78bfa, #ff6b9d);
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: rainbowShift 4s linear infinite;
}

/* ── Responsive ──────────────────────────────────────────── */
@media (max-width: 480px) {
  .kids-btn { min-width: 220px; font-size: 18px; min-height: 64px; }
  .kids-tile { width: 76px; height: 76px; font-size: 28px; }
  .kids-pin-key { width: 64px; height: 64px; font-size: 22px; }
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/kids.css
git commit -m "feat(ui): kids.css light theme for Zeus Baby Beats"
```

---

## Task 5: Frontend — `KidsShell` + Ziggy mascot

**Files:**
- Create: `web-beats/src/components/KidsShell.jsx`

- [ ] **Step 1: Create `KidsShell.jsx`**

```jsx
import '../kids.css';

// Ziggy: friendly baby lightning bolt SVG mascot
function Ziggy({ size = 56 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg" className="ziggy-bounce">
      {/* Head */}
      <circle cx="28" cy="18" r="13" fill="#FBD155" stroke="#F59E0B" strokeWidth="2"/>
      {/* Eyes */}
      <circle cx="23" cy="16" r="2.5" fill="#1A2B4A"/>
      <circle cx="33" cy="16" r="2.5" fill="#1A2B4A"/>
      {/* Smile */}
      <path d="M22 22 Q28 27 34 22" stroke="#1A2B4A" strokeWidth="2" strokeLinecap="round" fill="none"/>
      {/* Lightning body */}
      <path d="M28 31 L20 42 L27 42 L23 54 L36 39 L29 39 L34 31 Z" fill="#FBD155" stroke="#F59E0B" strokeWidth="1.5" strokeLinejoin="round"/>
      {/* Sparkles */}
      <circle cx="10" cy="12" r="2" fill="#FF6B9D" opacity="0.8"/>
      <circle cx="46" cy="20" r="1.5" fill="#4ECDC4" opacity="0.8"/>
      <circle cx="8" cy="30" r="1.5" fill="#A78BFA" opacity="0.7"/>
      <circle cx="48" cy="8" r="2" fill="#FBD155" opacity="0.8"/>
    </svg>
  );
}

export default function KidsShell({ children, showExitBtn = false, onExitClick }) {
  return (
    <div className="kids-shell" style={{ display: 'flex', flexDirection: 'column', minHeight: '100dvh' }}>
      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px 20px', gap: 12, position: 'relative',
      }}>
        <Ziggy size={48} />
        <h1 style={{ margin: 0, fontSize: 'clamp(22px, 5vw, 32px)', fontWeight: 900, lineHeight: 1 }}>
          <span className="kids-rainbow-text">Zeus Baby Beats</span>
          <span style={{ marginLeft: 8 }}>🧸</span>
        </h1>
        {showExitBtn && (
          <button
            onClick={onExitClick}
            style={{
              position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)',
              background: 'rgba(255,255,255,0.7)', border: '2px solid #45b7d1',
              borderRadius: 20, padding: '6px 14px', fontSize: 12, fontWeight: 700,
              color: '#45b7d1', cursor: 'pointer',
            }}
          >
            🔑 Parent Exit
          </button>
        )}
      </header>

      {/* Main content */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {children}
      </main>

      {/* Footer */}
      <footer style={{ textAlign: 'center', padding: '12px 20px', fontSize: 12, color: '#94a3b8' }}>
        Zeus Baby Beats 🧸 — Safe songs &amp; stories for little ones
      </footer>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/components/KidsShell.jsx
git commit -m "feat(ui): KidsShell layout wrapper with Ziggy mascot"
```

---

## Task 6: Frontend — `ParentPINGate` modal

**Files:**
- Create: `web-beats/src/components/ParentPINGate.jsx`

- [ ] **Step 1: Create `ParentPINGate.jsx`**

```jsx
import { useState } from 'react';
import { BACKEND_URL } from '../brand';

// action: 'enter' (going into kids) | 'exit' (leaving kids)
export default function ParentPINGate({ token, action = 'enter', onSuccess, onCancel }) {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [shake, setShake] = useState(false);
  const [loading, setLoading] = useState(false);

  const digits = [1,2,3,4,5,6,7,8,9,'',0,'⌫'];

  const handleKey = (k) => {
    if (k === '⌫') {
      setPin(p => p.slice(0, -1));
      setError('');
      return;
    }
    if (k === '') return;
    if (pin.length >= 4) return;
    const next = pin + String(k);
    setPin(next);
    if (next.length === 4) submit(next);
  };

  const submit = async (code) => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/kids/pin/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ pin: code }),
      });
      if (res.ok) {
        onSuccess();
      } else {
        setShake(true);
        setError('Oops! Try again 😊');
        setPin('');
        setTimeout(() => setShake(false), 500);
      }
    } catch {
      setError('Connection error — try again');
      setPin('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(26,43,74,0.55)', backdropFilter: 'blur(6px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 16,
    }}>
      <div className="kids-card" style={{
        maxWidth: 360, width: '100%', textAlign: 'center',
        animation: shake ? 'shake 0.4s ease' : 'none',
      }}>
        <style>{`
          @keyframes shake {
            0%,100% { transform: translateX(0); }
            20%,60%  { transform: translateX(-8px); }
            40%,80%  { transform: translateX(8px); }
          }
        `}</style>

        <div style={{ fontSize: 40, marginBottom: 8 }}>🔑</div>
        <h2 style={{ margin: '0 0 4px', fontSize: 20 }}>Parent exit code</h2>
        <p style={{ margin: '0 0 20px', fontSize: 14, color: '#64748b' }}>
          {action === 'exit' ? 'Enter your PIN to return to Zeus Beats' : 'Enter your PIN to open Zeus Baby Beats'}
        </p>

        {/* PIN dots */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginBottom: 24 }}>
          {[0,1,2,3].map(i => (
            <div key={i} className={`kids-pin-dot${pin.length > i ? ' filled' : ''}`} />
          ))}
        </div>

        {/* Error */}
        {error && <p style={{ color: '#ef4444', fontSize: 14, margin: '0 0 12px', fontWeight: 700 }}>{error}</p>}

        {/* Keypad */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, maxWidth: 260, margin: '0 auto 20px' }}>
          {digits.map((d, i) => (
            <button
              key={i}
              onClick={() => handleKey(d)}
              disabled={loading}
              className="kids-pin-key"
              style={{ opacity: d === '' ? 0 : 1, pointerEvents: d === '' ? 'none' : 'auto' }}
            >
              {d}
            </button>
          ))}
        </div>

        <button onClick={onCancel} className="kids-btn kids-btn-ghost" style={{ minWidth: 120, minHeight: 44, fontSize: 14 }}>
          Cancel
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/components/ParentPINGate.jsx
git commit -m "feat(ui): ParentPINGate 4-digit PIN modal"
```

---

## Task 7: Frontend — `KidsHomePage`

**Files:**
- Create: `web-beats/src/pages/kids/` directory
- Create: `web-beats/src/pages/kids/KidsHomePage.jsx`

- [ ] **Step 1: Create the `kids/` directory and `KidsHomePage.jsx`**

```jsx
import { useNavigate } from 'react-router-dom';

export default function KidsHomePage() {
  const navigate = useNavigate();

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '24px 20px', gap: 24,
      textAlign: 'center',
    }}>
      <p style={{ fontSize: 'clamp(16px, 3vw, 20px)', color: '#64748b', margin: 0, fontWeight: 600 }}>
        What would you like to make today? ✨
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, width: '100%', maxWidth: 320 }}>
        <button
          className="kids-btn kids-btn-primary"
          style={{ width: '100%' }}
          onClick={() => navigate('/kids/song')}
        >
          🎵 Make a Song!
        </button>

        <button
          className="kids-btn kids-btn-coral"
          style={{ width: '100%' }}
          onClick={() => navigate('/kids/story')}
        >
          📖 Hear a Story!
        </button>
      </div>

      {/* Decorative bubbles */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', overflow: 'hidden', zIndex: 0 }}>
        {['🌟','⭐','✨','🎵','🎶','💛','🌈'].map((e, i) => (
          <span key={i} style={{
            position: 'absolute',
            fontSize: `${14 + (i * 4) % 18}px`,
            left: `${(i * 13 + 5) % 90}%`,
            top: `${(i * 17 + 10) % 80}%`,
            opacity: 0.25,
            animation: `ziggyBounce ${2 + i * 0.4}s ease-in-out infinite`,
            animationDelay: `${i * 0.3}s`,
          }}>{e}</span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/pages/kids/KidsHomePage.jsx
git commit -m "feat(ui): KidsHomePage — two big buttons for song and story"
```

---

## Task 8: Frontend — `KidsSongMode`

**Files:**
- Create: `web-beats/src/pages/kids/KidsSongMode.jsx`

- [ ] **Step 1: Create `KidsSongMode.jsx`**

```jsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

const THEMES = [
  { emoji: '🐘', label: 'Animals',   genres: ['kids pop', 'childrens'] },
  { emoji: '🚀', label: 'Space',     genres: ['kids pop', 'fun electronic'] },
  { emoji: '🌈', label: 'Magic',     genres: ['childrens', 'fantasy pop'] },
  { emoji: '🐠', label: 'Ocean',     genres: ['kids pop', 'relaxed'] },
  { emoji: '🦁', label: 'Safari',    genres: ['kids pop', 'world'] },
  { emoji: '❄️',  label: 'Winter',   genres: ['childrens', 'festive'] },
];

const AGE_RANGES = [
  { value: 'tiny_tots',   label: '👶 Tiny Tots',   sub: 'Ages 2–4' },
  { value: 'little_ones', label: '🧒 Little Ones',  sub: 'Ages 4–6' },
  { value: 'big_kids',    label: '🧑 Big Kids',     sub: 'Ages 7–10' },
];

export default function KidsSongMode() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(null);
  const [age, setAge] = useState('little_ones');
  const [character, setCharacter] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  const canGenerate = theme !== null;

  const handleGenerate = async () => {
    if (!canGenerate || generating) return;
    setGenerating(true);
    setError('');
    try {
      const res = await fetch(`${BACKEND_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          prompt: character.trim()
            ? `A fun kids song about ${character.trim()} with a ${THEMES[theme].label.toLowerCase()} theme`
            : `A fun kids song with a ${THEMES[theme].label.toLowerCase()} theme`,
          genres: THEMES[theme].genres,
          kids_mode: 'song',
          age_range: age,
          explicit: false,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Could not make the song');
      }
      navigate('/kids/songs');
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div style={{ flex: 1, padding: '16px 20px 32px', maxWidth: 520, margin: '0 auto', width: '100%' }}>
      <button onClick={() => navigate('/kids')} style={{ background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 14, cursor: 'pointer', marginBottom: 16, padding: 0 }}>
        ← Back
      </button>

      <h2 style={{ margin: '0 0 6px', fontSize: 22 }}>What kind of song? 🎶</h2>
      <p style={{ margin: '0 0 20px', color: '#64748b', fontSize: 14 }}>Pick a theme to get started!</p>

      {/* Theme tiles */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginBottom: 24 }}>
        {THEMES.map((t, i) => (
          <button key={i} className={`kids-tile${theme === i ? ' selected' : ''}`} onClick={() => setTheme(i)}>
            {t.emoji}
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Age range */}
      <p style={{ fontWeight: 700, fontSize: 14, margin: '0 0 10px' }}>Who is it for?</p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {AGE_RANGES.map(a => (
          <button
            key={a.value}
            onClick={() => setAge(a.value)}
            style={{
              flex: '1 1 90px', padding: '10px 8px', borderRadius: 16, border: `2px solid ${age === a.value ? '#fbd155' : 'rgba(69,183,209,0.3)'}`,
              background: age === a.value ? 'rgba(251,209,85,0.15)' : 'rgba(255,255,255,0.7)',
              cursor: 'pointer', fontFamily: 'Nunito, sans-serif', fontWeight: 700, fontSize: 13, color: '#1a2b4a',
            }}
          >
            {a.label}<br/><span style={{ fontSize: 11, fontWeight: 400, color: '#64748b' }}>{a.sub}</span>
          </button>
        ))}
      </div>

      {/* Optional character name */}
      <p style={{ fontWeight: 700, fontSize: 14, margin: '0 0 8px' }}>Who is the song about? (optional)</p>
      <input
        className="kids-input"
        placeholder="e.g. Bella the bunny, Leo the lion..."
        value={character}
        onChange={e => setCharacter(e.target.value)}
        style={{ marginBottom: 24 }}
      />

      {error && <p style={{ color: '#ef4444', fontWeight: 700, fontSize: 14, marginBottom: 12 }}>{error}</p>}

      <button
        className="kids-btn kids-btn-primary"
        style={{ width: '100%', opacity: canGenerate ? 1 : 0.5 }}
        disabled={!canGenerate || generating}
        onClick={handleGenerate}
      >
        {generating ? '✨ Making your song...' : '✨ Make My Song!'}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/pages/kids/KidsSongMode.jsx
git commit -m "feat(ui): KidsSongMode — simplified kids song creation"
```

---

## Task 9: Frontend — `KidsStoryMode`

**Files:**
- Create: `web-beats/src/pages/kids/KidsStoryMode.jsx`

- [ ] **Step 1: Create `KidsStoryMode.jsx`**

```jsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

const THEMES = [
  { emoji: '🐉', label: 'Dragons' },
  { emoji: '🧚', label: 'Fairies' },
  { emoji: '🌙', label: 'Bedtime' },
  { emoji: '🏴‍☠️', label: 'Pirates' },
  { emoji: '🦄', label: 'Unicorns' },
  { emoji: '🌳', label: 'Forest' },
];

const AGE_RANGES = [
  { value: 'tiny_tots',   label: '👶 Tiny Tots',   sub: 'Ages 2–4' },
  { value: 'little_ones', label: '🧒 Little Ones',  sub: 'Ages 4–6' },
  { value: 'big_kids',    label: '🧑 Big Kids',     sub: 'Ages 7–10' },
];

const LANGUAGES = [
  { value: 'english',  flag: '🇬🇧', label: 'English' },
  { value: 'spanish',  flag: '🇪🇸', label: 'Spanish' },
  { value: 'french',   flag: '🇫🇷', label: 'French' },
  { value: 'german',   flag: '🇩🇪', label: 'German' },
  { value: 'italian',  flag: '🇮🇹', label: 'Italian' },
  { value: 'portuguese', flag: '🇵🇹', label: 'Portuguese' },
];

export default function KidsStoryMode() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(null);
  const [age, setAge] = useState('little_ones');
  const [language, setLanguage] = useState('english');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  const canGenerate = theme !== null;

  const handleGenerate = async () => {
    if (!canGenerate || generating) return;
    setGenerating(true);
    setError('');
    try {
      const res = await fetch(`${BACKEND_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          prompt: `A magical ${THEMES[theme].label.toLowerCase()} story for children`,
          kids_mode: 'story',
          age_range: age,
          story_language: language,
          explicit: false,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Could not make the story');
      }
      navigate('/kids/songs');
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div style={{ flex: 1, padding: '16px 20px 32px', maxWidth: 520, margin: '0 auto', width: '100%' }}>
      <button onClick={() => navigate('/kids')} style={{ background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 14, cursor: 'pointer', marginBottom: 16, padding: 0 }}>
        ← Back
      </button>

      <h2 style={{ margin: '0 0 6px', fontSize: 22 }}>What's the story about? 📖</h2>
      <p style={{ margin: '0 0 20px', color: '#64748b', fontSize: 14 }}>Pick a theme and we'll tell you a magical story!</p>

      {/* Theme tiles */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center', marginBottom: 24 }}>
        {THEMES.map((t, i) => (
          <button key={i} className={`kids-tile${theme === i ? ' selected' : ''}`} onClick={() => setTheme(i)}>
            {t.emoji}
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Age range */}
      <p style={{ fontWeight: 700, fontSize: 14, margin: '0 0 10px' }}>Who is the story for?</p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        {AGE_RANGES.map(a => (
          <button
            key={a.value}
            onClick={() => setAge(a.value)}
            style={{
              flex: '1 1 90px', padding: '10px 8px', borderRadius: 16,
              border: `2px solid ${age === a.value ? '#fbd155' : 'rgba(69,183,209,0.3)'}`,
              background: age === a.value ? 'rgba(251,209,85,0.15)' : 'rgba(255,255,255,0.7)',
              cursor: 'pointer', fontFamily: 'Nunito, sans-serif', fontWeight: 700, fontSize: 13, color: '#1a2b4a',
            }}
          >
            {a.label}<br/><span style={{ fontSize: 11, fontWeight: 400, color: '#64748b' }}>{a.sub}</span>
          </button>
        ))}
      </div>

      {/* Language */}
      <p style={{ fontWeight: 700, fontSize: 14, margin: '0 0 10px' }}>Story language</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 24 }}>
        {LANGUAGES.map(l => (
          <button
            key={l.value}
            onClick={() => setLanguage(l.value)}
            style={{
              padding: '8px 14px', borderRadius: 12,
              border: `2px solid ${language === l.value ? '#4ecdc4' : 'rgba(69,183,209,0.25)'}`,
              background: language === l.value ? 'rgba(78,205,196,0.15)' : 'rgba(255,255,255,0.7)',
              cursor: 'pointer', fontFamily: 'Nunito, sans-serif', fontWeight: 700, fontSize: 13, color: '#1a2b4a',
            }}
          >
            {l.flag} {l.label}
          </button>
        ))}
      </div>

      {error && <p style={{ color: '#ef4444', fontWeight: 700, fontSize: 14, marginBottom: 12 }}>{error}</p>}

      <button
        className="kids-btn kids-btn-coral"
        style={{ width: '100%', opacity: canGenerate ? 1 : 0.5 }}
        disabled={!canGenerate || generating}
        onClick={handleGenerate}
      >
        {generating ? '📖 Creating your story...' : '📖 Tell My Story!'}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/pages/kids/KidsStoryMode.jsx
git commit -m "feat(ui): KidsStoryMode — kids story creation with theme and language picker"
```

---

## Task 10: Frontend — `SchoolRegisterPage`

**Files:**
- Create: `web-beats/src/pages/SchoolRegisterPage.jsx`

- [ ] **Step 1: Create `SchoolRegisterPage.jsx`**

```jsx
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { BACKEND_URL } from '../brand';
import KidsShell from '../components/KidsShell';

const YEAR_GROUPS = [
  'Nursery / Pre-school (ages 3–4)',
  'Reception (age 4–5)',
  'Year 1–2 (ages 5–7)',
  'Year 3–4 (ages 7–9)',
  'Year 5–6 (ages 9–11)',
  'Mixed age class',
];

export default function SchoolRegisterPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ school_name: '', teacher_name: '', email: '', password: '', year_group: '', country: 'UK' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.school_name || !form.teacher_name || !form.email || !form.password || !form.year_group) {
      setError('Please fill in all fields');
      return;
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/auth/register/school`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');

      // Log in with returned token + user
      localStorage.setItem('zeus_token', data.token);
      // Reload auth state by refreshing
      window.location.href = '/kids';
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KidsShell>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px 20px' }}>
        <div className="kids-card" style={{ maxWidth: 440, width: '100%' }}>
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>🏫</div>
            <h2 style={{ margin: '0 0 4px', fontSize: 22 }}>School Sign Up</h2>
            <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
              Safe AI music and stories for your class
            </p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>School name</label>
              <input className="kids-input" placeholder="e.g. Sunflower Primary School" value={form.school_name} onChange={set('school_name')} />
            </div>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>Your name (teacher)</label>
              <input className="kids-input" placeholder="e.g. Ms Johnson" value={form.teacher_name} onChange={set('teacher_name')} />
            </div>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>School email</label>
              <input className="kids-input" type="email" placeholder="you@school.sch.uk" value={form.email} onChange={set('email')} />
            </div>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>Year group</label>
              <select className="kids-select" value={form.year_group} onChange={set('year_group')}>
                <option value="">Select year group...</option>
                {YEAR_GROUPS.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontWeight: 700, fontSize: 13, display: 'block', marginBottom: 4 }}>Password</label>
              <input className="kids-input" type="password" placeholder="At least 8 characters" value={form.password} onChange={set('password')} />
            </div>

            {error && <p style={{ color: '#ef4444', fontWeight: 700, fontSize: 13, margin: 0 }}>{error}</p>}

            <button type="submit" className="kids-btn kids-btn-primary" style={{ width: '100%', marginTop: 8 }} disabled={loading}>
              {loading ? '✨ Creating your account...' : '🏫 Create School Account'}
            </button>
          </form>

          <p style={{ textAlign: 'center', fontSize: 12, color: '#94a3b8', marginTop: 16, marginBottom: 0 }}>
            Already have an account? <Link to="/login" style={{ color: '#45b7d1', fontWeight: 700 }}>Log in</Link>
          </p>
          <p style={{ textAlign: 'center', fontSize: 11, color: '#cbd5e1', marginTop: 8, marginBottom: 0 }}>
            No individual child data is collected. <Link to="/privacy" style={{ color: '#94a3b8' }}>Privacy Policy</Link>
          </p>
        </div>
      </div>
    </KidsShell>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/pages/SchoolRegisterPage.jsx
git commit -m "feat(ui): SchoolRegisterPage for school account signup"
```

---

## Task 11: Frontend — `KidsSongsListPage` (library view)

**Files:**
- Create: `web-beats/src/pages/kids/KidsSongsListPage.jsx`

- [ ] **Step 1: Create `KidsSongsListPage.jsx`**

This page shows the child's completed songs and stories in a simple, big-card grid with play buttons.

```jsx
import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { BACKEND_URL } from '../../brand';

export default function KidsSongsListPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [songs, setSongs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => {
    if (!token) return;
    fetch(`${BACKEND_URL}/songs`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        // songs endpoint returns { variants: [...] } or array
        const variants = Array.isArray(data) ? data : (data.variants || []);
        setSongs(variants.filter(v => v.status === 'complete').slice(0, 20));
      })
      .catch(() => setSongs([]))
      .finally(() => setLoading(false));
  }, [token]);

  const handlePlay = (song) => {
    if (!song.mp3_url) return;
    if (playingId === song.variant_id) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = song.mp3_url;
      audioRef.current.play().catch(() => {});
      setPlayingId(song.variant_id);
    }
  };

  return (
    <div style={{ flex: 1, padding: '16px 20px 80px', maxWidth: 600, margin: '0 auto', width: '100%' }}>
      <audio ref={audioRef} onEnded={() => setPlayingId(null)} style={{ display: 'none' }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20 }}>Your Songs &amp; Stories 🎵</h2>
        <button onClick={() => navigate('/kids')} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#45b7d1', fontWeight: 700, fontSize: 13, cursor: 'pointer' }}>
          ← Home
        </button>
      </div>

      {loading && <p style={{ color: '#64748b', textAlign: 'center' }}>Loading your songs... ✨</p>}

      {!loading && songs.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <div style={{ fontSize: 56, marginBottom: 12 }}>🎵</div>
          <p style={{ color: '#64748b', fontWeight: 600 }}>No songs yet! Go make your first one.</p>
          <button className="kids-btn kids-btn-primary" onClick={() => navigate('/kids')} style={{ marginTop: 16 }}>
            Make a Song!
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 16 }}>
        {songs.map(song => (
          <div key={song.variant_id} className="kids-card" style={{ padding: 0, overflow: 'hidden', cursor: 'pointer' }} onClick={() => handlePlay(song)}>
            {song.image_url
              ? <img src={song.image_url} alt={song.title} className="cover-ken-burns" style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover', display: 'block' }} />
              : <div style={{ width: '100%', aspectRatio: '1/1', background: 'linear-gradient(135deg, #fbd155, #ff6b9d)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40 }}>🎵</div>
            }
            <div style={{ padding: '10px 12px' }}>
              <div style={{ fontWeight: 800, fontSize: 13, color: '#1a2b4a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {song.title || 'My Song'}
              </div>
              <div style={{ fontSize: 22, textAlign: 'center', marginTop: 6 }}>
                {playingId === song.variant_id ? '⏸' : '▶️'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web-beats/src/pages/kids/KidsSongsListPage.jsx
git commit -m "feat(ui): KidsSongsListPage — big-card song library for kids"
```

---

## Task 12: Frontend — `App.jsx` routing + route guard

**Files:**
- Modify: `web-beats/src/App.jsx`
- Modify: `web-beats/src/components/ProtectedRoute.jsx`

- [ ] **Step 1: Add `SchoolRoute` to `ProtectedRoute.jsx`**

Add a second export to `ProtectedRoute.jsx` that redirects school accounts away from adult routes:

```jsx
// Add this after the existing ProtectedRoute export:

export function SchoolSafeRoute({ children }) {
  // Blocks school accounts from adult pages — redirects to /kids
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="spinner-page"><div className="spinner" /></div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (user.account_type === 'school') return <Navigate to="/kids" replace />;
  return children;
}
```

- [ ] **Step 2: Update `App.jsx` — add kids routes and school guard**

At the top of `App.jsx`, add these lazy imports after the existing ones:

```jsx
const KidsShellPage     = lazy(() => import('./components/KidsShell'));
const KidsHomePage      = lazy(() => import('./pages/kids/KidsHomePage'));
const KidsSongMode      = lazy(() => import('./pages/kids/KidsSongMode'));
const KidsStoryMode     = lazy(() => import('./pages/kids/KidsStoryMode'));
const KidsSongsListPage = lazy(() => import('./pages/kids/KidsSongsListPage'));
const SchoolRegisterPage = lazy(() => import('./pages/SchoolRegisterPage'));
```

Import `SchoolSafeRoute`:
```jsx
import { ProtectedRoute, SchoolSafeRoute } from './components/ProtectedRoute';
```

Add a `KidsProtectedRoute` component (inside `App.jsx`, before the `App` function):

```jsx
function KidsProtectedRoute({ children }) {
  // School accounts: always allow /kids
  // Standard accounts: must be logged in + have kidsMode session flag
  const { user, loading } = useAuth();
  const navigate = useNavigate ? undefined : null; // just use Navigate
  if (loading) return <div className="spinner-page"><div className="spinner" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.account_type === 'school') return children;
  // Standard account: check sessionStorage flag
  if (sessionStorage.getItem('kidsMode') !== '1') return <Navigate to="/songs" replace />;
  return children;
}
```

**Note:** `KidsProtectedRoute` needs to import `Navigate` from `react-router-dom` — it's already imported at the top of `App.jsx`.

In the `<Routes>` block, add before the closing `</Routes>`:

```jsx
            {/* ── Zeus Baby Beats ────────────────────────────────── */}
            <Route path="/schools" element={<SchoolRegisterPage />} />
            <Route
              path="/kids"
              element={
                <KidsProtectedRoute>
                  <KidsShellWrapper showExit />
                </KidsProtectedRoute>
              }
            >
              <Route index element={<KidsHomePage />} />
              <Route path="song" element={<KidsSongMode />} />
              <Route path="story" element={<KidsStoryMode />} />
              <Route path="songs" element={<KidsSongsListPage />} />
            </Route>
```

Add a `KidsShellWrapper` component above `AppInner` in `App.jsx`:

```jsx
import { Outlet, useNavigate } from 'react-router-dom';
import KidsShell from './components/KidsShell';
import ParentPINGate from './components/ParentPINGate';
import { useState } from 'react';

function KidsShellWrapper({ showExit }) {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [showPin, setShowPin] = useState(false);
  const isSchool = user?.account_type === 'school';

  const handleExit = () => {
    sessionStorage.removeItem('kidsMode');
    navigate('/songs');
  };

  return (
    <>
      <KidsShell showExitBtn={!isSchool} onExitClick={() => setShowPin(true)}>
        <Outlet />
      </KidsShell>
      {showPin && (
        <ParentPINGate
          token={token}
          action="exit"
          onSuccess={handleExit}
          onCancel={() => setShowPin(false)}
        />
      )}
    </>
  );
}
```

Wrap the `/songs` route (and other adult protected routes) with `SchoolSafeRoute` so school accounts can't visit them:

```jsx
            <Route
              path="/songs"
              element={
                <SchoolSafeRoute>
                  <SongsPage />
                </SchoolSafeRoute>
              }
            />
```

Do the same for `/billing`, `/mixer`, `/search`, `/playlists`, `/admin`.

- [ ] **Step 3: Commit**

```bash
git add web-beats/src/App.jsx web-beats/src/components/ProtectedRoute.jsx
git commit -m "feat(routing): /kids routes, KidsProtectedRoute, SchoolSafeRoute guard"
```

---

## Task 13: Frontend — SongsPage "Switch to Baby Beats" button

**Files:**
- Modify: `web-beats/src/pages/SongsPage.jsx`

- [ ] **Step 1: Add state for PIN gate and import at top of SongsPage**

SongsPage is a large self-contained file with inline imports. At the top of the component function, add:

```jsx
  const [showKidsPinGate, setShowKidsPinGate] = useState(false);
```

Find where `useState` imports are (they're inside the component or at top). The file uses dynamic imports — add the gate state alongside other boolean states (around line 1218).

- [ ] **Step 2: Add the switch button to the SongsPage header**

Search for the Kids Mode toggle section (around line 3036 — the yellow `isKidsMode` toggle button). Add this button BEFORE the existing kids mode toggle:

```jsx
                <button
                  onClick={() => setShowKidsPinGate(true)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '8px 16px', borderRadius: 20, cursor: 'pointer',
                    background: 'rgba(251,209,85,0.10)',
                    border: '1px solid rgba(251,209,85,0.5)',
                    color: '#fbbf24', fontSize: 13, fontWeight: 700,
                    transition: 'background 0.2s',
                  }}
                >
                  🧸 Zeus Baby Beats
                </button>
```

- [ ] **Step 3: Add PIN gate modal render + success handler**

Find the end of the SongsPage return JSX (just before the final closing `</div>`). Add:

```jsx
        {showKidsPinGate && token && (
          <React.Suspense fallback={null}>
            {/* Lazy-load ParentPINGate to avoid circular imports */}
            <KidsPinGateLoader
              token={token}
              onSuccess={() => {
                sessionStorage.setItem('kidsMode', '1');
                window.location.href = '/kids';
              }}
              onCancel={() => setShowKidsPinGate(false)}
            />
          </React.Suspense>
        )}
```

Add a small inline loader component near the top of the file (before `SongCard`):

```jsx
const LazyPINGate = React.lazy(() => import('../components/ParentPINGate'));
function KidsPinGateLoader({ token, onSuccess, onCancel }) {
  return <LazyPINGate token={token} action="enter" onSuccess={onSuccess} onCancel={onCancel} />;
}
```

- [ ] **Step 4: Commit**

```bash
git add web-beats/src/pages/SongsPage.jsx
git commit -m "feat(ui): add Zeus Baby Beats switch button to SongsPage"
```

---

## Task 14: Frontend — Privacy Policy children's data section

**Files:**
- Modify: `web-beats/src/pages/PrivacyPage.jsx`

- [ ] **Step 1: Find the PrivacyPage and add a children's data section**

Open `web-beats/src/pages/PrivacyPage.jsx`. Find the last `<section>` element before the closing `</main>`. Add this section after it:

```jsx
        <section className="content-section">
          <h2>Children's Data (Zeus Baby Beats)</h2>
          <p>Zeus Baby Beats is our child-safe music and storytelling mode designed for use in schools and family settings. We take children's privacy extremely seriously.</p>
          <p><strong>No individual child data is collected.</strong> Zeus Baby Beats school accounts are managed by adult teachers. Children do not have individual logins or personal profiles. All songs and stories created belong to the teacher's account, not to any individual child.</p>
          <p>School accounts store only: the teacher's name, school name, email address, and year group. No child names, ages, or personal identifiers are stored.</p>
          <p>Zeus Beats is not directed at children under 13 for individual account registration. School accounts are operated by adult teachers who are responsible for their class's use of the platform under their own consent.</p>
          <p>If you have questions about children's data, contact us at <a href="mailto:privacy@zeusbeats.com">privacy@zeusbeats.com</a>.</p>
        </section>
```

- [ ] **Step 2: Update "Last updated" date**

Find the "Last updated" line at the top of PrivacyPage and update it to reflect today: `6 June 2026`.

- [ ] **Step 3: Commit**

```bash
git add web-beats/src/pages/PrivacyPage.jsx
git commit -m "content(privacy): add Children's Data section for Zeus Baby Beats / GDPR-K"
```

---

## Task 15: Deploy

- [ ] **Step 1: Push all commits**

```bash
git push origin master
```

- [ ] **Step 2: Deploy backend**

```bash
cd C:\Users\Student\zeus-app
railway up --detach
```

Expected output: `Uploading... Build Logs: https://...`

- [ ] **Step 3: Verify in browser**

1. Navigate to `zeusbeats.com/schools` — school registration form should appear with kids theme
2. Register a test school account with a gmail (flagged) and a `.sch.uk` email (auto-verified)
3. After login, confirm redirect goes to `/kids` with the rainbow Baby Beats UI
4. Try navigating to `/songs` while logged in as school — should redirect back to `/kids`
5. Log in as a standard account, navigate to SongsPage — confirm "🧸 Zeus Baby Beats" button appears
6. Click the button — PIN gate modal should appear
7. Set a PIN in account settings first if needed, then enter PIN → lands on `/kids`
8. Click "Parent Exit" → PIN gate → returns to `/songs`

---

## Self-Review Notes

- **Spec coverage check:** Account types ✓, parent PIN ✓, school registration ✓, domain verification ✓, Telegram alert ✓, route guard ✓, kids UI components ✓, safety enforcement (explicit=False, mixer blocked) ✓, COPPA/privacy policy ✓, KidsSongsListPage ✓, Ziggy mascot ✓, kids.css theme ✓
- **Type/name consistency:** `account_type` used consistently across backend and frontend. `kids_pin_hash` in DB, `set_kids_pin`/`get_kids_pin_hash` in db.py. `/kids/pin/set` and `/kids/pin/verify` endpoints.
- **No placeholders:** All code blocks are complete. No "TBD" found.
- **One gap closed:** Added `KidsSongsListPage` (Task 11) — spec mentioned songs list but plan originally omitted it. Added.
- **`KidsShellWrapper` uses `Outlet`** from react-router-dom for nested route children — this is the correct pattern for the nested `/kids/*` routes.
