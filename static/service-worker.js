const CACHE_NAME = "busystem-v10";

const urlsToCache = [
  "/",
  "/dashboard",
  "/cashflow",
  "/investments",
  "/livestock",
  "/assets",
  "/liability",
  "/goals",
  "/budget",
  "/reports",
  "/analytics",
  "/ratios",
  "/risk",
  "/timeline",
  "/decisions",
  "/rules",
  "/exports",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
