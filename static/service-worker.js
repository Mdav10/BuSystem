// BuSystem Service Worker - Native App Experience
const CACHE_NAME = 'busystem-v10';
const STATIC_ASSETS = [
  '/',
  '/login',
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
  '/static/manifest.json',
  '/static/service-worker.js'
];

// Install Service Worker - Cache all assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('📦 BuSystem: Caching assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate - Clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('🗑️ BuSystem: Removing old cache', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch - Network first, then cache
self.addEventListener('fetch', event => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip API calls
  if (event.request.url.includes('/api/')) {
    return;
  }

  // Skip static assets that are already cached
  if (event.request.url.includes('/static/')) {
    event.respondWith(
      caches.match(event.request)
        .then(response => {
          if (response) {
            return response;
          }
          return fetch(event.request);
        })
    );
    return;
  }

  // For HTML pages - Network first, fallback to cache
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Cache the response
        const responseClone = response.clone();
        caches.open(CACHE_NAME).then(cache => {
          cache.put(event.request, responseClone);
        });
        return response;
      })
      .catch(() => {
        // Fallback to cache
        return caches.match(event.request)
          .then(cachedResponse => {
            if (cachedResponse) {
              return cachedResponse;
            }
            // If nothing in cache, return offline page
            return caches.match('/');
          });
      })
  );
});

// Handle messages from client
self.addEventListener('message', event => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});

// Push notification support (for future use)
self.addEventListener('push', event => {
  const data = event.data.json();
  const options = {
    body: data.body || 'BuSystem notification',
    icon: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"%3E%3Crect width="512" height="512" rx="100" fill="%230a0e17"/%3E%3Ctext x="256" y="340" font-family="Arial, sans-serif" font-size="180" font-weight="bold" text-anchor="middle" fill="%2300d4ff"%3E💰%3C/text%3E%3Ctext x="256" y="420" font-family="Arial, sans-serif" font-size="42" font-weight="bold" text-anchor="middle" fill="%2300d4ff"%3EBuSys%3C/text%3E%3C/svg%3E',
    badge: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"%3E%3Crect width="512" height="512" rx="100" fill="%230a0e17"/%3E%3Ctext x="256" y="340" font-family="Arial, sans-serif" font-size="180" font-weight="bold" text-anchor="middle" fill="%2300d4ff"%3E💰%3C/text%3E%3C/svg%3E',
    vibrate: [200, 100, 200],
    data: {
      url: data.url || '/dashboard'
    }
  };
  event.waitUntil(
    self.registration.showNotification(data.title || 'BuSystem', options)
  );
});

// Handle notification click
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url || '/dashboard')
  );
});
