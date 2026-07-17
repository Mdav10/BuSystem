const CACHE_NAME = 'busystem-v10';
const urlsToCache = [
  '/',
  '/dashboard',
  '/cashflow',
  '/investments',
  '/livestock',
  '/assets',
  '/liability',
  '/goals',
  '/budget',
  '/reports',
  '/analytics',
  '/ratios',
  '/risk',
  '/timeline',
  '/decisions',
  '/rules',
  '/exports',
  '/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  if (event.request.url.includes('/api/')) return;
  
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
