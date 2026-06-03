import { useEffect, useState } from 'react';

export function useSWUpdate() {
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;

    // Capture whether a SW is already controlling this page *before* registering.
    // If true, any subsequent controllerchange is an update (not first install).
    const hadController = Boolean(navigator.serviceWorker.controller);

    let registration;
    navigator.serviceWorker
      .register('/sw.js')
      .then(reg => {
        registration = reg;
        // Poll for updates every 30 minutes so long-running tabs pick up deploys
        const timer = setInterval(() => reg.update().catch(() => {}), 30 * 60 * 1000);
        // Clean up timer when component unmounts
        reg._zbUpdateTimer = timer;
      })
      .catch(err => console.warn('[SW] registration failed:', err));

    const handleControllerChange = () => {
      if (!hadController) {
        // First-time install — SW is taking over from nothing. No reload needed.
        return;
      }
      // An update replaced the old SW — show toast then reload to pick up new assets
      setUpdating(true);
      setTimeout(() => window.location.reload(), 1500);
    };

    navigator.serviceWorker.addEventListener('controllerchange', handleControllerChange);

    return () => {
      navigator.serviceWorker.removeEventListener('controllerchange', handleControllerChange);
      if (registration?._zbUpdateTimer) clearInterval(registration._zbUpdateTimer);
    };
  }, []);

  return { updating };
}
