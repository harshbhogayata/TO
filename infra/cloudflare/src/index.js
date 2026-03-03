/**
 * TalentOrbit — Cloudflare Worker: Edge API Cache
 *
 * Intelligent edge caching layer that sits between clients and the
 * TalentOrbit API origin. Provides sub-millisecond responses for
 * cacheable endpoints while preserving real-time accuracy for
 * authenticated and mutable routes.
 *
 * Architecture:
 *   Client → Cloudflare Edge (this Worker) → Origin (K8s Ingress)
 *
 * Cache tiers:
 *   1. Cloudflare Cache API (per-colo, automatic eviction)
 *   2. Workers KV (global, explicit TTL, used for cache tags/purge)
 *
 * Cache-Control contract with origin:
 *   - Origin sets `Cache-Control` and `X-Cache-Tags` headers
 *   - Worker respects origin CC directives when present
 *   - Worker applies default TTLs for known cacheable routes when origin
 *     doesn't set CC (backward-compatible with existing Django views)
 *
 * Purge:
 *   - Tag-based purge via KV: write a purge marker, Worker checks before serving
 *   - Full purge: `wrangler kv:key delete --namespace-id=<id> <key>`
 *   - Django signal → Celery task → KV purge marker (see compliance/signals.py)
 */

// ─── Route classification ────────────────────────────────────────────────────

/**
 * Routes that are ALWAYS cacheable (public, read-only, unauthenticated).
 * Pattern → TTL in seconds.
 */
const CACHEABLE_ROUTES = [
  { pattern: /^\/api\/v1\/jobs\/?(\?.*)?$/,             ttl: 60,   tags: ['jobs'] },
  { pattern: /^\/api\/v1\/jobs\/\d+\/?$/,               ttl: 120,  tags: ['jobs', 'job-detail'] },
  { pattern: /^\/api\/v1\/courses\/?(\?.*)?$/,           ttl: 120,  tags: ['courses'] },
  { pattern: /^\/api\/v1\/courses\/\d+\/?$/,             ttl: 300,  tags: ['courses', 'course-detail'] },
  { pattern: /^\/api\/v1\/courses\/categories\/?$/,      ttl: 600,  tags: ['courses', 'categories'] },
  { pattern: /^\/api\/v1\/blog\/?(\?.*)?$/,              ttl: 300,  tags: ['blog'] },
  { pattern: /^\/api\/v1\/blog\/[\w-]+\/?$/,             ttl: 600,  tags: ['blog', 'blog-detail'] },
  { pattern: /^\/api\/v1\/search\/?(\?.*)?$/,            ttl: 30,   tags: ['search'] },
  { pattern: /^\/api\/v1\/admin-api\/public-stats\/?$/,  ttl: 300,  tags: ['stats'] },
  { pattern: /^\/health\/?$/,                            ttl: 5,    tags: ['health'] },
  { pattern: /^\/health\/(ready|live)\/?$/,              ttl: 5,    tags: ['health'] },
  // Certificate / badge verification (public)
  { pattern: /^\/api\/v1\/courses\/certificates\/verify\//, ttl: 3600, tags: ['certificates'] },
  { pattern: /^\/api\/v1\/assessments\/badges\/verify\//,   ttl: 3600, tags: ['badges'] },
];

/**
 * Routes that must NEVER be cached.
 */
const NEVER_CACHE_PATTERNS = [
  /^\/api\/v1\/auth\//,          // Authentication
  /^\/api\/v1\/payments\//,      // Payment flows
  /^\/api\/v1\/compliance\//,    // GDPR / audit
  /^\/api\/v1\/messages\//,      // Private messaging
  /^\/api\/v1\/notifications\//, // User-specific
  /^\/ws\//,                     // WebSocket
  /^\/admin\//,                  // Django admin
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Build a deterministic cache key from the request.
 * Includes: method, URL, Accept-Language, API version.
 * Excludes: Authorization, Cookie (these routes are public-only).
 */
function buildCacheKey(request) {
  const url = new URL(request.url);
  // Normalise: lowercase path, sort query params
  const path = url.pathname.toLowerCase().replace(/\/+$/, '') || '/';
  url.searchParams.sort();
  const params = url.searchParams.toString();
  const lang = (request.headers.get('Accept-Language') || 'en').split(',')[0].trim();
  return new Request(
    `https://cache.talentorbit.internal${path}${params ? '?' + params : ''}`,
    {
      method: 'GET',
      headers: { 'X-Cache-Lang': lang },
    }
  );
}

/**
 * Check whether a purge marker exists in KV for any of the given tags.
 */
async function isTagPurged(env, tags, cacheTimestamp) {
  if (!env.EDGE_CACHE || !tags.length) return false;
  // Check tags in parallel
  const checks = tags.map(async (tag) => {
    const purgedAt = await env.EDGE_CACHE.get(`purge:${tag}`);
    return purgedAt && parseInt(purgedAt, 10) > cacheTimestamp;
  });
  const results = await Promise.all(checks);
  return results.some(Boolean);
}

/**
 * Classify a request and return caching metadata.
 */
function classifyRequest(request) {
  const url = new URL(request.url);
  const path = url.pathname;

  // Never cache non-GET requests
  if (request.method !== 'GET') {
    return { cacheable: false, reason: 'non-GET' };
  }

  // Never cache if Authorization header is present
  if (request.headers.get('Authorization')) {
    return { cacheable: false, reason: 'authenticated' };
  }

  // Never cache WebSocket upgrades
  if (request.headers.get('Upgrade') === 'websocket') {
    return { cacheable: false, reason: 'websocket' };
  }

  // Explicit never-cache routes
  for (const pattern of NEVER_CACHE_PATTERNS) {
    if (pattern.test(path)) {
      return { cacheable: false, reason: 'never-cache-route' };
    }
  }

  // Check cacheable routes
  for (const route of CACHEABLE_ROUTES) {
    if (route.pattern.test(path)) {
      return {
        cacheable: true,
        ttl: route.ttl,
        tags: route.tags,
      };
    }
  }

  // Default: not cacheable (safe default for unclassified routes)
  return { cacheable: false, reason: 'unclassified' };
}

// ─── Main handler ────────────────────────────────────────────────────────────

export default {
  /**
   * @param {Request} request
   * @param {Object} env - Bindings (EDGE_CACHE KV, environment vars)
   * @param {Object} ctx - Execution context (waitUntil for async cleanup)
   */
  async fetch(request, env, ctx) {
    const startTime = Date.now();
    const classification = classifyRequest(request);

    // ── Pass-through for non-cacheable requests ────────────────────────
    if (!classification.cacheable) {
      const response = await fetch(request);
      const headers = new Headers(response.headers);
      headers.set('X-Cache', 'BYPASS');
      headers.set('X-Cache-Reason', classification.reason);
      headers.set('X-Edge-Time', `${Date.now() - startTime}ms`);
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    }

    // ── Cacheable request flow ─────────────────────────────────────────
    const cache = caches.default;
    const cacheKey = buildCacheKey(request);
    const defaultTTL = parseInt(env.DEFAULT_TTL || '120', 10);
    const maxTTL = parseInt(env.MAX_TTL || '600', 10);
    const ttl = Math.min(classification.ttl || defaultTTL, maxTTL);

    // 1. Check Cloudflare Cache API
    let cachedResponse = await cache.match(cacheKey);

    if (cachedResponse) {
      // Check for tag-based purge
      const cacheTimestamp = parseInt(
        cachedResponse.headers.get('X-Cache-Timestamp') || '0', 10
      );
      const purged = await isTagPurged(env, classification.tags, cacheTimestamp);

      if (!purged) {
        const headers = new Headers(cachedResponse.headers);
        headers.set('X-Cache', 'HIT');
        headers.set('X-Edge-Time', `${Date.now() - startTime}ms`);
        headers.set('CF-Cache-Status', 'HIT');
        return new Response(cachedResponse.body, {
          status: cachedResponse.status,
          statusText: cachedResponse.statusText,
          headers,
        });
      }
      // Purged — fall through to origin
    }

    // 2. Cache MISS — fetch from origin
    const originResponse = await fetch(request);

    // Only cache successful responses
    if (originResponse.status !== 200) {
      const headers = new Headers(originResponse.headers);
      headers.set('X-Cache', 'MISS');
      headers.set('X-Cache-Reason', `origin-${originResponse.status}`);
      headers.set('X-Edge-Time', `${Date.now() - startTime}ms`);
      return new Response(originResponse.body, {
        status: originResponse.status,
        statusText: originResponse.statusText,
        headers,
      });
    }

    // Respect origin Cache-Control: no-store / no-cache / private
    const originCC = originResponse.headers.get('Cache-Control') || '';
    if (/no-store|no-cache|private/.test(originCC)) {
      const headers = new Headers(originResponse.headers);
      headers.set('X-Cache', 'MISS');
      headers.set('X-Cache-Reason', 'origin-no-cache');
      headers.set('X-Edge-Time', `${Date.now() - startTime}ms`);
      return new Response(originResponse.body, {
        status: originResponse.status,
        statusText: originResponse.statusText,
        headers,
      });
    }

    // 3. Store in cache
    const now = Date.now();
    const responseHeaders = new Headers(originResponse.headers);
    responseHeaders.set('Cache-Control', `public, s-maxage=${ttl}, max-age=${Math.floor(ttl / 2)}`);
    responseHeaders.set('X-Cache', 'MISS');
    responseHeaders.set('X-Cache-Timestamp', String(now));
    responseHeaders.set('X-Cache-Tags', classification.tags.join(','));
    responseHeaders.set('X-Edge-Time', `${Date.now() - startTime}ms`);
    responseHeaders.set('Vary', 'Accept-Language');

    const responseToCache = new Response(originResponse.body, {
      status: originResponse.status,
      statusText: originResponse.statusText,
      headers: responseHeaders,
    });

    // Write to cache asynchronously (don't block the response)
    ctx.waitUntil(cache.put(cacheKey, responseToCache.clone()));

    // Write cache metadata to KV for tag-based purge support
    if (env.EDGE_CACHE && classification.tags.length) {
      ctx.waitUntil(
        env.EDGE_CACHE.put(
          `cached:${new URL(request.url).pathname}`,
          JSON.stringify({
            tags: classification.tags,
            timestamp: now,
            ttl,
          }),
          { expirationTtl: ttl + 60 }
        )
      );
    }

    return responseToCache;
  },
};

// ─── Scheduled handler (cache warming) ───────────────────────────────────────

/**
 * Cron trigger: warm critical cache entries on a schedule.
 * Configure in wrangler.toml:
 *   [triggers]
 *   crons = ["*/5 * * * *"]
 */
// export default {
//   ...existing fetch handler...,
//   async scheduled(event, env, ctx) {
//     const warmUrls = [
//       '/api/v1/jobs/?ordering=-created_at&page_size=20',
//       '/api/v1/courses/?ordering=-popularity&page_size=20',
//       '/api/v1/courses/categories/',
//       '/api/v1/admin-api/public-stats/',
//     ];
//     for (const path of warmUrls) {
//       ctx.waitUntil(
//         fetch(`${env.ORIGIN}${path}`, {
//           headers: { 'User-Agent': 'TalentOrbit-CacheWarmer/1.0' },
//         })
//       );
//     }
//   },
// };
