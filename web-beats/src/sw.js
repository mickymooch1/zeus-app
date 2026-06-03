// Cache version is injected at build time — changes every deploy
const CACHE_VERSION = '__SW_VERSION__';
const CACHE_NAME = `zeus-static-${CACHE_VERSION}`;

// Only these paths are cached — everything else (API, auth, songs, billing…) goes straight to network
const CACHEABLE = /^\/(assets-beats|icons)\//;

self.addEventListener('install', () => {
  // Take over immediately — don't wait for old clients to close
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  // Delete every cache that isn't this version — clears stale assets from old deploys
  event.waitUntil(
    caches.keys()
      .then(names =>
        Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Only intercept same-origin GETs for static assets with content hashes
  if (
    request.method !== 'GET' ||
    url.origin !== self.location.origin ||
    !CACHEABLE.test(url.pathname)
  ) {
    return; // Fall through to network — API calls, HTML, manifest, etc. are never cached
  }

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
});
