/**
 * Pure decision logic behind the CLIPS_ENABLED flag. Combines the server's
 * raw flag (GET /api/clips/config — not admin-aware) with the current user's
 * own is_admin, so admins can dog-food clip creation before it's promoted to
 * everyone. Only ever gates clip CREATION UI (SongCard's "Create Clip"
 * button, the /clips/new page) — never the public /clips feed or /clips/:id
 * pages, which work for anyone with a link regardless of this flag.
 */
export function canCreateClips(flagEnabled, user) {
  return Boolean(flagEnabled) || Boolean(user?.is_admin);
}
