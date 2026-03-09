/**
 * src/store/paymentStore.js
 * Zustand store for payment, billing, referral, CRM, and revenue state.
 */
import { create } from 'zustand';
import { paymentsService } from '../services/api';

const toNumber = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

const normaliseFeatureList = (features = []) => {
    if (!Array.isArray(features)) {
        return [];
    }

    return features
        .map((feature) => {
            if (typeof feature === 'string') {
                return { label: feature, included: true };
            }
            if (feature && typeof feature === 'object') {
                return {
                    label: feature.label ?? feature.name ?? '',
                    included: feature.included !== false,
                };
            }
            return { label: String(feature), included: true };
        })
        .filter((feature) => feature.label);
};

const yearlyToMonthlyPrice = (value) => {
    const parsed = toNumber(value);
    if (parsed === null) {
        return null;
    }
    return Math.round((parsed / 12) * 100) / 100;
};

const humaniseToken = (value) => {
    const raw = String(value ?? '').trim();
    if (!raw) {
        return '';
    }

    return raw
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());
};

const normaliseListPayload = (data) => {
    if (Array.isArray(data)) {
        return data;
    }
    if (Array.isArray(data?.results)) {
        return data.results;
    }
    return [];
};

const normaliseCampaign = (campaign = {}) => ({
    ...campaign,
    name: campaign.name ?? campaign.job_title ?? 'Untitled Campaign',
    sub: campaign.sub ?? campaign.description ?? campaign.target_audience ?? '',
    spend: toNumber(campaign.spend ?? campaign.amount_spent) ?? 0,
    impressions: toNumber(campaign.impressions) ?? 0,
    clicks: toNumber(campaign.clicks) ?? 0,
    applications: toNumber(campaign.applications ?? campaign.apps) ?? 0,
    apps: toNumber(campaign.apps ?? campaign.applications) ?? 0,
    status: String(campaign.status ?? '').toLowerCase() || 'draft',
});

const normalisePipelineStage = (stage = {}) => ({
    ...stage,
    name: stage.name ?? stage.label ?? humaniseToken(stage.id) ?? 'Stage',
});

const normalisePipeline = (pipeline = {}) => ({
    ...pipeline,
    stages: Array.isArray(pipeline.stages) ? pipeline.stages.map(normalisePipelineStage) : [],
    candidate_count: toNumber(pipeline.candidate_count) ?? pipeline.candidate_count ?? 0,
});

const normaliseCandidate = (candidate = {}) => {
    const matchScore = toNumber(candidate.match_score);
    const rating = toNumber(candidate.rating);

    return {
        ...candidate,
        name: candidate.name
            ?? candidate.display_name
            ?? candidate.user_name
            ?? candidate.candidate_name
            ?? candidate.external_name
            ?? candidate.display_email
            ?? candidate.external_email
            ?? 'Unknown',
        role: candidate.role ?? candidate.position ?? candidate.headline ?? '',
        score_display: candidate.score_display
            ?? (matchScore !== null ? `${matchScore}%` : rating !== null ? `${rating}/5` : '—'),
        source_label: candidate.source_label ?? humaniseToken(candidate.source),
        badge: candidate.badge ?? candidate.status ?? humaniseToken(candidate.source),
    };
};

const normaliseCampaigns = (data = []) => normaliseListPayload(data).map(normaliseCampaign);
const normalisePipelines = (data = []) => normaliseListPayload(data).map(normalisePipeline);
const normaliseCandidates = (data = []) => normaliseListPayload(data).map(normaliseCandidate);

export const normalisePlanCatalog = (rawPlans = []) => {
    const grouped = new Map();

    for (const plan of rawPlans || []) {
        const key = `${plan.audience ?? 'ALL'}:${plan.name ?? plan.slug ?? plan.id}`;
        const existing = grouped.get(key) ?? {
            id: key,
            name: plan.name ?? 'Plan',
            slug: plan.slug ?? '',
            audience: plan.audience ?? '',
            monthly_price: null,
            annual_price: null,
            monthly_plan_id: null,
            annual_plan_id: null,
            checkout_plan: plan.name ?? '',
            is_current: false,
            is_popular: Boolean(plan.is_popular),
            cta: 'Select Plan',
            cta_style: plan.is_popular ? 'primary' : 'secondary',
            features: normaliseFeatureList(plan.features),
        };
        const interval = String(plan.billing_interval || '').toLowerCase();

        if (interval === 'monthly') {
            existing.monthly_price = toNumber(plan.price);
            existing.monthly_plan_id = plan.id;
        } else if (interval === 'yearly' || interval === 'annual') {
            existing.annual_price = yearlyToMonthlyPrice(plan.price);
            existing.annual_plan_id = plan.id;
        }

        if (!existing.features.length) {
            existing.features = normaliseFeatureList(plan.features);
        }
        existing.is_popular = existing.is_popular || Boolean(plan.is_popular);
        grouped.set(key, existing);
    }

    return Array.from(grouped.values()).sort((left, right) => {
        if (left.is_popular !== right.is_popular) {
            return left.is_popular ? -1 : 1;
        }
        return left.name.localeCompare(right.name);
    });
};

const normaliseInvoice = (invoice = {}) => ({
    ...invoice,
    date: invoice.paid_at ?? invoice.due_date ?? invoice.created_at ?? '',
    amount: toNumber(invoice.amount_paid ?? invoice.amount_due) ?? invoice.amount_paid ?? invoice.amount_due ?? 0,
    status: invoice.status ?? 'unknown',
});

export const normaliseBillingOverview = (data = {}) => {
    const subscription = data.subscription ?? {};

    return {
        ...data,
        plan: {
            name: subscription.plan_name ?? 'Free',
            description: subscription.subscription_status
                ? `Subscription status: ${String(subscription.subscription_status).replace(/_/g, ' ')}`
                : 'Your current active plan.',
            next_invoice_date: subscription.current_period_end ?? null,
            price: null,
        },
        usage: Array.isArray(data.usage) ? data.usage : [],
        invoices: Array.isArray(data.invoices) ? data.invoices.map(normaliseInvoice) : [],
        payment_methods: Array.isArray(data.payment_methods) ? data.payment_methods : [],
        upcoming_charge: data.upcoming_charge ?? {},
    };
};

export const usePaymentStore = create((set) => ({
    // Plans
    plans: [],
    plansLoading: false,
    fetchPlans: async (audience) => {
        set({ plansLoading: true });
        try {
            const { data } = await paymentsService.getPlans(audience);
            set({
                plans: normalisePlanCatalog(data.results || data),
                plansLoading: false,
            });
        } catch {
            set({ plansLoading: false });
        }
    },

    // Billing
    billing: null,
    billingLoading: false,
    fetchBilling: async () => {
        set({ billingLoading: true });
        try {
            const { data } = await paymentsService.getBillingOverview();
            set({
                billing: normaliseBillingOverview(data),
                billingLoading: false,
            });
        } catch {
            set({ billingLoading: false });
        }
    },

    // Referrals
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

    // Sponsored Campaigns
    campaigns: [],
    campaignsLoading: false,
    fetchCampaigns: async (options = {}) => {
        set({ campaignsLoading: true });
        try {
            const { data } = await paymentsService.getSponsoredCampaigns(options);
            set({ campaigns: normaliseCampaigns(data), campaignsLoading: false });
        } catch (error) {
            set({ campaignsLoading: false });
            throw error;
        }
    },

    // Pipelines & Candidates (CRM)
    pipelines: [],
    pipelinesLoading: false,
    activePipeline: null,
    candidates: [],
    candidatesLoading: false,
    fetchPipelines: async () => {
        set({ pipelinesLoading: true });
        try {
            const { data } = await paymentsService.getPipelines();
            const pipelines = normalisePipelines(data);
            set((state) => ({
                pipelines,
                activePipeline: state.activePipeline
                    ? pipelines.find((pipeline) => pipeline.id === state.activePipeline.id) ?? state.activePipeline
                    : state.activePipeline,
                pipelinesLoading: false,
            }));
        } catch (error) {
            set({ pipelinesLoading: false });
            throw error;
        }
    },
    setActivePipeline: (pipeline) => set({ activePipeline: pipeline ? normalisePipeline(pipeline) : null }),
    fetchCandidates: async (pipelineId, stageId) => {
        set({ candidatesLoading: true });
        try {
            const { data } = await paymentsService.getCandidates(pipelineId, stageId);
            set({ candidates: normaliseCandidates(data), candidatesLoading: false });
        } catch (error) {
            set({ candidatesLoading: false });
            throw error;
        }
    },

    // Revenue (Admin)
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

