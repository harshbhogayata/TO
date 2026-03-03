/**
 * developerStore.js
 * Zustand store for the Developer Platform pages.
 */
import { create } from 'zustand';

export const useDeveloperStore = create((set) => ({
    // ── Portal Stats ─────────────────────────────────────────────
    portalStats: null,
    portalStatsLoading: false,
    portalStatsError: null,
    setPortalStats: (v) => set({ portalStats: v }),
    setPortalStatsLoading: (v) => set({ portalStatsLoading: v }),
    setPortalStatsError: (v) => set({ portalStatsError: v }),

    // ── API Keys ─────────────────────────────────────────────────
    apiKeys: [],
    apiKeysLoading: false,
    apiKeysError: null,
    setApiKeys: (v) => set({ apiKeys: v }),
    setApiKeysLoading: (v) => set({ apiKeysLoading: v }),
    setApiKeysError: (v) => set({ apiKeysError: v }),

    // ── Webhooks ─────────────────────────────────────────────────
    webhooks: [],
    webhooksLoading: false,
    webhooksError: null,
    activeWebhook: null,
    deliveryLog: [],
    deliveryLogLoading: false,
    setWebhooks: (v) => set({ webhooks: v }),
    setWebhooksLoading: (v) => set({ webhooksLoading: v }),
    setWebhooksError: (v) => set({ webhooksError: v }),
    setActiveWebhook: (v) => set({ activeWebhook: v }),
    setDeliveryLog: (v) => set({ deliveryLog: v }),
    setDeliveryLogLoading: (v) => set({ deliveryLogLoading: v }),

    // ── OAuth Apps ───────────────────────────────────────────────
    oauthApps: [],
    oauthAppsLoading: false,
    oauthAppsError: null,
    setOauthApps: (v) => set({ oauthApps: v }),
    setOauthAppsLoading: (v) => set({ oauthAppsLoading: v }),
    setOauthAppsError: (v) => set({ oauthAppsError: v }),

    // ── Changelog ────────────────────────────────────────────────
    changelog: [],
    changelogLoading: false,
    setChangelog: (v) => set({ changelog: v }),
    setChangelogLoading: (v) => set({ changelogLoading: v }),

    // ── Reference data ───────────────────────────────────────────
    endpoints: [],
    rateLimits: [],
    availableEvents: [],
    availableScopes: { api_key_scopes: [], oauth_scopes: [] },
    setEndpoints: (v) => set({ endpoints: v }),
    setRateLimits: (v) => set({ rateLimits: v }),
    setAvailableEvents: (v) => set({ availableEvents: v }),
    setAvailableScopes: (v) => set({ availableScopes: v }),
}));
