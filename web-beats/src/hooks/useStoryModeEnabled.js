import { useEffect, useState } from 'react';
import { BACKEND_URL } from '../brand';

// Kids Story Mode is disabled server-side while the ElevenLabs narration key is
// unpaid — /api/songs/generate 503s before any lyrics/ElevenLabs call regardless
// of what this hook returns. This only controls the UI treatment (Coming Soon
// vs the real flow); it defaults to false (Coming Soon) until the flag loads or
// if the request fails, matching the backend's fail-closed default.
export function useStoryModeEnabled() {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${BACKEND_URL}/api/feature-flags`)
      .then(res => res.ok ? res.json() : { story_mode_enabled: false })
      .then(data => { if (!cancelled) setEnabled(Boolean(data.story_mode_enabled)); })
      .catch(() => { if (!cancelled) setEnabled(false); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return { storyModeEnabled: enabled, loading };
}
