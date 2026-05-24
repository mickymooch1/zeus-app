# AI Playlist Builder + Discover For You — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an AI-curated playlist generator to PlaylistPage and a personalised "For You" tab to DiscoverPage.

**Architecture:** Feature 1 adds a Claude Haiku endpoint that reads the user's song library and selects matching variant_ids; Feature 3 adds a play-event table, a for-you recommendation endpoint (genre-based, using existing likes), and a tab bar in DiscoverPage.

**Tech Stack:** FastAPI + SQLite (backend), React/Vite (web-beats frontend), Anthropic Claude Haiku for AI curation.

---

## File map

| File | Change |
|---|---|
| `backend/db.py` | Add `get_user_songs_for_ai`, `log_play_event`, `get_for_you_songs`; add `song_play_events` table to schema |
| `backend/main.py` | Add `POST /api/playlists/ai-generate`, `POST /api/discover/play`, `GET /api/discover/for-you` |
| `web-beats/src/pages/PlaylistPage.jsx` | Add AI modal with chips |
| `web-beats/src/pages/DiscoverPage.jsx` | Add tab bar, For You fetch, play-event logging |

---

## FEATURE 1 — AI Playlist Builder

---

### Task 1 — DB helper: `get_user_songs_for_ai`

**Files:**
- Modify: `backend/db.py` (append after the last `def` in the file)

- [ ] **Step 1: Locate the end of db.py**

```bash
grep -n "^def " backend/db.py | tail -5
```

Note the last function name so you know where to append.

- [ ] **Step 2: Add the function**

Append to the bottom of `backend/db.py`:

```python
def get_user_songs_for_ai(db_path: pathlib.Path, user_id: str) -> list[dict]:
    """Return all completed songs for a user: variant_id, title, genre_tag, style_prompt."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            """SELECT sv.id AS variant_id,
                      l.title,
                      sv.genre_tag,
                      sv.style_prompt
               FROM song_variants sv
               JOIN lyrics l ON l.id = sv.lyric_id
               WHERE sv.user_id = ?
                 AND sv.status = 'complete'
                 AND sv.mp3_url IS NOT NULL
               ORDER BY sv.created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 3: Smoke-test the import**

```bash
cd backend && python -c "import db; print('db ok')"
```

Expected: `db ok`

---

### Task 2 — Backend endpoint: `POST /api/playlists/ai-generate`

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add Anthropic import**

Find the existing import block at the top of `main.py` (around lines 1–43). If `from anthropic import Anthropic` is not already there, add it after the other `from` imports:

```python
from anthropic import Anthropic
```

- [ ] **Step 2: Add the request model**

Find the block of Pydantic models near the playlist models (search for `class _CreatePlaylistRequest`). Add directly below it:

```python
class _AiPlaylistRequest(BaseModel):
    prompt: str
```

- [ ] **Step 3: Add the endpoint**

Find `@app.delete("/api/playlists/{playlist_id}")` (the last playlist endpoint). Add the new endpoint **immediately after** it (after its closing `return` line):

```python
@app.post("/api/playlists/ai-generate")
async def ai_generate_playlist(
    body: _AiPlaylistRequest,
    current_user=Depends(auth.get_current_user),
):
    """Generate a playlist using Claude Haiku based on a mood/vibe prompt."""
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt required")

    db_path = db.get_db_path()
    songs = db.get_user_songs_for_ai(db_path, current_user["id"])

    if len(songs) < 3:
        raise HTTPException(status_code=400, detail="Add more songs to use AI Playlist")

    song_lines = "\n".join(
        f"{i + 1}. variant_id={s['variant_id']}, "
        f"title=\"{s['title']}\", "
        f"genre={s['genre_tag'] or 'unknown'}"
        for i, s in enumerate(songs)
    )

    client = Anthropic()
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=(
                "You are a music curator. Given a numbered list of songs, select 10 to 15 "
                "that best match the user's mood or vibe. Return ONLY a valid JSON array of "
                "variant_id integers from the list. No explanation, no markdown, just the array. "
                "If fewer than 10 songs exist, return all of them."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f'Vibe: "{prompt}"\n\n'
                    f"Songs:\n{song_lines}\n\n"
                    "Return matching variant_ids as a JSON array."
                ),
            }],
        )
    except Exception as exc:
        log.exception("ai_generate_playlist: claude error")
        raise HTTPException(status_code=500, detail="AI service unavailable") from exc

    raw = response.content[0].text.strip()
    try:
        selected_ids = json.loads(raw)
        if not isinstance(selected_ids, list):
            raise ValueError("not a list")
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="No matching songs found for that vibe")

    valid_ids = {s["variant_id"] for s in songs}
    chosen = [vid for vid in selected_ids if isinstance(vid, int) and vid in valid_ids]

    if not chosen:
        raise HTTPException(status_code=400, detail="No matching songs found for that vibe")

    name = prompt[:60]
    playlist = db.create_playlist(db_path, current_user["id"], name)
    for vid in chosen:
        db.add_song_to_playlist(db_path, playlist["id"], vid)

    return {"playlist": playlist, "song_count": len(chosen)}
```

- [ ] **Step 4: Verify the server starts**

```bash
cd backend && python -c "import main; print('main ok')"
```

Expected: `main ok` with no import errors.

---

### Task 3 — Frontend: AI Playlist modal in PlaylistPage

**Files:**
- Modify: `web-beats/src/pages/PlaylistPage.jsx`

- [ ] **Step 1: Add state and chips constant**

In `PlaylistPage` (the default export function, starting at line 210), add these new state variables directly after the existing `const [creating, setCreating] = useState(false);` line:

```javascript
const [aiOpen, setAiOpen]         = useState(false);
const [aiPrompt, setAiPrompt]     = useState('');
const [aiLoading, setAiLoading]   = useState(false);
const [aiError, setAiError]       = useState('');
```

Add the chips constant at module level (below the `S` style object, above `ConfirmDialog`):

```javascript
const AI_CHIPS = [
  'Sunday morning chill', 'Hype workout', 'Late night drive',
  'Friday night out', 'Focus mode', 'Heartbreak vibes',
];
```

- [ ] **Step 2: Add the generate handler**

Add this function inside `PlaylistPage`, after `handleDeleted`:

```javascript
const handleAiGenerate = async () => {
  if (!aiPrompt.trim()) return;
  setAiLoading(true);
  setAiError('');
  try {
    const r = await fetch(`${BACKEND_URL}/api/playlists/ai-generate`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: aiPrompt.trim() }),
    });
    const data = await r.json();
    if (!r.ok) { setAiError(data.detail || 'Something went wrong'); return; }
    setPlaylists(prev => [data.playlist, ...prev]);
    setAiOpen(false);
    setAiPrompt('');
  } catch (_) {
    setAiError('Something went wrong. Try again.');
  } finally {
    setAiLoading(false);
  }
};
```

- [ ] **Step 3: Add the "✨ AI Playlist" button**

Find the existing `<form onSubmit={handleCreate}` block. Add the AI button **after** the `</form>` closing tag and before `{loading ? ...}`:

```jsx
<button
  type="button"
  onClick={() => { setAiOpen(true); setAiError(''); }}
  style={{
    background: 'linear-gradient(135deg,rgba(0,240,255,0.08),rgba(168,85,247,0.08))',
    border: '1px solid rgba(0,240,255,0.3)',
    borderRadius: 8, color: '#00f0ff', fontWeight: 700,
    fontSize: 13, padding: '8px 18px', cursor: 'pointer',
    marginBottom: 32, transition: 'all 0.15s',
  }}
>
  ✨ AI Playlist
</button>
```

- [ ] **Step 4: Add the modal**

Add this block inside the return JSX, immediately before the closing `</div>` of the outer page wrapper (`<div style={S.page}`):

```jsx
{aiOpen && (
  <div
    onClick={() => setAiOpen(false)}
    style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.78)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
    }}
  >
    <div
      onClick={e => e.stopPropagation()}
      style={{
        background: '#12121e', border: '1px solid rgba(0,240,255,0.25)',
        borderRadius: 16, padding: '28px 24px', maxWidth: 440, width: '100%',
      }}
    >
      {/* Heading */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, background: 'linear-gradient(90deg,#00f0ff,#a855f7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          ✨ AI Playlist Builder
        </h2>
        <button onClick={() => setAiOpen(false)} style={{ ...S.btn, padding: '4px 9px', fontSize: 15 }}>✕</button>
      </div>

      {/* Suggestion chips */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: 14 }}>
        {AI_CHIPS.map(chip => (
          <button
            key={chip}
            onClick={() => setAiPrompt(chip)}
            style={{
              background: aiPrompt === chip ? 'rgba(0,240,255,0.12)' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${aiPrompt === chip ? 'rgba(0,240,255,0.5)' : 'rgba(255,255,255,0.1)'}`,
              borderRadius: 20, color: aiPrompt === chip ? '#00f0ff' : '#94a3b8',
              fontSize: 12, padding: '5px 12px', cursor: 'pointer', transition: 'all 0.15s',
            }}
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Text input */}
      <input
        value={aiPrompt}
        onChange={e => setAiPrompt(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && !aiLoading && handleAiGenerate()}
        placeholder="Describe your mood or vibe..."
        style={{ ...S.input, width: '100%', marginBottom: 12, boxSizing: 'border-box' }}
        autoFocus
        maxLength={120}
      />

      {/* Error */}
      {aiError && (
        <p style={{ color: '#f87171', fontSize: 13, marginBottom: 10, margin: '0 0 10px' }}>{aiError}</p>
      )}

      {/* Generate button */}
      <button
        onClick={handleAiGenerate}
        disabled={aiLoading || !aiPrompt.trim()}
        style={{
          width: '100%', padding: '11px 0', marginTop: 4,
          background: 'linear-gradient(135deg,#7c3aed,#a855f7)', border: 'none',
          borderRadius: 8, color: '#fff', fontWeight: 700, fontSize: 14, cursor: 'pointer',
          opacity: aiLoading || !aiPrompt.trim() ? 0.55 : 1, transition: 'opacity 0.2s',
        }}
      >
        {aiLoading ? '✨ Claude is curating your playlist…' : '✨ Generate Playlist'}
      </button>
    </div>
  </div>
)}
```

- [ ] **Step 5: Verify the frontend builds**

```bash
cd web-beats && npm run build 2>&1 | tail -20
```

Expected: build completes with no errors.

- [ ] **Step 6: Commit and push Feature 1**

```bash
git add backend/db.py backend/main.py web-beats/src/pages/PlaylistPage.jsx
git commit -m "feat: AI Playlist Builder — Claude Haiku curates playlists from mood prompt"
git push origin master
```

---

## FEATURE 3 — Discover "For You" Tab

---

### Task 4 — DB schema + functions for play events and For You

**Files:**
- Modify: `backend/db.py`

- [ ] **Step 1: Add `song_play_events` table to schema**

Find the block where `playlists` and `playlist_songs` tables are created (search for `CREATE TABLE IF NOT EXISTS playlists`). Add the new table **immediately after** the `playlist_songs` CREATE statement:

```python
            """CREATE TABLE IF NOT EXISTS song_play_events (
                   id         INTEGER PRIMARY KEY AUTOINCREMENT,
                   variant_id INTEGER NOT NULL,
                   user_id    TEXT,
                   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
               )""",
            """CREATE INDEX IF NOT EXISTS idx_play_events_user
               ON song_play_events(user_id)""",
```

These lines go in whichever list/tuple holds the other `CREATE TABLE` statements. Look at how `playlist_songs` is added and follow the same pattern exactly.

- [ ] **Step 2: Add `log_play_event` function**

Append to the bottom of `backend/db.py`:

```python
def log_play_event(db_path: pathlib.Path, variant_id: int, user_id: str | None) -> None:
    """Record that a user started playing a discover song."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT INTO song_play_events (variant_id, user_id) VALUES (?, ?)",
            (variant_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 3: Add `get_for_you_songs` function**

Append to the bottom of `backend/db.py`:

```python
def get_for_you_songs(db_path: pathlib.Path, user_id: str, limit: int = 20) -> list[dict]:
    """Return public songs in genres the user has liked, ordered by like_count.
    Falls back to most-liked public songs if the user has no likes yet."""
    conn = _conn(db_path)
    try:
        # Genres this user has already liked
        liked_genre_rows = conn.execute(
            """SELECT DISTINCT sv.genre_tag
               FROM song_variant_likes svl
               JOIN song_variants sv ON sv.id = svl.variant_id
               WHERE svl.user_id = ? AND sv.genre_tag IS NOT NULL""",
            (user_id,),
        ).fetchall()
        liked_genres = [r[0] for r in liked_genre_rows]

        # Variant IDs the user has already liked (exclude from results)
        liked_id_rows = conn.execute(
            "SELECT variant_id FROM song_variant_likes WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        liked_ids = [r[0] for r in liked_id_rows]

        base_select = """SELECT sv.id AS variant_id,
                                sv.genre_tag,
                                sv.mp3_url,
                                sv.image_url  AS cover_url,
                                sv.music_video_url,
                                sv.duration_seconds,
                                l.title,
                                u.artist_name,
                                (SELECT COUNT(*) FROM song_variant_likes lk
                                 WHERE lk.variant_id = sv.id) AS like_count
                         FROM song_variants sv
                         JOIN lyrics l ON l.id = sv.lyric_id
                         JOIN users  u ON u.id = sv.user_id
                         WHERE sv.is_public = 1
                           AND sv.status = 'complete'
                           AND sv.mp3_url IS NOT NULL"""

        if liked_genres:
            genre_ph = ",".join("?" * len(liked_genres))
            if liked_ids:
                excl_ph = ",".join("?" * len(liked_ids))
                sql = (f"{base_select} AND sv.genre_tag IN ({genre_ph})"
                       f" AND sv.id NOT IN ({excl_ph})"
                       f" ORDER BY like_count DESC, sv.completed_at DESC LIMIT ?")
                params: list = liked_genres + liked_ids + [limit]
            else:
                sql = (f"{base_select} AND sv.genre_tag IN ({genre_ph})"
                       f" ORDER BY like_count DESC, sv.completed_at DESC LIMIT ?")
                params = liked_genres + [limit]
        else:
            sql = f"{base_select} ORDER BY like_count DESC, sv.completed_at DESC LIMIT ?"
            params = [limit]

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 4: Smoke-test**

```bash
cd backend && python -c "import db; print('db ok')"
```

Expected: `db ok`

---

### Task 5 — Backend endpoints: `POST /api/discover/play` + `GET /api/discover/for-you`

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add request model**

Find the Pydantic model block (near the other request models). Add:

```python
class _PlayEventRequest(BaseModel):
    variant_id: int
```

- [ ] **Step 2: Add `POST /api/discover/play`**

Find `@app.post("/api/discover/{variant_id}/like")` (around line 2849). Add the new endpoint **immediately before** it:

```python
@app.post("/api/discover/play", status_code=204)
async def log_discover_play(
    body: _PlayEventRequest,
    request: Request,
    current_user=Depends(auth.get_optional_user),
):
    """Fire-and-forget play event logging for the Discover feed."""
    user_id = current_user["id"] if current_user else None
    try:
        db.log_play_event(db.get_db_path(), body.variant_id, user_id)
    except Exception:
        pass  # Never fail the client for analytics
    return Response(status_code=204)
```

> **Note:** `auth.get_optional_user` may not exist yet. Check `backend/auth.py` for an optional auth dependency. If it doesn't exist, add this to `backend/auth.py`:
>
> ```python
> async def get_optional_user(authorization: str = Header(default="")):
>     """Like get_current_user but returns None instead of raising on missing/invalid token."""
>     if not authorization.startswith("Bearer "):
>         return None
>     token = authorization[7:]
>     try:
>         return verify_token(token)
>     except Exception:
>         return None
> ```
>
> If `verify_token` is named differently in auth.py, use the correct name.

- [ ] **Step 3: Add `GET /api/discover/for-you`**

Add this endpoint **after** `POST /api/discover/play` and **before** `POST /api/discover/{variant_id}/like`:

```python
@app.get("/api/discover/for-you")
async def discover_for_you(current_user=Depends(auth.get_current_user)):
    """Personalised feed: public songs in genres the user has liked, ordered by popularity."""
    songs = db.get_for_you_songs(db.get_db_path(), current_user["id"])
    return {"songs": songs, "page": 0, "count": len(songs)}
```

- [ ] **Step 4: Verify server starts**

```bash
cd backend && python -c "import main; print('main ok')"
```

Expected: `main ok`

---

### Task 6 — Frontend: DiscoverPage tab bar + For You + play logging

**Files:**
- Modify: `web-beats/src/pages/DiscoverPage.jsx`

- [ ] **Step 1: Add new state variables**

In `DiscoverPage` (the default export, at line 214), add these after the existing `const [signupPrompt, setSignupPrompt] = useState(false);`:

```javascript
const [activeTab, setActiveTab]         = useState('trending'); // 'trending' | 'for_you'
const [forYouSongs, setForYouSongs]     = useState([]);
const [forYouLoading, setForYouLoading] = useState(false);
const [forYouFetched, setForYouFetched] = useState(false);
```

Add a ref for the scroll container (after the existing refs block, around line 234):

```javascript
const scrollContainerRef = useRef(null);
```

- [ ] **Step 2: Add `activeSongs` computed value**

Add this line directly after all the `const [...]` state declarations and `const [...] = useRef(...)` lines, before `fetchPage`:

```javascript
const activeSongs = activeTab === 'for_you' ? forYouSongs : songs;
```

- [ ] **Step 3: Add `fetchForYou` callback**

Add this after the existing `fetchPage` useCallback (around line 260):

```javascript
const fetchForYou = useCallback(async () => {
  if (!token || forYouFetched) return;
  setForYouLoading(true);
  try {
    const r = await fetch(`${BACKEND_URL}/api/discover/for-you`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) return;
    const d = await r.json();
    const s = d.songs || [];
    setForYouSongs(s);
    setCounts(prev => {
      const n = { ...prev };
      s.forEach(x => { n[x.variant_id] = x.like_count; });
      return n;
    });
    setForYouFetched(true);
  } catch (e) {
    console.error('for-you:', e);
  } finally {
    setForYouLoading(false);
  }
}, [token, forYouFetched]);
```

- [ ] **Step 4: Add `handleTabChange`**

Add this after `fetchForYou`:

```javascript
const handleTabChange = (tab) => {
  if (tab === 'for_you' && !token) {
    setSignupPrompt(true);
    return;
  }
  setActiveTab(tab);
  activeRef.current = null;
  if (scrollContainerRef.current) scrollContainerRef.current.scrollTop = 0;
  if (tab === 'for_you' && !forYouFetched) fetchForYou();
};
```

- [ ] **Step 5: Update the IntersectionObserver**

Replace the entire IntersectionObserver `useEffect` block (currently `useEffect(() => { if (!songs.length) return; ... }, [songs, fetchPage]);`) with:

```javascript
useEffect(() => {
  if (!activeSongs.length) return;

  const obs = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      const idx = +entry.target.dataset.idx;
      const vid = videoRefs.current[idx];
      const aud = audioRefs.current[idx];

      if (entry.isIntersecting) {
        const prev = activeRef.current;
        if (prev !== null && prev !== idx) {
          videoRefs.current[prev]?.pause();
          const pa = audioRefs.current[prev];
          if (pa) { pa.pause(); pa.currentTime = 0; }
        }
        activeRef.current = idx;

        if (vid) { vid.muted = true; vid.play().catch(() => {}); }
        if (aud && !mutedRef.current) audioManager.play(aud, activeSongs[idx]?.variant_id);

        // Log play event (fire-and-forget)
        const song = activeSongs[idx];
        if (song) {
          fetch(`${BACKEND_URL}/api/discover/play`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({ variant_id: song.variant_id }),
          }).catch(() => {});
        }

        // Only infinite-scroll on the trending tab
        if (activeTab === 'trending' && idx >= activeSongs.length - 3) fetchPage();
      } else {
        if (vid) vid.pause();
        if (aud) { aud.pause(); aud.currentTime = 0; }
      }
    });
  }, { threshold: 0.65 });

  Object.values(slideRefs.current).forEach(el => { if (el) obs.observe(el); });
  return () => obs.disconnect();
}, [activeSongs, activeTab, fetchPage, token]);
```

- [ ] **Step 6: Add the tab bar to the JSX**

Find the fixed header `<div>` block (starts around line 354: `position: 'fixed', top: 0, ...`). Add the tab bar as a **new fixed `<div>`** immediately after that header div's closing `</div>`:

```jsx
{/* Tab bar */}
<div style={{
  position: 'fixed', top: 54, left: 0, right: 0, zIndex: 199,
  display: 'flex', justifyContent: 'center',
  pointerEvents: 'auto',
}}>
  {[['trending', '🔥 Trending'], ['for_you', '✨ For You']].map(([tab, label]) => (
    <button
      key={tab}
      onClick={() => handleTabChange(tab)}
      style={{
        background: 'none', border: 'none', borderBottom: `2px solid ${activeTab === tab ? CYAN : 'transparent'}`,
        color: activeTab === tab ? CYAN : 'rgba(255,255,255,0.45)',
        fontSize: 13, fontWeight: 700, padding: '6px 22px',
        cursor: 'pointer', transition: 'all 0.18s',
        textShadow: activeTab === tab ? `0 0 10px ${CYAN}88` : 'none',
      }}
    >
      {label}
    </button>
  ))}
</div>
```

- [ ] **Step 7: Update the scroll feed to use `activeSongs` and attach the ref**

Find the scroll feed container div (around line 411: `height: '100svh', overflowY: 'scroll', ...`). Add `ref={scrollContainerRef}` to it:

```jsx
<div
  ref={scrollContainerRef}
  style={{
    height: '100svh',
    overflowY: 'scroll',
    scrollSnapType: 'y mandatory',
    WebkitOverflowScrolling: 'touch',
  }}
>
```

- [ ] **Step 8: Replace `songs.map` with `activeSongs.map` in the render**

Find `{songs.map((song, idx) => (` in the scroll feed. Replace `songs.map` with `activeSongs.map`:

```jsx
{activeSongs.map((song, idx) => (
  <SongSlide
    key={song.variant_id}
    song={song}
    idx={idx}
    muted={muted}
    isLiked={liked.has(song.variant_id)}
    likeCount={counts[song.variant_id] || 0}
    isCopied={copied === song.variant_id}
    onLike={() => handleLike(song.variant_id)}
    onShare={() => handleShare(song.variant_id)}
    onSlideRef={el => { slideRefs.current[idx] = el; }}
    onVideoRef={el => { videoRefs.current[idx] = el; }}
    onAudioRef={el => { audioRefs.current[idx] = el; }}
  />
))}
```

- [ ] **Step 9: Add For You loading and empty states**

The existing loading spinner and empty-state divs at the bottom of the scroll feed are for the Trending tab. Add these **before** the existing `{loading && ...}` block:

```jsx
{/* For You loading state */}
{activeTab === 'for_you' && forYouLoading && (
  <div style={{
    height: '100svh', scrollSnapAlign: 'start',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  }}>
    <div style={{
      width: 36, height: 36, borderRadius: '50%',
      border: `3px solid ${CYAN}33`, borderTopColor: CYAN,
      animation: 'spin 0.8s linear infinite',
    }} />
  </div>
)}

{/* For You empty state */}
{activeTab === 'for_you' && !forYouLoading && forYouFetched && forYouSongs.length === 0 && (
  <div style={{
    height: '100svh', scrollSnapAlign: 'start',
    display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', gap: 16, padding: 32,
  }}>
    <p style={{ color: '#555', fontSize: 16, textAlign: 'center' }}>
      Like some songs on Trending to get personalised picks ❤️
    </p>
  </div>
)}
```

- [ ] **Step 10: Verify the frontend builds**

```bash
cd web-beats && npm run build 2>&1 | tail -20
```

Expected: build completes with no errors.

- [ ] **Step 11: Commit and push Feature 3**

```bash
git add backend/db.py backend/main.py web-beats/src/pages/DiscoverPage.jsx
git commit -m "feat: Discover For You tab — personalised recommendations + play event logging"
git push origin master
```

---

## Self-review checklist

- [x] `get_user_songs_for_ai` → Task 1 ✓
- [x] `POST /api/playlists/ai-generate` → Task 2 ✓
- [x] Suggestion chips (6) in modal → Task 3 ✓
- [x] `song_play_events` table + index → Task 4 ✓
- [x] `log_play_event` → Task 4 ✓
- [x] `get_for_you_songs` with liked-genre filtering + fallback → Task 4 ✓
- [x] `POST /api/discover/play` → Task 5 ✓
- [x] `GET /api/discover/for-you` → Task 5 ✓
- [x] Tab bar with 🔥 Trending / ✨ For You → Task 6 ✓
- [x] Play event fire-and-forget in IntersectionObserver → Task 6 ✓
- [x] Non-logged-in users → signup prompt when clicking For You → Task 6 ✓
- [x] Scroll reset + activeRef reset on tab change → Task 6 ✓
- [x] Infinite scroll gated to trending tab only → Task 6 ✓
- [x] Commit + push after each feature → Task 3 step 6, Task 6 step 11 ✓
