/**
 * TalentOrbit Service Worker
 * Cache-first for static assets, network-first for API calls.
 * Push notification support for real-time alerts.
 * Version is bumped automatically by the build timestamp.
 */

const CACHE_NAME = 'talentorbit-v__SW_VERSION__';
const STATIC_ASSETS = [
    '/',
    '/manifest.json',
];

// Install — precache the app shell
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// Activate — clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((k) => k.startsWith('talentorbit-') && k !== CACHE_NAME)
                    .map((k) => caches.delete(k))
            )
        )
    );
    self.clients.claim();
});

// ── Push Notifications ────────────────────────────────────────────────────
self.addEventListener('push', (event) => {
    let payload = { title: 'TalentOrbit', body: 'You have a new notification.' };

    if (event.data) {
        try {
            payload = event.data.json();
        } catch {
            payload.body = event.data.text() || payload.body;
        }
    }

    const options = {
        body: payload.body || payload.message || '',
        icon: payload.icon || '/icon-192.svg',
        badge: '/icon-192.svg',
        tag: payload.tag || `to-push-${Date.now()}`,
        data: {
            url: payload.url || payload.click_action || '/',
            notificationId: payload.notification_id || null,
        },
        actions: payload.actions || [],
        requireInteraction: payload.require_interaction || false,
        vibrate: [100, 50, 100],
    };

    event.waitUntil(
        self.registration.showNotification(payload.title || 'TalentOrbit', options)
    );
});

// Handle notification click — focus or open the app
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const targetUrl = event.notification.data?.url || '/';

    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
            // If a TalentOrbit window is already open, focus it and navigate
            for (const client of clients) {
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    client.focus();
                    if (targetUrl !== '/') {
                        client.navigate(targetUrl);
                    }
                    return;
                }
            }
            // Otherwise open a new window
            return self.clients.openWindow(targetUrl);
        })
    );
});

// Handle notification close — optional analytics hook
self.addEventListener('notificationclose', (_event) => {
    // Could send analytics event here in the future
});

// Fetch — network-first for API, cache-first for static assets
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') return;

    // Skip cross-origin requests except fonts & CDN
    if (url.origin !== self.location.origin &&
        !url.hostname.includes('fonts.googleapis.com') &&
        !url.hostname.includes('fonts.gstatic.com')) {
        return;
    }

    // API calls — network-first with no cache
    if (url.pathname.startsWith('/api/')) {
        return;
    }

    // Static assets (JS, CSS, images, fonts) — stale-while-revalidate
    event.respondWith(
        caches.open(CACHE_NAME).then(async (cache) => {
            const cached = await cache.match(request);
            const fetchPromise = fetch(request).then((response) => {
                if (response && response.status === 200 && response.type === 'basic') {
                    cache.put(request, response.clone());
                }
                return response;
            }).catch(() => cached);

            return cached || fetchPromise;
        })
    );
});
