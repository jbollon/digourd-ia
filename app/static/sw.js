const CACHE_NAME = "digourd-v1";

// App shell: static assets to cache on install
const PRECACHE = [
  "/",
  "/static/tailwind.css",
  "/static/style.css",
  "/static/app.js",
  "/static/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png",
];

// ── Install: pre-cache the app shell ──────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

// ── Activate: delete old caches ───────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: cache-first for static, network-first for API ──────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API calls → network only (no caching)
  if (url.pathname.startsWith("/chat")) {
    return; // let browser handle it normally
  }

  // Static assets → cache-first, fall back to network
  event.respondWith(
    caches.match(event.request).then(
      (cached) => cached || fetch(event.request)
    )
  );
});
