// A stable-per-browser id for logged-out clip views (POST /api/clips/:id/view
// requires anon_id when there's no Authorization header — see backend/clips.py's
// record_view). localStorage rather than sessionStorage: the backend's view-count
// dedup window is 24h, so the id needs to survive a tab close/reopen within that
// window the same way it would for a logged-in user's own id.
const KEY = 'zeus_clip_anon_id';

export function getClipAnonId() {
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    // localStorage unavailable — an id that only lives for this one call still
    // lets the view POST succeed; it just won't dedup against a future visit.
    return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}
