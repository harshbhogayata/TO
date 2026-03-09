import { beforeEach, describe, expect, it, vi } from 'vitest';

const { paymentsService } = vi.hoisted(() => ({
    paymentsService: {
        getPlans: vi.fn(),
        getBillingOverview: vi.fn(),
        getReferralProgram: vi.fn(),
        getReferralStats: vi.fn(),
        getMyReferrals: vi.fn(),
        getMyReferralRewards: vi.fn(),
        getSponsoredCampaigns: vi.fn(),
        getPipelines: vi.fn(),
        getCandidates: vi.fn(),
        getRevenueDashboard: vi.fn(),
        getRevenueTrend: vi.fn(),
    },
}));

vi.mock('../services/api', () => ({ paymentsService }));

import { usePaymentStore } from './paymentStore';

const resetStore = () => {
    usePaymentStore.setState({
        plans: [],
        plansLoading: false,
        billing: null,
        billingLoading: false,
        referralProgram: null,
        referralStats: null,
        referrals: [],
        rewards: [],
        referralLoading: false,
        campaigns: [],
        campaignsLoading: false,
        pipelines: [],
        pipelinesLoading: false,
        activePipeline: null,
        candidates: [],
        candidatesLoading: false,
        revenueMetrics: null,
        revenueTrend: [],
        revenueLoading: false,
    });
};

describe('paymentStore', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        resetStore();
    });

    it('normalises API plan rows into billing-toggle cards', async () => {
        paymentsService.getPlans.mockResolvedValue({
            data: [
                {
                    id: 'plan_monthly',
                    name: 'Professional',
                    slug: 'professional-monthly',
                    audience: 'COMPANY',
                    billing_interval: 'monthly',
                    price: '299.00',
                    features: ['Unlimited jobs', 'Priority support'],
                    is_popular: true,
                },
                {
                    id: 'plan_yearly',
                    name: 'Professional',
                    slug: 'professional-yearly',
                    audience: 'COMPANY',
                    billing_interval: 'yearly',
                    price: '2388.00',
                    features: ['Unlimited jobs', 'Priority support'],
                    is_popular: true,
                },
            ],
        });

        await usePaymentStore.getState().fetchPlans('COMPANY');

        expect(paymentsService.getPlans).toHaveBeenCalledWith('COMPANY');
        expect(usePaymentStore.getState().plans).toEqual([
            {
                id: 'COMPANY:Professional',
                name: 'Professional',
                slug: 'professional-monthly',
                audience: 'COMPANY',
                monthly_price: 299,
                annual_price: 199,
                monthly_plan_id: 'plan_monthly',
                annual_plan_id: 'plan_yearly',
                checkout_plan: 'Professional',
                is_current: false,
                is_popular: true,
                cta: 'Select Plan',
                cta_style: 'primary',
                features: [
                    { label: 'Unlimited jobs', included: true },
                    { label: 'Priority support', included: true },
                ],
            },
        ]);
    });

    it('normalises billing overview data for the billing page contract', async () => {
        paymentsService.getBillingOverview.mockResolvedValue({
            data: {
                subscription: {
                    plan_name: 'Premium Pro',
                    subscription_status: 'active',
                    current_period_end: '2026-04-01T00:00:00Z',
                },
                payment_history: [],
                invoices: [
                    {
                        id: 'inv_1',
                        number: 'INV-001',
                        status: 'paid',
                        amount_due: '19.00',
                        due_date: '2026-04-01',
                    },
                ],
            },
        });

        await usePaymentStore.getState().fetchBilling();

        expect(usePaymentStore.getState().billing).toMatchObject({
            plan: {
                name: 'Premium Pro',
                description: 'Subscription status: active',
                next_invoice_date: '2026-04-01T00:00:00Z',
                price: null,
            },
            usage: [],
            payment_methods: [],
            upcoming_charge: {},
            invoices: [
                {
                    id: 'inv_1',
                    date: '2026-04-01',
                    amount: 19,
                    status: 'paid',
                },
            ],
        });
    });
});
