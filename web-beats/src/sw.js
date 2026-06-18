// Cache version is injected at build time — changes every deploy
const CACHE_VERSION = '__SW_VERSION__';
const CACHE_NAME = `zeus-static-${CACHE_VERSION}`;

// Only these paths are cached as hashed static assets
const CACHEABLE = /^\/(assets-beats|icons)\//;

self.addEventListener('install', event => {
  // Take over immediately — don't wait for old clients to close
  self.skipWaiting();
  // Pre-cache the app shell (index.html) so the app opens when offline.
  // The .catch() prevents a network failure during install from blocking SW activation —
  // the shell will be cached on the user's first online visit instead.
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      cache.add('/').catch(() => {})
    )
  );
});

self.addEventListener('activate', event => {
  // Delete every cache that isn't this version — clears stale assets from old deploys
  event.waitUntil(
    caches.keys()
      .then(names =>
        Promise.all(names.filter(n => n !== CACHE_NAME && !n.startsWith('zeus-audio-')).map(n => caches.delete(n)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }

  // Navigation requests (full-page loads for any SPA route) — network first.
  // When online: fetch fresh HTML and refresh the shell cache for next offline visit.
  // When offline: serve the cached shell — React Router handles routing client-side.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            // Always store under '/' so any SPA route resolves to the same shell
            caches.open(CACHE_NAME).then(cache => cache.put('/', response.clone()));
          }
          return response;
        })
        .catch(() => caches.match('/'))
    );
    return;
  }

  // Hashed static assets (JS/CSS bundles, icons) — cache first
  if (CACHEABLE.test(url.pathname)) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;

        return fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // Everything else (API, audio, auth, billing) — fall through to network
});
