import { useEffect, useState } from 'react';
import { BACKEND_URL } from '../brand';
import { canCreateClips } from '../utils/clipsFeatureFlag';

/**
 * Whether the CURRENT user should see clip-creation UI (SongCard's "Create
 * Clip" button, the /clips/new page) — see clipsFeatureFlag.js for the pure
 * decision logic this wraps. Never gates the public /clips feed or
 * /clips/:id pages; those work for anyone with a link regardless.
 *
 * Purely additive: any fetch failure leaves the flag OFF, which still shows
 * clip creation to admins (client-side only — the real enforcement is
 * server-side in publish_clip/upload_clip_media; see the "Don't trust the
 * client" note there). A stale/failed fetch never breaks anything else.
 *
 * The flag is cached at module scope so every component using this hook on
 * one page load shares a single request, not one each — same reasoning as
 * useDiscoverBadge's per-mount fetch, just without the per-user cache key
 * since this flag isn't user-specific.
 */

let cachedFlag = null; // null = not yet fetched
let inFlight = null;

async function fetchClipsEnabledFlag() {
  if (cachedFlag !== null) return cachedFlag;
  if (!inFlight) {
    inFlight = fetch(`${BACKEND_URL}/api/clips/config`)
      .then((r) => (r.ok ? r.json() : { enabled: false }))
      .then((d) => {
        cachedFlag = Boolean(d?.enabled);
        return cachedFlag;
      })
      .catch(() => {
        cachedFlag = false;
        return false;
      })
      .finally(() => {
        inFlight = null;
      });
  }
  return inFlight;
}

export function useClipsEnabled(user) {
  const [flagEnabled, setFlagEnabled] = useState(cachedFlag ?? false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const enabled = await fetchClipsEnabledFlag();
      if (!cancelled) setFlagEnabled(enabled);
    })();
    return () => { cancelled = true; };
  }, []);

  return canCreateClips(flagEnabled, user);
}
