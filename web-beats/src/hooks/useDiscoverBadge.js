import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { BACKEND_URL } from '../brand';

/**
 * "New on Discover" badge count.
 *
 * The stored timestamp always comes from the SERVER (`server_time` on the
 * new-count response), never from the device clock. A client guessing "now"
 * would drift against the server and either miss songs or re-show seen ones.
 *
 * Keyed per user, so a shared device does not leak one person's read state to
 * the next. Signed out, there is no badge at all.
 *
 * Purely additive: every failure path leaves the count at 0. A badge is not
 * worth breaking the header over.
 */

export const discoverSeenKey = (userId) => `zeus_discover_seen_${userId}`;

/** Reseed the "last seen" marker from the server's clock. Never throws. */
export async function markDiscoverSeen(userId) {
  if (!userId) return;
  try {
    const r = await fetch(`${BACKEND_URL}/api/discover/new-count`);
    if (!r.ok) return;
    const d = await r.json();
    if (d?.server_time) localStorage.setItem(discoverSeenKey(userId), d.server_time);
  } catch {
    /* the badge simply stays until the next successful visit */
  }
}

export function useDiscoverBadge(user) {
  // Re-checked on navigation so the badge clears as soon as DiscoverPage has
  // reseeded, without needing shared state between the two components.
  const { pathname } = useLocation();
  const [count, setCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    // All setState lives inside the async body — a synchronous setState in an
    // effect body triggers a cascading re-render (react-hooks/set-state-in-effect).
    (async () => {
      const userId = user?.id;
      if (!userId) {
        if (!cancelled) setCount(0);   // signed out: drop any previous user's count
        return;
      }
      try {
        const since = localStorage.getItem(discoverSeenKey(userId));
        const url = since
          ? `${BACKEND_URL}/api/discover/new-count?since=${encodeURIComponent(since)}`
          : `${BACKEND_URL}/api/discover/new-count`;
        const r = await fetch(url);
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (cancelled) return;

        if (!since) {
          // First time on this device: seed the baseline and show nothing. Otherwise
          // a new user's first load would announce every song ever shared.
          if (d?.server_time) localStorage.setItem(discoverSeenKey(userId), d.server_time);
          setCount(0);
          return;
        }
        setCount(Number(d?.count) || 0);
      } catch {
        /* offline or endpoint unavailable — no badge, no error */
      }
    })();

    return () => { cancelled = true; };
  }, [user?.id, pathname]);

  return count;
}
