/**
 * src/store/reviewStore.js
 * Zustand store for company reviews state.
 */
import { create } from 'zustand';

export const useReviewStore = create((set) => ({
    // ── Reviews list ─────────────────────────────────────────────────────────
    reviews: [],
    reviewsLoading: false,
    reviewsError: null,
    totalCount: 0,

    setReviews: (reviews) => set({ reviews }),
    setReviewsLoading: (loading) => set({ reviewsLoading: loading }),
    setReviewsError: (error) => set({ reviewsError: error }),
    setTotalCount: (count) => set({ totalCount: count }),

    // ── Stats ────────────────────────────────────────────────────────────────
    stats: null,
    statsLoading: false,
    setStats: (stats) => set({ stats }),
    setStatsLoading: (loading) => set({ statsLoading: loading }),

    // ── Filters ──────────────────────────────────────────────────────────────
    filters: {
        department: '',
        min_rating: '',
        role: '',
        ordering: '-created_at',
    },
    setFilter: (key, value) =>
        set((state) => ({ filters: { ...state.filters, [key]: value } })),
    resetFilters: () =>
        set({
            filters: {
                department: '',
                min_rating: '',
                role: '',
                ordering: '-created_at',
            },
        }),

    // ── Write form ───────────────────────────────────────────────────────────
    submitting: false,
    submitError: null,
    setSubmitting: (val) => set({ submitting: val }),
    setSubmitError: (err) => set({ submitError: err }),
}));
