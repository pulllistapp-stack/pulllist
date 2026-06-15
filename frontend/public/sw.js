// PullList service worker — minimal v1.
// Registers PWA install eligibility on iOS/Android. No aggressive caching
// yet; we want fresh data from the API every request. A future v2 can add
// stale-while-revalidate for static assets if perf needs it.

const VERSION = "v1";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// Network-first pass-through. The browser's HTTP cache + Next.js's own
// static asset caching still apply — this just gates PWA installability.
self.addEventListener("fetch", (event) => {
  // Don't interfere with non-GET requests
  if (event.request.method !== "GET") return;
  event.respondWith(fetch(event.request).catch(() => Response.error()));
});
