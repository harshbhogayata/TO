/**
 * src/services/searchService.js
 * API client for the Search & Discovery engine.
 *
 * All endpoints hit /api/v1/search/... via the shared Axios instance
 * (auto-attaches auth headers, handles token refresh).
 */
import api from './api';

/**
 * Unified search across all entity types.
 * @param {string} q - Search query
 * @param {Object} [params] - Additional params (entity_type, limit)
 * @returns {Promise<{results: Array, search_meta: Object}>}
 */
export const unifiedSearch = (q, params = {}) =>
    api.get('/search/', { params: { q, ...params } });

/**
 * Job-specific search with faceted filtering.
 * @param {Object} params - { q, job_type, work_mode, experience_level, salary_min, salary_max, skills, location, sort, page }
 * @returns {Promise<{count, next, previous, results, search_meta}>}
 */
export const searchJobs = (params = {}) =>
    api.get('/search/jobs/', { params });

/**
 * Talent profile search (company/admin only).
 * @param {Object} params - { q, is_open_to_work, skills, location, page }
 * @returns {Promise<{count, next, previous, results, search_meta}>}
 */
export const searchTalent = (params = {}) =>
    api.get('/search/talent/', { params });

/**
 * Company search.
 * @param {Object} params - { q, industry, is_verified, location, page }
 * @returns {Promise<{count, next, previous, results, search_meta}>}
 */
export const searchCompanies = (params = {}) =>
    api.get('/search/companies/', { params });

/**
 * Fast autocomplete suggestions (Redis-backed).
 * @param {string} q - Prefix (min 2 chars)
 * @param {string} [entityType='jobs'] - Entity type filter
 * @returns {Promise<{suggestions: Array<{text, entity_type}>}>}
 */
export const getAutocompleteSuggestions = (q, entityType = 'jobs') =>
    api.get('/search/autocomplete/', { params: { q, entity_type: entityType } });

/**
 * Trending searches.
 * @param {string} [entityType='all']
 * @returns {Promise<{trending: Array<{query, count, entity_type}>}>}
 */
export const getTrendingSearches = (entityType = 'all') =>
    api.get('/search/trending/', { params: { entity_type: entityType } });

/**
 * Record a search result click for analytics.
 * Fire-and-forget — errors are swallowed.
 * @param {Object} data - { query, entity_type, result_id, position }
 */
export const recordSearchClick = (data) => {
    api.post('/search/click/', data).catch(() => {
        // Swallow — analytics should never break UX
    });
};

export default {
    unifiedSearch,
    searchJobs,
    searchTalent,
    searchCompanies,
    getAutocompleteSuggestions,
    getTrendingSearches,
    recordSearchClick,
};
