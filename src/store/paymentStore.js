/**
 * src/store/paymentStore.js
 * Zustand store for payment, billing, referral, CRM, and revenue state.
 */
import { create } from 'zustand';
import { paymentsService } from '../services/api';

export const usePaymentStore = create((set, get) => ({
    // ── Plans ──────────────────────────────────────────────────────────────
    plans: [],
    plansLoading: false,
    fetchPlans: async (audience) => {
        set({ plansLoading: true });
        try {
            const { data } = await paymentsService.getPlans(audience);
            set({ plans: data.results || data, plansLoading: false });
        } catch {
            set({ plansLoading: false });
        }
    },

    // ── Billing ────────────────────────────────────────────────────────────
    billing: null,
    billingLoading: false,
    fetchBilling: async () => {
        set({ billingLoading: true });
        try {
            const { data } = await paymentsService.getBillingOverview();
            set({ billing: data, billingLoading: false });
        } catch {
            set({ billingLoading: false });
        }
    },

    // ── Referrals ──────────────────────────────────────────────────────────
    referralProgram: null,
    referralStats: null,
    referrals: [],
    rewards: [],
    referralLoading: false,
    fetchReferralProgram: async () => {
        try {
            const { data } = await paymentsService.getReferralProgram();
            set({ referralProgram: data.program });
        } catch { /* ignore */ }
    },
    fetchReferralStats: async () => {
        set({ referralLoading: true });
        try {
            const { data } = await paymentsService.getReferralStats();
            set({ referralStats: data, referralLoading: false });
        } catch {
            set({ referralLoading: false });
        }
    },
    fetchReferrals: async () => {
        try {
            const { data } = await paymentsService.getMyReferrals();
            set({ referrals: data.results || data });
        } catch { /* ignore */ }
    },
    fetchRewards: async () => {
        try {
            const { data } = await paymentsService.getMyReferralRewards();
            set({ rewards: data.results || data });
        } catch { /* ignore */ }
    },

    // ── Sponsored Campaigns ────────────────────────────────────────────────
    campaigns: [],
    campaignsLoading: false,
    fetchCampaigns: async () => {
        set({ campaignsLoading: true });
        try {
            const { data } = await paymentsService.getSponsoredCampaigns();
            set({ campaigns: data.results || data, campaignsLoading: false });
        } catch {
            set({ campaignsLoading: false });
        }
    },

    // ── Pipelines & Candidates (CRM) ───────────────────────────────────────
    pipelines: [],
    pipelinesLoading: false,
    activePipeline: null,
    candidates: [],
    candidatesLoading: false,
    fetchPipelines: async () => {
        set({ pipelinesLoading: true });
        try {
            const { data } = await paymentsService.getPipelines();
            set({ pipelines: data.results || data, pipelinesLoading: false });
        } catch {
            set({ pipelinesLoading: false });
        }
    },
    setActivePipeline: (pipeline) => set({ activePipeline: pipeline }),
    fetchCandidates: async (pipelineId, stageId) => {
        set({ candidatesLoading: true });
        try {
            const { data } = await paymentsService.getCandidates(pipelineId, stageId);
            set({ candidates: data.results || data, candidatesLoading: false });
        } catch {
            set({ candidatesLoading: false });
        }
    },

    // ── Revenue (Admin) ────────────────────────────────────────────────────
    revenueMetrics: null,
    revenueTrend: [],
    revenueLoading: false,
    fetchRevenueMetrics: async () => {
        set({ revenueLoading: true });
        try {
            const { data } = await paymentsService.getRevenueDashboard();
            set({ revenueMetrics: data, revenueLoading: false });
        } catch {
            set({ revenueLoading: false });
        }
    },
    fetchRevenueTrend: async (months = 12) => {
        try {
            const { data } = await paymentsService.getRevenueTrend(months);
            set({ revenueTrend: data.trend || [] });
        } catch { /* ignore */ }
    },
}));
