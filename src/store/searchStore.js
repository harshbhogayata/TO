/**
 * src/store/searchStore.js
 * Zustand store for search state — query, filters, results, suggestions, trending.
 *
 * Follows the same patterns as authStore / chatStore:
 *  - No persistence (search state is ephemeral)
 *  - Debounced search via external hook
 *  - Separated concerns: query state vs. result state
 */
import { create } from 'zustand';
import {
    searchJobs,
    searchTalent,
    searchCompanies,
    unifiedSearch,
    getAutocompleteSuggestions,
    getTrendingSearches,
    recordSearchClick,
} from '../services/searchService';

export const useSearchStore = create((set, get) => ({
    // ─── Query State ────────────────────────────────────────────────────
    query: '',
    entityType: 'jobs',          // 'jobs' | 'talent' | 'companies' | 'all'
    filters: {},                  // { job_type, work_mode, salary_min, ... }
    sort: 'relevance',            // 'relevance' | 'salary' | 'date'
    page: 1,

    // ─── Result State ───────────────────────────────────────────────────
    results: [],
    totalCount: 0,
    isLoading: false,
    error: null,
    searchMeta: null,             // { query, filters, response_time_ms }
    hasSearched: false,           // Distinguish "no results" from "haven't searched"

    // ─── Autocomplete State ─────────────────────────────────────────────
    suggestions: [],
    isSuggestionsLoading: false,
    showSuggestions: false,

    // ─── Trending State ─────────────────────────────────────────────────
    trending: [],
    isTrendingLoading: false,

    // ─── Actions ────────────────────────────────────────────────────────

    setQuery: (query) => set({ query }),

    setEntityType: (entityType) => set({ entityType, page: 1, results: [], hasSearched: false }),

    setFilters: (filters) => set({ filters, page: 1 }),

    updateFilter: (key, value) => set((state) => ({
        filters: { ...state.filters, [key]: value },
        page: 1,
    })),

    removeFilter: (key) => set((state) => {
        const next = { ...state.filters };
        delete next[key];
        return { filters: next, page: 1 };
    }),

    clearFilters: () => set({ filters: {}, page: 1 }),

    setSort: (sort) => set({ sort, page: 1 }),

    setPage: (page) => set({ page }),

    /**
     * Execute a search based on current store state.
     * Called by the SearchPage component on query/filter/page changes.
     */
    executeSearch: async () => {
        const { query, entityType, filters, sort, page } = get();
        set({ isLoading: true, error: null, showSuggestions: false });

        try {
            const params = {
                q: query,
                sort,
                page,
                ...filters,
            };

            let response;

            switch (entityType) {
                case 'jobs':
                    response = await searchJobs(params);
                    break;
                case 'talent':
                    response = await searchTalent(params);
                    break;
                case 'companies':
                    response = await searchCompanies(params);
                    break;
                case 'all':
                    response = await unifiedSearch(query, { entity_type: 'all', limit: 30 });
                    break;
                default:
                    response = await searchJobs(params);
            }

            const data = response.data;

            if (entityType === 'all') {
                set({
                    results: data.results || [],
                    totalCount: data.search_meta?.total || data.results?.length || 0,
                    searchMeta: data.search_meta || null,
                    hasSearched: true,
                    isLoading: false,
                });
            } else {
                set({
                    results: data.results || [],
                    totalCount: data.count || data.results?.length || 0,
                    searchMeta: data.search_meta || null,
                    hasSearched: true,
                    isLoading: false,
                });
            }
        } catch (err) {
            const message = err?.response?.data?.detail
                || err?.response?.data?.message
                || 'Search failed. Please try again.';
            set({
                error: message,
                results: [],
                totalCount: 0,
                isLoading: false,
                hasSearched: true,
            });
        }
    },

    /**
     * Fetch autocomplete suggestions for the current prefix.
     */
    fetchSuggestions: async (prefix) => {
        if (!prefix || prefix.length < 2) {
            set({ suggestions: [], showSuggestions: false });
            return;
        }

        set({ isSuggestionsLoading: true });

        try {
            const { entityType } = get();
            const { data } = await getAutocompleteSuggestions(prefix, entityType);
            set({
                suggestions: data.suggestions || [],
                showSuggestions: (data.suggestions || []).length > 0,
                isSuggestionsLoading: false,
            });
        } catch {
            set({ suggestions: [], showSuggestions: false, isSuggestionsLoading: false });
        }
    },

    hideSuggestions: () => set({ showSuggestions: false }),

    /**
     * Fetch trending searches.
     */
    fetchTrending: async () => {
        const { entityType } = get();
        set({ isTrendingLoading: true });

        try {
            const { data } = await getTrendingSearches(entityType);
            set({ trending: data.trending || [], isTrendingLoading: false });
        } catch {
            set({ trending: [], isTrendingLoading: false });
        }
    },

    /**
     * Record a click on a search result (fire-and-forget analytics).
     */
    trackClick: (resultId, position) => {
        const { query, entityType } = get();
        if (query) {
            recordSearchClick({
                query,
                entity_type: entityType === 'all' ? 'all' : entityType,
                result_id: resultId,
                position,
            });
        }
    },

    /**
     * Reset all search state.
     */
    reset: () => set({
        query: '',
        filters: {},
        sort: 'relevance',
        page: 1,
        results: [],
        totalCount: 0,
        isLoading: false,
        error: null,
        searchMeta: null,
        hasSearched: false,
        suggestions: [],
        showSuggestions: false,
    }),
}));
