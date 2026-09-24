// Derives the @handle shown under a clip/on a profile — lowercased, all
// whitespace stripped. Must match backend/clips.py's _normalize_handle
// exactly, since the backend's /api/clips/u/:handle lookup uses the same
// derivation to resolve a profile. Not a real per-account username system —
// see clips.get_user_public_profile's docstring for why handles aren't
// guaranteed unique.
export function deriveClipHandle(name) {
  return (name || '').trim().toLowerCase().replace(/\s+/g, '') || 'zeusbeats';
}
