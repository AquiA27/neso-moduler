// Service Worker for PWA
const CACHE_NAME = 'neso-v1';
const urlsToCache = [
  '/',
  '/index.html',
  '/manifest.json',
];

// Install event
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Fetch event - Network first, fallback to cache
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const urlString = request.url || '';

  // Skip non-HTTP(S) schemes (chrome-extension, blob, data, etc.)
  if (!urlString.startsWith('http')) {
    return;
  }

  // Only handle same-origin GET requests
  if (request.method !== 'GET' || !urlString.startsWith(self.location.origin)) {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        // Only cache successful, basic (same-origin) responses
        if (
          response &&
          response.status === 200 &&
          response.type === 'basic'
        ) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache).catch(() => {
              // Ignore caching errors (e.g. opaque responses)
            });
          });
        }

        return response;
      })
      .catch(() => caches.match(request))
  );
});

// Activate event - Clean old caches
self.addEventListener('activate', (event) => {
  const cacheWhitelist = [CACHE_NAME];

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (!cacheWhitelist.includes(cacheName)) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Push notification
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};

  const options = {
    body: data.body || 'Yeni bildirim',
    icon: data.icon || '/icon-192x192.png',
    badge: '/icon-192x192.png',
    vibrate: [200, 100, 200],
    data: data.data || {},
    actions: data.actions || [],
    tag: data.tag || 'default',
    requireInteraction: data.requireInteraction || false,
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'Neso', options)
  );
});

// Notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  event.waitUntil(
    clients.openWindow(event.notification.data.url || '/')
  );
});

// Background sync (for offline operations)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-orders') {
    event.waitUntil(syncOrders());
  }
});

async function syncOrders() {
  // TODO: Implement offline order sync
  console.log('Syncing offline orders...');
}
