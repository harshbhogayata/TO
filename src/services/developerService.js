/**
 * developerService.js
 * API client for the Developer Platform endpoints.
 * Base path: /api/v1/developer/
 */
import api from './api';

const BASE = '/api/v1/developer';

const developerService = {
    // ── Portal overview ──────────────────────────────────────────
    getPortalStats: () => api.get(`${BASE}/portal/stats/`),

    // ── API Keys ─────────────────────────────────────────────────
    listAPIKeys: () => api.get(`${BASE}/api-keys/`),
    createAPIKey: (data) => api.post(`${BASE}/api-keys/`, data),
    getAPIKey: (id) => api.get(`${BASE}/api-keys/${id}/`),
    revokeAPIKey: (id) => api.delete(`${BASE}/api-keys/${id}/`),
    rotateAPIKey: (id) => api.post(`${BASE}/api-keys/${id}/rotate/`),

    // ── Webhooks ─────────────────────────────────────────────────
    listWebhooks: () => api.get(`${BASE}/webhooks/`),
    createWebhook: (data) => api.post(`${BASE}/webhooks/`, data),
    getWebhook: (id) => api.get(`${BASE}/webhooks/${id}/`),
    updateWebhook: (id, data) => api.patch(`${BASE}/webhooks/${id}/`, data),
    deleteWebhook: (id) => api.delete(`${BASE}/webhooks/${id}/`),
    getDeliveryLog: (webhookId) => api.get(`${BASE}/webhooks/${webhookId}/deliveries/`),
    testWebhookPing: (webhookId) => api.post(`${BASE}/webhooks/${webhookId}/test/`),

    // ── OAuth Apps ───────────────────────────────────────────────
    listOAuthApps: (params) => api.get(`${BASE}/oauth-apps/`, { params }),
    createOAuthApp: (data) => api.post(`${BASE}/oauth-apps/`, data),
    getOAuthApp: (id) => api.get(`${BASE}/oauth-apps/${id}/`),
    revokeOAuthApp: (id) => api.post(`${BASE}/oauth-apps/${id}/revoke/`),

    // ── Changelog ────────────────────────────────────────────────
    listChangelog: () => api.get(`${BASE}/changelog/`),

    // ── Reference data (public) ──────────────────────────────────
    getAvailableEvents: () => api.get(`${BASE}/available-events/`),
    getAvailableScopes: () => api.get(`${BASE}/available-scopes/`),
    getRateLimits: () => api.get(`${BASE}/rate-limits/`),
    getEndpoints: () => api.get(`${BASE}/endpoints/`),
};

export default developerService;
