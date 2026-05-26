# "Your Sound" Persona Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let paid users lock a finished song as their sonic DNA so every future generation automatically routes through CometAPI with that style persona.

**Architecture:** CometAPI is added as a parallel provider alongside Apiframe. Regular song generation stays on Apiframe unchanged. When a user has `sound_persona_id` set, the generate endpoint instead calls `cometapi.generate_with_persona()` and the callback comes in via a new `/webhooks/cometapi` handler. The persona is stored as three columns on the users table.

**Tech Stack:** FastAPI, SQLite (WAL mode, idempotent try/except migrations), CometAPI REST API (Bearer auth), React/Vite frontend with useAuth hook, requests library.

---

## File Map

| File | Change |
|---|---|
| `backend/db.py` | +3 migrations, +2 helpers: `set_sound_persona`, `clear_sound_persona` |
| `backend/cometapi.py` | **CREATE** — CometAPI client: `create_persona`, `generate_with_persona` |
| `backend/main.py` | +`import cometapi`, +`COMETAPI_WEBHOOK_URL`, +`POST /api/user/sound`, +`DELETE /api/user/sound`, modify `songs_generate` |
| `backend/webhooks.py` | +`POST /webhooks/cometapi` handler |
| `backend/tests/test_your_sound.py` | **CREATE** — integration tests for all backend changes |
| `web-beats/src/pages/SongsPage.jsx` | +soundPersona state, +`handleLockSound`, +`handleResetSound`, +Lock My Sound button on cards, +Your Sound Active pill |
| `web-beats/src/pages/BillingPage.jsx` | +Your Sound section |

---

## Task 1: DB migrations and helpers

**Files:**
- Modify: `backend/db.py` (migration list ending at line ~286, helpers after `clear_sound_persona` near line ~405)
- Create: `backend/tests/test_your_sound.py` (new test file)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_your_sound.py
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
os.environ.setdefault("APIFRAME_API_KEY", "test-apiframe-key")
os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_your_sound_storage")
os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/songs")
os.environ.setdefault("COMETAPI_API_KEY", "test-comet-key")
os.environ.setdefault("COMETAPI_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/cometapi")


def _make_db():
    import db
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = pathlib.Path(tmp.name)
    tmp.close()
    db.init_user_tables(db_path)
    return db_path


def _make_user(db_path):
    import db, uuid
    uid = str(uuid.uuid4())
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO users (id, email, password_hash, subscription_status, subscription_plan) VALUES (?, ?, ?, ?, ?)",
        (uid, f"{uid}@test.com", "hash", "active", "music_starter"),
    )
    conn.commit()
    conn.close()
    return uid


def test_set_and_clear_sound_persona():
    import db
    db_path = _make_db()
    uid = _make_user(db_path)
    db.set_sound_persona(db_path, uid, persona_id="uuid-test-123", variant_id=42, title="Midnight Drift")
    user = db.get_user_by_id(db_path, uid)
    assert user["sound_persona_id"] == "uuid-test-123"
    assert user["sound_persona_variant_id"] == 42
    assert user["sound_persona_title"] == "Midnight Drift"
    db.clear_sound_persona(db_path, uid)
    user = db.get_user_by_id(db_path, uid)
    assert user["sound_persona_id"] is None
    assert user["sound_persona_variant_id"] is None
    assert user["sound_persona_title"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend
python -m pytest tests/test_your_sound.py::test_set_and_clear_sound_persona -v
```
Expected: FAIL — `AttributeError: module 'db' has no attribute 'set_sound_persona'`

- [ ] **Step 3: Add three migrations to `backend/db.py`**

Find the migration list (ends around line 285 with `"ALTER TABLE song_variants ADD COLUMN stems_other_url TEXT"`). Add three lines immediately before the closing `]:`

```python
            "ALTER TABLE users ADD COLUMN sound_persona_id TEXT",
            "ALTER TABLE users ADD COLUMN sound_persona_variant_id INTEGER",
            "ALTER TABLE users ADD COLUMN sound_persona_title TEXT",
```

The full end of the migration list should look like:
```python
            "ALTER TABLE song_variants ADD COLUMN stems_bass_url TEXT",
            "ALTER TABLE song_variants ADD COLUMN stems_other_url TEXT",
            "ALTER TABLE users ADD COLUMN sound_persona_id TEXT",
            "ALTER TABLE users ADD COLUMN sound_persona_variant_id INTEGER",
            "ALTER TABLE users ADD COLUMN sound_persona_title TEXT",
        ]:
```

- [ ] **Step 4: Add two helpers to `backend/db.py`**

Add immediately after the `clear_sound_persona` helper (after the `update_user` function, around line 405):

```python
def set_sound_persona(
    db_path: pathlib.Path,
    user_id: str,
    *,
    persona_id: str,
    variant_id: int,
    title: str,
) -> None:
    """Save the user's CometAPI sound persona."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE users SET sound_persona_id = ?, sound_persona_variant_id = ?, sound_persona_title = ? WHERE id = ?",
            (persona_id, variant_id, title, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def clear_sound_persona(db_path: pathlib.Path, user_id: str) -> None:
    """Clear the user's sound persona."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE users SET sound_persona_id = NULL, sound_persona_variant_id = NULL, sound_persona_title = NULL WHERE id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run test to verify it passes**

```
cd backend
python -m pytest tests/test_your_sound.py::test_set_and_clear_sound_persona -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/db.py backend/tests/test_your_sound.py
git commit -m "feat: db migrations + set/clear_sound_persona helpers for Your Sound"
```

---

## Task 2: CometAPI client module

**Files:**
- Create: `backend/cometapi.py`

⚠️  **PRE-BUILD STEP (do before writing any code):** Sign into CometAPI at https://apidoc.cometapi.com and search for "persona". Determine which scenario applies:
- **Scenario A:** There is a dedicated `POST /suno/submit/persona` endpoint → use the implementation below as-is.
- **Scenario B:** No creation endpoint exists — persona_id is caller-supplied and `audio_url` is passed at generation time → update `create_persona()` to generate a local UUID (`str(uuid.uuid4())`) and store the mp3_url in a module-level dict, then pass `audio_url` in `generate_with_persona()` payload.

The rest of this task assumes Scenario A. If Scenario B, adjust `create_persona()` and add `"audio_url": stored_mp3_url` to `generate_with_persona()`'s payload.

- [ ] **Step 1: Write the failing test (add to `backend/tests/test_your_sound.py`)**

```python
from unittest.mock import patch, MagicMock


def test_generate_with_persona_builds_correct_payload():
    import cometapi
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 1, "data": "task-id-abc123"}
    mock_resp.raise_for_status = MagicMock()
    with patch("cometapi.requests.post", return_value=mock_resp) as mock_post:
        task_id = cometapi.generate_with_persona(
            variant_id=7,
            lyrics="verse 1 lyrics",
            style_prompt="uk grime, 140bpm",
            persona_id="uuid-persona-xyz",
            webhook_url="https://zeusaidesign.com/webhooks/cometapi?variant_id=7",
            extra_suno_params=None,
        )
    assert task_id == "task-id-abc123"
    call_json = mock_post.call_args.kwargs["json"]
    assert call_json["persona_id"] == "uuid-persona-xyz"
    assert call_json["task"] == "artist_consistency"
    assert "verse 1 lyrics" in call_json["prompt"]
    assert call_json["notify_hook"] == "https://zeusaidesign.com/webhooks/cometapi?variant_id=7"


def test_generate_with_persona_no_api_key_raises():
    import cometapi
    original = cometapi.COMETAPI_API_KEY
    cometapi.COMETAPI_API_KEY = ""
    try:
        try:
            cometapi.generate_with_persona(7, "lyrics", "style", "pid", "http://hook")
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "COMETAPI_API_KEY" in str(e)
    finally:
        cometapi.COMETAPI_API_KEY = original
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend
python -m pytest tests/test_your_sound.py::test_generate_with_persona_builds_correct_payload -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'cometapi'`

- [ ] **Step 3: Create `backend/cometapi.py`**

```python
"""
cometapi.py — CometAPI client for persona-based song generation.

Used ONLY when the user has a sound_persona_id set (Your Sound feature).
Regular song generation continues to use Apiframe via songs.py.

Environment variables:
    COMETAPI_API_KEY      — CometAPI bearer token (required for persona feature)
    COMETAPI_WEBHOOK_URL  — public URL for CometAPI callbacks
                            e.g. https://zeusaidesign.com/webhooks/cometapi
"""
import logging
import os

import requests

log = logging.getLogger("zeus.cometapi")

COMETAPI_BASE = "https://api.cometapi.com"
COMETAPI_API_KEY = os.environ.get("COMETAPI_API_KEY", "")
COMETAPI_WEBHOOK_URL = os.environ.get("COMETAPI_WEBHOOK_URL", "")

_MV_MAP = {
    "V4_5": "chirp-auk",
    "V4_5PLUS": "chirp-bluejay",
    "V5": "chirp-crow",
    "V5_5": "chirp-fenix",
}


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {COMETAPI_API_KEY}",
        "Content-Type": "application/json",
    }


def create_persona(mp3_url: str, title: str) -> str:
    """
    Create a CometAPI style persona from a finished song MP3.
    Returns the persona_id UUID string.

    ⚠️  VERIFY ENDPOINT BEFORE PRODUCTION USE:
    CometAPI's persona creation endpoint is behind their authenticated docs.
    Check https://apidoc.cometapi.com → search "persona" for the exact path.
    If the endpoint below is wrong, update the URL. The response parsing handles
    both {"data": "uuid"} and {"data": {"persona_id": "uuid"}} shapes.
    """
    if not COMETAPI_API_KEY:
        raise RuntimeError("COMETAPI_API_KEY not configured")
    resp = requests.post(
        f"{COMETAPI_BASE}/suno/submit/persona",
        headers=_headers(),
        json={"audio_url": mp3_url, "title": title},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    payload = data.get("data") or data
    if isinstance(payload, str):
        persona_id = payload
    elif isinstance(payload, dict):
        persona_id = payload.get("persona_id") or payload.get("id")
    else:
        persona_id = None
    if not persona_id:
        raise RuntimeError(f"CometAPI persona creation: no persona_id in response: {data!r}")
    log.info("create_persona: persona_id=%s title=%r mp3=%s", persona_id, title, mp3_url)
    return str(persona_id)


def generate_with_persona(
    variant_id: int,
    lyrics: str,
    style_prompt: str,
    persona_id: str,
    webhook_url: str,
    extra_suno_params: dict | None = None,
) -> str:
    """
    Submit a Suno generation to CometAPI with the user's style persona.
    Returns the CometAPI task_id string.
    Raises RuntimeError on API error; raises requests.HTTPError on HTTP failure.
    """
    if not COMETAPI_API_KEY:
        raise RuntimeError("COMETAPI_API_KEY not configured")

    mv = "chirp-fenix"
    vocal_gender = None
    if extra_suno_params:
        if "model_version" in extra_suno_params:
            mv = _MV_MAP.get(extra_suno_params["model_version"], "chirp-fenix")
        if "vocal_gender" in extra_suno_params:
            vocal_gender = extra_suno_params["vocal_gender"]

    body: dict = {
        "mv": mv,
        "prompt": lyrics,
        "tags": style_prompt[:200],
        "persona_id": persona_id,
        "task": "artist_consistency",
        "notify_hook": webhook_url,
        "generation_type": "TEXT",
    }
    if vocal_gender:
        body["vocal_gender"] = vocal_gender

    log.info(
        "generate_with_persona: variant_id=%d persona_id=%s mv=%s webhook=%s",
        variant_id, persona_id, mv, webhook_url,
    )
    resp = requests.post(
        f"{COMETAPI_BASE}/suno/submit/music",
        headers=_headers(),
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    payload = data.get("data") or data
    task_id = payload if isinstance(payload, str) else payload.get("task_id") if isinstance(payload, dict) else None
    if not task_id:
        raise RuntimeError(f"CometAPI generate_with_persona: no task_id in response: {data!r}")
    log.info("generate_with_persona: variant_id=%d → task_id=%s", variant_id, task_id)
    return str(task_id)
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend
python -m pytest tests/test_your_sound.py::test_generate_with_persona_builds_correct_payload tests/test_your_sound.py::test_generate_with_persona_no_api_key_raises -v
```
Expected: both PASS

- [ ] **Step 5: Commit**

```bash
git add backend/cometapi.py backend/tests/test_your_sound.py
git commit -m "feat: CometAPI client module — create_persona + generate_with_persona"
```

---

## Task 3: Backend API — POST/DELETE /api/user/sound

**Files:**
- Modify: `backend/main.py`

This task adds two endpoints and imports. No existing code is changed.

- [ ] **Step 1: Write the failing test (add to `backend/tests/test_your_sound.py`)**

```python
def test_sound_persona_endpoints_require_auth():
    from fastapi.testclient import TestClient
    import main as _main
    with TestClient(_main.app) as client:
        resp = client.post("/api/user/sound", json={"variant_id": 1})
        assert resp.status_code in {401, 403, 422}
        resp2 = client.delete("/api/user/sound")
        assert resp2.status_code in {401, 403}


def test_sound_persona_free_user_gets_402():
    import sqlite3, uuid, pathlib, db as _db
    from fastapi.testclient import TestClient
    import main as _main
    import auth as _auth

    db_path = _db.get_db_path()
    uid = str(uuid.uuid4())
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, subscription_status) VALUES (?, ?, ?, ?)",
        (uid, f"{uid}@test.com", "hash", "free"),
    )
    conn.commit()
    conn.close()
    token = _auth.create_token(uid, f"{uid}@test.com", is_admin=False)
    with TestClient(_main.app) as client:
        resp = client.post(
            "/api/user/sound",
            json={"variant_id": 999},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 402
    assert resp.json()["detail"] == "upgrade_required"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend
python -m pytest tests/test_your_sound.py::test_sound_persona_endpoints_require_auth tests/test_your_sound.py::test_sound_persona_free_user_gets_402 -v
```
Expected: first test FAIL (`404 not found`), second test FAIL (`404 not found`)

- [ ] **Step 3: Add import and constant to `backend/main.py`**

Find the block of module-level imports in `backend/main.py` (around line 30–50 where other module imports are). Add:

```python
import cometapi as _cometapi_mod
```

Find where env vars are read at module level (look for lines like `WEBHOOK_URL = os.environ.get(...)`, around line 1630–1640 in main.py). Add:

```python
COMETAPI_WEBHOOK_URL = os.environ.get("COMETAPI_WEBHOOK_URL", "")
```

- [ ] **Step 4: Add the `_SoundPersonaRequest` model and both endpoints to `backend/main.py`**

Add this block just before the `@app.post("/api/songs/variants/{variant_id}/stems")` endpoint (or anywhere in the songs/user section):

```python
class _SoundPersonaRequest(BaseModel):
    variant_id: int


@app.post("/api/user/sound")
async def set_sound_persona_endpoint(
    body: _SoundPersonaRequest,
    current_user: dict = Depends(auth.get_current_user),
):
    plan = current_user.get("subscription_plan")
    status = current_user.get("subscription_status", "free")
    is_admin = bool(current_user.get("is_admin", 0))
    if not is_admin and not (status == "active" and plan in billing.MUSIC_PLAN_KEYS):
        raise HTTPException(status_code=402, detail="upgrade_required")

    db_path = db.get_db_path()
    user_id = current_user["id"]

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT id, mp3_url FROM song_variants WHERE id = ? AND user_id = ?",
            (body.variant_id, user_id),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Song not found")
    mp3_url = row[1]
    if not mp3_url:
        raise HTTPException(status_code=400, detail="Song not yet complete — wait for generation to finish")

    conn = sqlite3.connect(str(db_path))
    try:
        title_row = conn.execute(
            "SELECT l.title FROM song_variants sv JOIN lyrics l ON l.id = sv.lyric_id WHERE sv.id = ?",
            (body.variant_id,),
        ).fetchone()
    finally:
        conn.close()
    song_title = title_row[0] if title_row and title_row[0] else f"Song #{body.variant_id}"

    if not _cometapi_mod.COMETAPI_API_KEY:
        raise HTTPException(status_code=503, detail="CometAPI not configured — contact support")

    try:
        persona_id = _cometapi_mod.create_persona(mp3_url, song_title)
    except Exception as exc:
        log.exception("set_sound_persona: CometAPI create_persona failed variant_id=%d", body.variant_id)
        raise HTTPException(status_code=502, detail=f"Persona creation failed: {exc}")

    db.set_sound_persona(db_path, user_id, persona_id=persona_id, variant_id=body.variant_id, title=song_title)
    log.info("set_sound_persona: user_id=%s persona_id=%s variant_id=%d", user_id, persona_id, body.variant_id)
    return {
        "sound_persona_id": persona_id,
        "sound_persona_title": song_title,
        "sound_persona_variant_id": body.variant_id,
    }


@app.delete("/api/user/sound")
async def clear_sound_persona_endpoint(current_user: dict = Depends(auth.get_current_user)):
    db_path = db.get_db_path()
    db.clear_sound_persona(db_path, current_user["id"])
    log.info("clear_sound_persona: user_id=%s", current_user["id"])
    return {"ok": True}
```

- [ ] **Step 5: Run tests to verify they pass**

```
cd backend
python -m pytest tests/test_your_sound.py::test_sound_persona_endpoints_require_auth tests/test_your_sound.py::test_sound_persona_free_user_gets_402 -v
```
Expected: both PASS

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_your_sound.py
git commit -m "feat: POST/DELETE /api/user/sound endpoints with paid-plan gate"
```

---

## Task 4: CometAPI webhook handler

**Files:**
- Modify: `backend/webhooks.py`

- [ ] **Step 1: Write the failing test (add to `backend/tests/test_your_sound.py`)**

```python
def test_cometapi_webhook_failed_status_marks_variant_failed():
    import sqlite3
    from fastapi.testclient import TestClient
    import main as _main
    import db as _db

    db_path = _db.get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO song_variants (id, lyric_id, user_id, style_prompt, genre_tag, status) VALUES (9901, 1, 'uid', 'style', 'hiphop', 'pending')"
    )
    conn.commit()
    conn.close()

    with TestClient(_main.app) as client:
        resp = client.post(
            "/webhooks/cometapi?variant_id=9901",
            json={"status": "FAILED", "data": []},
        )
    assert resp.status_code == 200
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT status FROM song_variants WHERE id = 9901").fetchone()
    conn.close()
    assert row and row[0] == "failed"


def test_cometapi_webhook_unexpected_status_returns_ok():
    from fastapi.testclient import TestClient
    import main as _main
    with TestClient(_main.app) as client:
        resp = client.post(
            "/webhooks/cometapi?variant_id=1",
            json={"status": "PROCESSING", "data": []},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "unexpected"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend
python -m pytest tests/test_your_sound.py::test_cometapi_webhook_failed_status_marks_variant_failed tests/test_your_sound.py::test_cometapi_webhook_unexpected_status_returns_ok -v
```
Expected: FAIL — `404 Not Found` (endpoint doesn't exist yet)

- [ ] **Step 3: Add the CometAPI webhook handler to `backend/webhooks.py`**

Add at the end of `backend/webhooks.py` (after the `apiframe_webhook` function):

```python
@router.post("/webhooks/cometapi")
async def cometapi_webhook(request: Request):
    """Callback handler for CometAPI persona-based song generations."""
    _raw_variant_id = request.query_params.get("variant_id", "MISSING")
    logger.info("COMETAPI WEBHOOK: variant_id=%s", _raw_variant_id)

    body = await request.json()

    variant_id = request.query_params.get("variant_id")
    if not variant_id:
        raise HTTPException(400, "Missing variant_id")
    try:
        variant_id = int(variant_id)
    except ValueError:
        raise HTTPException(400, "variant_id must be an integer")

    status = body.get("status", "")
    data = body.get("data", [])
    logger.info("CometAPI webhook: variant_id=%d status=%s", variant_id, status)

    if status == "FAILED":
        logger.error("CometAPI webhook FAILED for variant_id=%d body=%r", variant_id, body)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "status": "failed"}

    if status != "SUCCESS":
        logger.warning("CometAPI unexpected status=%r variant_id=%d", status, variant_id)
        return {"ok": True, "status": "unexpected"}

    # Atomic claim — prevent duplicate deliveries from processing twice
    _claim_conn = sqlite3.connect(DB_PATH)
    try:
        _claim_conn.execute("BEGIN IMMEDIATE")
        _claim_row = _claim_conn.execute(
            "SELECT status FROM song_variants WHERE id = ?", (variant_id,)
        ).fetchone()
        if _claim_row and _claim_row[0] in ("complete", "processing"):
            _claim_conn.execute("ROLLBACK")
            logger.info("CometAPI webhook: variant_id=%d already %s — ignoring duplicate", variant_id, _claim_row[0])
            return {"ok": True, "status": "already_" + _claim_row[0]}
        _claim_conn.execute("UPDATE song_variants SET status = 'processing' WHERE id = ?", (variant_id,))
        _claim_conn.execute("COMMIT")
    finally:
        _claim_conn.close()

    tracks = data if isinstance(data, list) else [data]
    if not tracks:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "status": "no_data"}

    track = tracks[0]
    audio_url = track.get("audio_url") or track.get("audioUrl")
    duration = round(float(track.get("duration", 0) or 0))

    if not audio_url:
        logger.error("CometAPI webhook: no audio_url in data: %r", track)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "status": "no_audio_url"}

    # Fetch variant metadata for cover art + animation
    conn = sqlite3.connect(DB_PATH)
    try:
        orig = conn.execute(
            "SELECT lyric_id, user_id, genre_tag, animate_cover FROM song_variants WHERE id = ?",
            (variant_id,),
        ).fetchone()
    finally:
        conn.close()

    animate_cover = bool(orig[3]) if orig and orig[3] is not None else True
    genre_tag = orig[2] if orig else None
    song_title = ""
    artist_name = ""
    if orig:
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute("SELECT title FROM lyrics WHERE id = ?", (orig[0],)).fetchone()
            song_title = row[0] if row and row[0] else ""
            ur = conn.execute("SELECT artist_name FROM users WHERE id = ?", (orig[1],)).fetchone()
            artist_name = (ur[0] or "") if ur else ""
        finally:
            conn.close()

    os.makedirs(STORAGE_PATH, exist_ok=True)
    logger.info("CometAPI webhook: downloading MP3 from %s", audio_url)
    dl = requests.get(audio_url, timeout=120)
    dl.raise_for_status()
    local_path = os.path.join(STORAGE_PATH, f"{variant_id}.mp3")
    with open(local_path, "wb") as fh:
        fh.write(dl.content)

    if os.path.getsize(local_path) < 100_000:
        logger.warning("CometAPI webhook: MP3 too small (%d bytes) variant_id=%d", os.path.getsize(local_path), variant_id)
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (variant_id,))
            conn.commit()
        finally:
            conn.close()
        return {"ok": True, "status": "small_file"}

    public_mp3_url = f"{PUBLIC_BASE_URL}/{variant_id}.mp3"

    # Generate cover art via Flux (same as Apiframe path)
    flux_cover = _generate_flux_cover(variant_id, genre_tag, song_title, artist_name)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """UPDATE song_variants
               SET mp3_url = ?, image_url = ?, duration_seconds = ?,
                   status = 'complete', take_number = 1, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (public_mp3_url, flux_cover, duration, variant_id),
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("CometAPI webhook: complete variant_id=%d mp3=%s", variant_id, public_mp3_url)

    # Trigger Kling animation if enabled and resources available
    if animate_cover and flux_cover and duration and FAL_API_KEY:
        logger.info("CometAPI webhook: starting Kling animation for variant_id=%d", variant_id)
        threading.Thread(
            target=_kling_pipeline,
            args=(variant_id, flux_cover, local_path, duration, genre_tag),
            daemon=True,
        ).start()
    else:
        logger.info(
            "CometAPI webhook: Kling skipped animate_cover=%s flux=%s duration=%s fal_key=%s",
            animate_cover, bool(flux_cover), duration, bool(FAL_API_KEY),
        )

    return {"ok": True, "status": "complete"}
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend
python -m pytest tests/test_your_sound.py::test_cometapi_webhook_failed_status_marks_variant_failed tests/test_your_sound.py::test_cometapi_webhook_unexpected_status_returns_ok -v
```
Expected: both PASS

- [ ] **Step 5: Commit**

```bash
git add backend/webhooks.py backend/tests/test_your_sound.py
git commit -m "feat: POST /webhooks/cometapi handler for persona-based song callbacks"
```

---

## Task 5: Song generation branching — persona path

**Files:**
- Modify: `backend/main.py`

When `sound_persona_id` is set, `songs_generate` generates ONE variant via CometAPI with the persona instead of calling Apiframe. The Apiframe path is completely unchanged for users without a persona.

- [ ] **Step 1: Write the failing test (add to `backend/tests/test_your_sound.py`)**

```python
def test_songs_generate_uses_cometapi_when_persona_set():
    import sqlite3, uuid, pathlib
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient
    import main as _main
    import db as _db
    import auth as _auth

    db_path = _db.get_db_path()
    uid = str(uuid.uuid4())
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, subscription_status, subscription_plan, sound_persona_id, sound_persona_title) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uid, f"{uid}@test.com", "hash", "active", "music_starter", "persona-uuid-test", "Test Song"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO song_credits (user_id, balance, monthly_allowance) VALUES (?, 5, 25)",
        (uid,),
    )
    conn.commit()
    conn.close()

    token = _auth.create_token(uid, f"{uid}@test.com", is_admin=False)
    mock_task_id = "comet-task-999"

    with patch("cometapi.generate_with_persona", return_value=mock_task_id) as mock_gen, \
         patch("lyrics.generate_lyrics", return_value={"lyric_id": 1, "lyrics": "test lyrics", "title": "Test"}):
        with TestClient(_main.app) as client:
            resp = client.post(
                "/api/songs/generate",
                json={"brief": "test song", "genres": ["hiphop"]},
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["variants"]) == 1
    assert data["variants"][0]["job_id"] == mock_task_id
    mock_gen.assert_called_once()
    call_kwargs = mock_gen.call_args.kwargs
    assert call_kwargs["persona_id"] == "persona-uuid-test"
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend
python -m pytest tests/test_your_sound.py::test_songs_generate_uses_cometapi_when_persona_set -v
```
Expected: FAIL — `mock_gen.assert_called_once()` fails (Apiframe path is taken instead)

- [ ] **Step 3: Add persona branching to `songs_generate` in `backend/main.py`**

In `backend/main.py`, find the `songs_generate` function. Locate this block:

```python
    log.info(
        "songs_generate: submitting to Apiframe user_id=%s lyric_id=%s genres=%r "
```

Add the persona branch **immediately before** that log line (after `is_admin = bool(...)` is set):

```python
    # ── CometAPI persona path ──────────────────────────────────────────────────
    # When the user has a sound persona set, route through CometAPI instead.
    # Generates exactly ONE variant using the first selected genre + their persona.
    _user_row_for_persona = db.get_user_by_id(db_path, user_id)
    _persona_id = _user_row_for_persona.get("sound_persona_id") if _user_row_for_persona else None

    if _persona_id:
        from song_genres import GENRE_PRESETS as _GP
        _p_genre = body.genres[0]
        _p_style = _GP.get(_p_genre, "")
        if tempo_suffix:
            _p_style = f"{_p_style}, {tempo_suffix}"

        _p_conn = sqlite3.connect(str(db_path))
        try:
            _p_cur = _p_conn.cursor()
            if not is_admin:
                _p_cur.execute("SELECT balance FROM song_credits WHERE user_id = ?", (user_id,))
                _p_row = _p_cur.fetchone()
                if not _p_row or _p_row[0] < 1:
                    raise HTTPException(status_code=402, detail="No song credits available. Top up to continue.")
                _p_cur.execute("UPDATE song_credits SET balance = balance - 1 WHERE user_id = ?", (user_id,))
            _p_cur.execute(
                "INSERT INTO song_variants (lyric_id, user_id, style_prompt, genre_tag, status, take_number, animate_cover) VALUES (?, ?, ?, ?, 'pending', 1, ?)",
                (lyric_id, user_id, _p_style, _p_genre, 1 if body.animate_cover else 0),
            )
            _p_variant_id = _p_cur.lastrowid
            _p_conn.commit()
        finally:
            _p_conn.close()

        _p_webhook = f"{COMETAPI_WEBHOOK_URL}?variant_id={_p_variant_id}"
        try:
            _p_task_id = _cometapi_mod.generate_with_persona(
                variant_id=_p_variant_id,
                lyrics=lyric_result["lyrics"],
                style_prompt=_p_style,
                persona_id=_persona_id,
                webhook_url=_p_webhook,
                extra_suno_params=extra_suno_params or None,
            )
        except Exception as exc:
            if not is_admin:
                _ref = sqlite3.connect(str(db_path))
                try:
                    _ref.execute("UPDATE song_credits SET balance = balance + 1 WHERE user_id = ?", (user_id,))
                    _ref.execute("UPDATE song_variants SET status = 'failed' WHERE id = ?", (_p_variant_id,))
                    _ref.commit()
                finally:
                    _ref.close()
            log.exception("songs_generate: CometAPI persona generation failed user_id=%s", user_id)
            raise HTTPException(status_code=502, detail=f"CometAPI generation failed: {exc}")

        _tj = sqlite3.connect(str(db_path))
        try:
            _tj.execute("UPDATE song_variants SET provider_job_id = ? WHERE id = ?", (_p_task_id, _p_variant_id))
            _tj.commit()
        finally:
            _tj.close()

        log.info("songs_generate: CometAPI persona ok user_id=%s variant_id=%d task_id=%s", user_id, _p_variant_id, _p_task_id)
        return {
            "lyric_id": lyric_id,
            "title": lyric_result["title"],
            "variants": [{"genre": _p_genre, "variant_id": _p_variant_id, "job_id": _p_task_id, "status": "generating"}],
        }
    # ── End CometAPI persona path ──────────────────────────────────────────────
```

- [ ] **Step 4: Run all backend tests**

```
cd backend
python -m pytest tests/test_your_sound.py -v
```
Expected: all tests PASS

- [ ] **Step 5: Run existing test suite to check for regressions**

```
cd backend
python -m pytest tests/ -v --ignore=tests/test_your_sound.py
```
Expected: all existing tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_your_sound.py
git commit -m "feat: persona branch in songs_generate — routes to CometAPI when sound_persona_id set"
```

---

## Task 6: Frontend — SongsPage (Lock My Sound + pill)

**Files:**
- Modify: `web-beats/src/pages/SongsPage.jsx`

Two UI additions:
1. "Lock My Sound 🔒" button on each completed song card
2. "🔒 Your Sound Active" pill with × button near the Generate button

- [ ] **Step 1: Add soundPersona state and handlers to SongsPage**

Find the state declarations near line 972 in `SongsPage.jsx` (after `const { token, user } = useAuth();`). Add:

```jsx
  const [soundPersona, setSoundPersona] = useState(null);
  const [lockToast, setLockToast] = useState('');
  const lockToastTimer = useRef(null);
```

Find the `useEffect` that fetches credits on mount (searches for `fetchCredits`). After the credits fetch, add an effect to initialise soundPersona from the user object:

```jsx
  useEffect(() => {
    if (!user) return;
    setSoundPersona(
      user.sound_persona_id
        ? {
            sound_persona_id: user.sound_persona_id,
            sound_persona_title: user.sound_persona_title,
            sound_persona_variant_id: user.sound_persona_variant_id,
          }
        : null
    );
  }, [user]);
```

Add the two handlers after the existing `handleGetStems` handler:

```jsx
  const handleLockSound = async (variant, title) => {
    const isPaid =
      user?.is_admin ||
      (user?.subscription_status === 'active' &&
        ['music_starter', 'music_pro', 'music_agency'].includes(user?.subscription_plan));
    if (!isPaid) {
      clearTimeout(lockToastTimer.current);
      setLockToast('Upgrade to Music Starter to unlock Your Sound 🔒');
      lockToastTimer.current = setTimeout(() => setLockToast(''), 4000);
      return;
    }
    try {
      const resp = await fetch(`${BACKEND_URL}/api/user/sound`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ variant_id: variant.variant_id }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        if (data.detail === 'upgrade_required') {
          clearTimeout(lockToastTimer.current);
          setLockToast('Upgrade to Music Starter to unlock Your Sound 🔒');
          lockToastTimer.current = setTimeout(() => setLockToast(''), 4000);
          return;
        }
        throw new Error(data.detail || 'Failed to lock sound');
      }
      setSoundPersona(data);
      clearTimeout(lockToastTimer.current);
      setLockToast(`Your Sound locked to "${data.sound_persona_title}" 🔒`);
      lockToastTimer.current = setTimeout(() => setLockToast(''), 4000);
    } catch (err) {
      clearTimeout(lockToastTimer.current);
      setLockToast(`Error: ${err.message}`);
      lockToastTimer.current = setTimeout(() => setLockToast(''), 4000);
    }
  };

  const handleResetSound = async () => {
    try {
      await fetch(`${BACKEND_URL}/api/user/sound`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setSoundPersona(null);
    } catch (err) {
      console.error('Failed to reset sound:', err);
    }
  };
```

- [ ] **Step 2: Pass new props to SongCard (both render sites)**

Find the first `<SongCard` render site (around line 2640). Add two new props:

```jsx
                      soundPersonaVariantId={soundPersona?.sound_persona_variant_id ?? null}
                      onLockSound={handleLockSound}
```

Find the second `<SongCard` render site (around line 2732). Add the same two props:

```jsx
                    soundPersonaVariantId={soundPersona?.sound_persona_variant_id ?? null}
                    onLockSound={handleLockSound}
```

- [ ] **Step 3: Add "Lock My Sound" button to the SongCard component**

In the `SongCard` function signature (around line 280), add `soundPersonaVariantId` and `onLockSound` to the destructured props:

```jsx
const SongCard = memo(function SongCard({
  variant, title, artistName, activeWsRef,
  canYouTube, ytConnected, ytStatus: ytSt, ytUrl, ytError, onYouTubeClick,
  canDid, didSt, videoUrl, onAvatarClick, videoCredits, didPlanOk, isAdmin,
  isFavourite, onToggleFavourite, isFreeTier, animateCover,
  isPublic, onShareToggle,
  playlists, onAddToPlaylist,
  premiumCredits, stemsData: stemsProp, onGetStems, onOpenCover,
  soundPersonaVariantId, onLockSound,  // NEW
}) {
```

Find the stems action buttons area (the section that renders after `{!isFailed && variant.mp3_url && (`). After the "Cover This Song" button block and before the stems panel block, add the "Lock My Sound" button:

```jsx
            {/* Lock My Sound */}
            <div style={{ marginTop: 6 }}>
              {soundPersonaVariantId === variant.variant_id ? (
                <div style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(0,240,255,0.3)', background: 'rgba(0,240,255,0.06)', color: '#00f0ff', fontSize: 12, fontWeight: 700, textAlign: 'center' }}>
                  ✓ Your Sound
                </div>
              ) : (
                <button
                  onClick={() => onLockSound(variant, title)}
                  style={{ width: '100%', padding: '8px 0', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.7)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
                >
                  🔒 Lock My Sound
                </button>
              )}
            </div>
```

- [ ] **Step 4: Add "Your Sound Active" pill near the Generate button**

Find the Generate button in the JSX (around line 2524 — the `<button onClick={handleGenerate}` block). Add the pill **immediately before** the Generate button:

```jsx
            {soundPersona && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, padding: '7px 12px', borderRadius: 8, background: 'rgba(0,240,255,0.07)', border: '1px solid rgba(0,240,255,0.25)' }}>
                <span style={{ flex: 1, fontSize: 12, color: '#00f0ff', fontWeight: 600 }}>
                  🔒 Your Sound Active — {soundPersona.sound_persona_title}
                </span>
                <button
                  onClick={handleResetSound}
                  aria-label="Reset Your Sound"
                  style={{ background: 'none', border: 'none', color: 'rgba(0,240,255,0.6)', fontSize: 16, cursor: 'pointer', lineHeight: 1, padding: '2px 4px', flexShrink: 0 }}
                >
                  ×
                </button>
              </div>
            )}
```

- [ ] **Step 5: Add lockToast notification**

Find the coverToast notification block (the fixed-bottom toast at the bottom of the JSX). Add the lockToast notification nearby:

```jsx
        {lockToast && (
          <div style={{ position: 'fixed', bottom: 90, left: '50%', transform: 'translateX(-50%)', background: 'rgba(0,0,0,0.92)', border: '1px solid rgba(0,240,255,0.35)', borderRadius: 10, padding: '12px 22px', color: '#00f0ff', fontSize: 13, fontWeight: 600, zIndex: 9999, whiteSpace: 'nowrap', boxShadow: '0 4px 24px rgba(0,240,255,0.12)' }}>
            {lockToast}
          </div>
        )}
```

- [ ] **Step 6: Verify frontend builds without errors**

```
cd web-beats
npm run build 2>&1 | tail -20
```
Expected: build completes with no errors (warnings are OK)

- [ ] **Step 7: Commit**

```bash
git add web-beats/src/pages/SongsPage.jsx
git commit -m "feat: Lock My Sound button on song cards + Your Sound Active pill with reset"
```

---

## Task 7: Frontend — BillingPage Your Sound section

**Files:**
- Modify: `web-beats/src/pages/BillingPage.jsx`

- [ ] **Step 1: Add soundPersona state and handlers to BillingPage**

In `BillingPage.jsx`, find the state declarations (around line 39). Add:

```jsx
  const [soundPersona, setSoundPersona]     = useState(null);
  const [soundResetLoading, setSoundResetLoading] = useState(false);
```

Find the `useEffect` that fetches billing status (around line 66). After it, add an effect to read persona from user:

```jsx
  useEffect(() => {
    if (!user) return;
    setSoundPersona(
      user.sound_persona_id
        ? {
            sound_persona_id: user.sound_persona_id,
            sound_persona_title: user.sound_persona_title,
          }
        : null
    );
  }, [user]);
```

Add the reset handler after the effect:

```jsx
  const handleResetSound = async () => {
    setSoundResetLoading(true);
    try {
      await fetch(`${BACKEND_URL}/api/user/sound`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setSoundPersona(null);
    } catch (err) {
      console.error('Failed to reset sound:', err);
    } finally {
      setSoundResetLoading(false);
    }
  };
```

- [ ] **Step 2: Add the "Your Sound" section to the BillingPage JSX**

Find the return JSX in BillingPage (the `<div className="billing-page">` block, around line 259). Find the first `<div className="billing-card">` (the current plan card). Add the Your Sound section **immediately before** that card:

```jsx
        {/* ── Your Sound ─────────────────────────────────────────────────── */}
        <div className="billing-card" style={{ marginBottom: 20 }}>
          <div className="billing-card-header" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: '1.1rem' }}>🎧</span>
            <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#00f0ff' }}>Your Sound</h2>
          </div>
          {(() => {
            const isPaid =
              user?.is_admin ||
              (user?.subscription_status === 'active' &&
                ['music_starter', 'music_pro', 'music_agency'].includes(user?.subscription_plan));
            if (!isPaid) {
              return (
                <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 14, margin: '12px 0 0' }}>
                  Upgrade to Music Starter to lock your sonic DNA — every future song will sound like you.
                </p>
              );
            }
            if (soundPersona) {
              return (
                <div style={{ marginTop: 14 }}>
                  <p style={{ margin: '0 0 14px', fontSize: 14, color: 'rgba(255,255,255,0.75)' }}>
                    🔒 Locked to: <strong style={{ color: '#fff' }}>{soundPersona.sound_persona_title}</strong>
                  </p>
                  <p style={{ margin: '0 0 16px', fontSize: 13, color: 'rgba(255,255,255,0.45)' }}>
                    All future songs will carry your sonic DNA — even across different genres.
                  </p>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <Link
                      to="/songs"
                      style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid rgba(0,240,255,0.4)', background: 'rgba(0,240,255,0.06)', color: '#00f0ff', fontSize: 13, fontWeight: 600, textDecoration: 'none', display: 'inline-block' }}
                    >
                      Change Sound
                    </Link>
                    <button
                      onClick={handleResetSound}
                      disabled={soundResetLoading}
                      style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.6)', fontSize: 13, fontWeight: 600, cursor: soundResetLoading ? 'default' : 'pointer' }}
                    >
                      {soundResetLoading ? 'Resetting…' : 'Reset'}
                    </button>
                  </div>
                </div>
              );
            }
            return (
              <div style={{ marginTop: 14 }}>
                <p style={{ margin: '0 0 8px', fontSize: 14, color: 'rgba(255,255,255,0.45)' }}>
                  Not set — go to a song you love and click "Lock My Sound" to save your sonic DNA.
                </p>
                <Link
                  to="/songs"
                  style={{ color: '#00f0ff', fontSize: 13, fontWeight: 600, textDecoration: 'none' }}
                >
                  → Go to My Songs
                </Link>
              </div>
            );
          })()}
        </div>
```

- [ ] **Step 3: Verify frontend builds without errors**

```
cd web-beats
npm run build 2>&1 | tail -20
```
Expected: build completes with no errors

- [ ] **Step 4: Commit and push**

```bash
git add web-beats/src/pages/BillingPage.jsx
git commit -m "feat: Your Sound section on BillingPage with lock status, Change and Reset"
git push origin master
```

---

## Post-implementation checklist

After all tasks are merged and pushed:

- [ ] Add `COMETAPI_API_KEY` and `COMETAPI_WEBHOOK_URL` to Railway environment variables
- [ ] Verify CometAPI persona creation endpoint (see Task 2 ⚠️ note) — update `create_persona()` if the endpoint URL is different
- [ ] Test end-to-end: lock a song → generate a new one → confirm it arrives via `/webhooks/cometapi` and appears in the library
- [ ] Check Railway logs for `"CometAPI webhook: complete"` and `"create_persona:"` log lines
