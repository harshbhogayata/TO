/**
 * src/services/api.js
 * Central Axios instance for the TalentOrbit API.
 *
 * Features:
 *  - Base URL points to Django backend (v1 prefix)
 *  - Automatically attaches Authorization: Bearer <token>
 *  - Silently refreshes expired access tokens via the refresh endpoint
 *  - Logs the user out (clears store) when refresh also fails
 */
import axios from 'axios';
import { useAuthStore } from '../store/authStore';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
    baseURL: BASE_URL,
    headers: { 'Content-Type': 'application/json' },
    timeout: 15000,
});

// ─── Request Interceptor ────────────────────────────────────────────────────
api.interceptors.request.use(
    (config) => {
        const token = useAuthStore.getState().accessToken;
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// ─── Response Interceptor — silent token refresh ────────────────────────────
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(({ resolve, reject }) => {
        if (error) reject(error);
        else resolve(token);
    });
    failedQueue = [];
};

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
            if (isRefreshing) {
                // Queue the request while a refresh is in-flight
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                }).then((token) => {
                    originalRequest.headers.Authorization = `Bearer ${token}`;
                    return api(originalRequest);
                }).catch((err) => Promise.reject(err));
            }

            originalRequest._retry = true;
            isRefreshing = true;

            const refreshToken = useAuthStore.getState().refreshToken;

            if (!refreshToken) {
                isRefreshing = false;
                useAuthStore.getState().logout();
                return Promise.reject(error);
            }

            try {
                const { data } = await axios.post(`${BASE_URL}/auth/refresh/`, {
                    refresh: refreshToken,
                });
                const newAccess = data.access;
                // ROTATE_REFRESH_TOKENS is enabled: the server returns a new
                // refresh token and blacklists the old one. Save both.
                const newRefresh = data.refresh || refreshToken;
                useAuthStore.getState().setTokens(newAccess, newRefresh);
                api.defaults.headers.common.Authorization = `Bearer ${newAccess}`;
                processQueue(null, newAccess);
                originalRequest.headers.Authorization = `Bearer ${newAccess}`;
                return api(originalRequest);
            } catch (refreshError) {
                processQueue(refreshError, null);
                // Dispatch session-expired event so UI can show a toast
                window.dispatchEvent(new CustomEvent('talentorbit:session-expired'));
                useAuthStore.getState().logout();
                return Promise.reject(refreshError);
            } finally {
                isRefreshing = false;
            }
        }

        return Promise.reject(error);
    }
);

export default api;

/**
 * Restore session on app boot — access token is memory-only,
 * so we need to refresh it from the persisted refresh token.
 * Returns true if session was restored, false otherwise.
 */
export async function restoreSession() {
    const { refreshToken, isAuthenticated } = useAuthStore.getState();
    if (!isAuthenticated || !refreshToken) return false;

    try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh/`, {
            refresh: refreshToken,
        });
        useAuthStore.getState().setTokens(data.access, data.refresh || refreshToken);
        return true;
    } catch {
        useAuthStore.getState().logout();
        return false;
    }
}

/**
 * Extract a user-friendly message from an API error (Axios or similar).
 * Prefers detail, then message, then non-field errors, then fallback.
 */
export function getApiErrorMessage(err, fallback = 'Something went wrong. Please try again.') {
    const data = err?.response?.data;
    if (!data) return fallback;
    if (typeof data.detail === 'string') return data.detail;
    if (data.message) return data.message;
    if (data.error) return data.error;
    const nonField = data.non_field_errors?.[0];
    if (nonField) return nonField;
    const firstKey = Object.keys(data)[0];
    const firstVal = Array.isArray(data[firstKey]) ? data[firstKey][0] : data[firstKey];
    if (firstVal && typeof firstVal === 'string') return firstVal;
    return fallback;
}

// ─── Named service functions ────────────────────────────────────────────────
export const authService = {
    loginUser: (email, password) =>
        api.post('/auth/login/', { email, password }),
    registerTalent: (data) =>
        api.post('/auth/register/talent/', data),
    extractResume: (formData) =>
        api.post('/intelligence/parse-resume/', formData),
    registerCompany: (data) =>
        api.post('/auth/register/company/', data),
    logout: (refresh) =>
        api.post('/auth/logout/', { refresh }),
    getMe: () =>
        api.get('/auth/me/'),
    updateTalentProfile: (data) =>
        api.patch('/auth/profile/talent/', data),
    updateCompanyProfile: (data) =>
        api.patch('/auth/profile/company/', data),
    changePassword: (data) =>
        api.post('/auth/change-password/', data),
    requestPasswordReset: (email) =>
        api.post('/auth/password-reset/', { email }),
    confirmPasswordReset: (uid, token, new_password) =>
        api.post('/auth/password-reset/confirm/', { uid, token, new_password }),
    verifyEmail: (uid, token) =>
        api.post('/auth/verify-email/', { uid, token }),
    resendVerification: () =>
        api.post('/auth/resend-verification/'),
    setup2FA: () => api.get('/auth/2fa/setup/'),
    verify2FA: (token) => api.post('/auth/2fa/verify/', { token }),
    disable2FA: (password) => api.post('/auth/2fa/disable/', { password }),
    login2FA: (temp_token, totp_code) =>
        api.post('/auth/2fa/login/', { temp_token, totp_code }),
    deactivateAccount: (password) => api.post('/auth/deactivate/', { password }),
};

export const jobsService = {
    listJobs: (params) => api.get('/jobs/', { params }),
    getJob: (id) => api.get(`/jobs/${id}/`),
    applyToJob: (id, data) => api.post(`/jobs/${id}/apply/`, data),
    myApplications: () => api.get('/jobs/applications/'),
    withdrawApplication: (id) => api.delete(`/jobs/applications/${id}/`),
    savedJobs: () => api.get('/jobs/saved/'),
    saveJob: (jobId) => api.post('/jobs/saved/', { job_id: jobId }),
    unsaveJob: (id) => api.delete(`/jobs/saved/${id}/`),
    // Company
    companyJobs: () => api.get('/jobs/mine/'),
    createJob: (data) => api.post('/jobs/mine/', data),
    updateJob: (id, data) => api.patch(`/jobs/mine/${id}/`, data),
    deleteJob: (id) => api.delete(`/jobs/mine/${id}/`),
    jobApplications: (jobId) => api.get(`/jobs/${jobId}/applications/`),
    updateApplicationStatus: (id, status) =>
        api.patch(`/jobs/applications/${id}/status/`, { status }),
};

export const messagingService = {
    myThreads: () => api.get('/messages/'),
    createThread: (data) => api.post('/messages/thread/', data),
    getMessages: (threadId) => api.get(`/messages/${threadId}/messages/`),
    sendMessage: (data) => api.post('/messages/send/', data),
    unreadCount: () => api.get('/messages/unread/'),
};

export const adminService = {
    stats: () => api.get('/admin-api/stats/'),
    listUsers: (params) => api.get('/admin-api/users/', { params }),
    verifyUser: (id) => api.patch(`/admin-api/users/${id}/verify/`),
    deactivateUser: (id) => api.delete(`/admin-api/users/${id}/`),
    listJobs: () => api.get('/admin-api/jobs/'),
    toggleJob: (id) => api.patch(`/admin-api/jobs/${id}/toggle/`),
    listApplications: () => api.get('/admin-api/applications/'),
};

export const paymentsService = {
    // Plans & Billing
    getPlans: (audience) =>
        api.get('/payments/plans/', { params: audience ? { audience } : {} }),
    getBillingOverview: () =>
        api.get('/payments/billing/'),
    createCheckoutSession: (plan, planId, couponCode) =>
        api.post('/payments/create-checkout-session/', {
            plan, plan_id: planId, coupon_code: couponCode,
        }),
    createPortalSession: () =>
        api.post('/payments/customer-portal/'),
    downloadInvoice: (id) =>
        api.get(`/payments/invoice/${id}/`, { responseType: 'blob' }),

    // Coupons
    validateCoupon: (code) =>
        api.post('/payments/coupons/validate/', { code }),

    // Referrals
    getReferralProgram: () =>
        api.get('/payments/referrals/program/'),
    getReferralStats: () =>
        api.get('/payments/referrals/stats/'),
    getMyReferrals: () =>
        api.get('/payments/referrals/'),
    createReferral: (data) =>
        api.post('/payments/referrals/create/', data),
    getMyReferralRewards: () =>
        api.get('/payments/referrals/rewards/'),

    // Sponsored Campaigns
    getSponsoredCampaigns: () =>
        api.get('/payments/sponsored/'),
    createSponsoredCampaign: (data) =>
        api.post('/payments/sponsored/', data),
    getSponsoredCampaign: (id) =>
        api.get(`/payments/sponsored/${id}/`),
    updateSponsoredCampaign: (id, data) =>
        api.patch(`/payments/sponsored/${id}/`, data),
    toggleCampaignStatus: (id) =>
        api.post(`/payments/sponsored/${id}/toggle/`),

    // Talent Pool CRM
    getPipelines: () =>
        api.get('/payments/pipelines/'),
    createPipeline: (data) =>
        api.post('/payments/pipelines/', data),
    getPipeline: (id) =>
        api.get(`/payments/pipelines/${id}/`),
    updatePipeline: (id, data) =>
        api.patch(`/payments/pipelines/${id}/`, data),
    deletePipeline: (id) =>
        api.delete(`/payments/pipelines/${id}/`),
    getCandidates: (pipelineId, stageId) =>
        api.get(`/payments/pipelines/${pipelineId}/candidates/`, {
            params: stageId ? { stage_id: stageId } : {},
        }),
    addCandidate: (pipelineId, data) =>
        api.post(`/payments/pipelines/${pipelineId}/candidates/`, data),
    getCandidate: (id) =>
        api.get(`/payments/candidates/${id}/`),
    updateCandidate: (id, data) =>
        api.patch(`/payments/candidates/${id}/`, data),
    deleteCandidate: (id) =>
        api.delete(`/payments/candidates/${id}/`),
    moveCandidate: (id, stageId) =>
        api.post(`/payments/candidates/${id}/move/`, { stage_id: stageId }),
    bulkMoveCandidates: (candidateIds, stageId) =>
        api.post('/payments/candidates/bulk-move/', { candidate_ids: candidateIds, stage_id: stageId }),

    // Revenue Dashboard (Admin)
    getRevenueDashboard: () =>
        api.get('/payments/revenue/dashboard/'),
    getRevenueTrend: (months = 12) =>
        api.get('/payments/revenue/trend/', { params: { months } }),
};

export const blogService = {
    listArticles: (params) => api.get('/blog/articles/', { params }),
};

export const notificationsService = {
    myNotifications: () => api.get('/notifications/'),
    read: (id) => api.patch(`/notifications/${id}/read/`),
    readAll: () => api.post('/notifications/read-all/'),
};

export const coursesService = {
    listCourses: () => api.get('/courses/'),
};

export const intelligenceService = {
    // Recommendations
    getRecommendedJobs: (limit = 20) =>
        api.get('/intelligence/recommendations/jobs/', { params: { limit } }),
    getMatchScore: (jobId) =>
        api.get('/intelligence/match-score/', { params: { job: jobId } }),

    // Interactions
    recordInteraction: (jobId, interactionType, metadata = {}) =>
        api.post('/intelligence/interactions/', {
            job: jobId,
            interaction_type: interactionType,
            metadata,
        }),

    // Resume parser
    parseResume: (formData) =>
        api.post('/intelligence/parse-resume/', formData),
    getParsedResume: () =>
        api.get('/intelligence/parse-resume/'),
    applyParsedResume: (data) =>
        api.post('/intelligence/parse-resume/apply/', data),

    // Skill taxonomy
    getSkillTaxonomy: (params) =>
        api.get('/intelligence/skills/taxonomy/', { params }),
    getSkillSuggestions: (q) =>
        api.get('/intelligence/skills/suggestions/', { params: { q } }),

    // Company analytics
    getAnalyticsOverview: () =>
        api.get('/intelligence/analytics/overview/'),
    getAnalyticsFunnel: (jobId) =>
        api.get('/intelligence/analytics/funnel/', { params: jobId ? { job: jobId } : {} }),
    getTimeToHire: () =>
        api.get('/intelligence/analytics/time-to-hire/'),
    getSourceAttribution: () =>
        api.get('/intelligence/analytics/sources/'),
    getTalentPool: () =>
        api.get('/intelligence/analytics/talent-pool/'),
    getBenchmarks: () =>
        api.get('/intelligence/analytics/benchmarks/'),
    getJobPerformance: () =>
        api.get('/intelligence/analytics/jobs/'),
    exportAnalytics: (format = 'json', dateFrom, dateTo) =>
        api.get('/intelligence/analytics/export/', {
            params: { format, date_from: dateFrom, date_to: dateTo },
            responseType: format === 'csv' ? 'blob' : 'json',
        }),

    // Platform analytics (admin)
    getPlatformMetrics: (days = 30) =>
        api.get('/intelligence/analytics/platform/', { params: { days } }),
    getPlatformGrowth: (days = 30) =>
        api.get('/intelligence/analytics/platform/growth/', { params: { days } }),
    getPlatformEngagement: (days = 30) =>
        api.get('/intelligence/analytics/platform/engagement/', { params: { days } }),
    getPlatformBenchmarks: () =>
        api.get('/intelligence/analytics/platform/benchmarks/'),

    // Experiments / A/B testing
    getFeatureFlags: () =>
        api.get('/intelligence/experiments/flags/'),
    trackExperimentEvent: (event, properties = {}, experimentKey, variant) =>
        api.post('/intelligence/experiments/track/', {
            event, properties, experiment_key: experimentKey, variant,
        }),

    // AI Features
    generateJobDescription: (data) =>
        api.post('/intelligence/ai/job-description/', data),
    scheduleInterviews: (data) =>
        api.post('/intelligence/ai/schedule-interviews/', data),

    // AI Chatbot
    chatWithAI: (message, context) =>
        api.post('/intelligence/ai/chat/', { message, context }),

    // Compensation Benchmark
    getCompensationBenchmark: (role, location) =>
        api.get('/intelligence/ai/compensation/', { params: { role, location } }),

    // Feature Flag Management (Admin)
    createFeatureFlag: (data) =>
        api.post('/intelligence/experiments/flags/', data),
    updateFeatureFlag: (id, data) =>
        api.patch(`/intelligence/experiments/flags/${id}/`, data),
    deleteFeatureFlag: (id) =>
        api.delete(`/intelligence/experiments/flags/${id}/`),
};

// ── Compliance & Trust ──────────────────────────────────────────────────────
export const complianceService = {
    // Audit Logs (admin)
    getAuditLogs: (params) => api.get('/compliance/audit-logs/', { params }),
    getAuditLog: (id) => api.get(`/compliance/audit-logs/${id}/`),
    getAuditLogIntegrity: (limit) =>
        api.get('/compliance/audit-logs/integrity/', { params: { limit } }),
    getAuditLogStats: () => api.get('/compliance/audit-logs/stats/'),

    // Policies
    getPolicies: (type) =>
        api.get('/compliance/policies/', { params: type ? { type } : {} }),
    getPolicy: (id) => api.get(`/compliance/policies/${id}/`),
    createPolicy: (data) => api.post('/compliance/policies/create/', data),

    // Consent
    getMyConsent: () => api.get('/compliance/consent/'),
    grantConsent: (policyVersionIds) =>
        api.post('/compliance/consent/grant/', { policy_version_ids: policyVersionIds }),
    withdrawConsent: (policyVersionId, reason) =>
        api.post('/compliance/consent/withdraw/', { policy_version_id: policyVersionId, reason }),
    getConsentStatus: () => api.get('/compliance/consent/status/'),

    // GDPR Data Export
    requestExport: () => api.post('/compliance/gdpr/export/'),
    getMyExports: () => api.get('/compliance/gdpr/export/list/'),
    downloadExport: (token) =>
        api.get(`/compliance/gdpr/export/${token}/download/`, { responseType: 'blob' }),

    // GDPR Data Deletion
    requestDeletion: (data) => api.post('/compliance/gdpr/deletion/', data),
    getMyDeletions: () => api.get('/compliance/gdpr/deletion/list/'),
    confirmDeletion: (token) =>
        api.post('/compliance/gdpr/deletion/confirm/', { token }),
    cancelDeletion: (token) =>
        api.post('/compliance/gdpr/deletion/cancel/', { token }),

    // Teams
    getTeam: () => api.get('/compliance/team/'),
    createTeam: (name) => api.post('/compliance/team/', { name }),
    getTeamMembers: () => api.get('/compliance/team/members/'),
    inviteMember: (data) => api.post('/compliance/team/invite/', data),
    previewInvitation: (token) =>
        api.get(`/compliance/team/invite/${token}/preview/`),
    acceptInvitation: (token) =>
        api.post(`/compliance/team/invite/${token}/accept/`),
    declineInvitation: (token) =>
        api.post(`/compliance/team/invite/${token}/decline/`),
    revokeInvitation: (id) =>
        api.delete(`/compliance/team/invite/${id}/`),
    changeMemberRole: (id, role) =>
        api.patch(`/compliance/team/members/${id}/role/`, { role }),
    removeMember: (id) =>
        api.delete(`/compliance/team/members/${id}/`),
    getTeamInvitations: () => api.get('/compliance/team/invitations/'),

    // Security
    getSecurityInfo: () => api.get('/compliance/security/'),
};

// ── Search / Discovery ──────────────────────────────────────────────────────
export const searchService = {
    search: (params) => api.get('/search/', { params }),
    getCompanyDirectory: (params) => api.get('/search/companies/', { params }),
    getFeaturedEmployers: () => api.get('/search/companies/featured/'),
    getTalentProfiles: (params) => api.get('/search/talent/', { params }),
};
