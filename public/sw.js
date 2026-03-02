/**
 * TalentOrbit Service Worker
 * Cache-first for static assets, network-first for API calls.
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
