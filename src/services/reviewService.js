/**
 * src/services/reviewService.js
 * API service for Company Reviews module.
 * Maps to backend endpoints under /api/v1/reviews/
 */
import api from './api';

const reviewService = {
    // ── Public ───────────────────────────────────────────────────────────
    listReviews: (companyId, params) =>
        api.get(`/reviews/${companyId}/`, { params }),
    getReviewStats: (companyId) =>
        api.get(`/reviews/${companyId}/stats/`),

    // ── Authenticated ────────────────────────────────────────────────────
    createReview: (data) =>
        api.post('/reviews/', data),
    toggleHelpful: (reviewId) =>
        api.post(`/reviews/${reviewId}/helpful/`),
    respondToReview: (reviewId, data) =>
        api.post(`/reviews/${reviewId}/respond/`, data),
};

export default reviewService;
