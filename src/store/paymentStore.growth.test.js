import { beforeEach, describe, expect, it, vi } from 'vitest';

const { paymentsService } = vi.hoisted(() => ({
    paymentsService: {
        getSponsoredCampaigns: vi.fn(),
        getPipelines: vi.fn(),
        getCandidates: vi.fn(),
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

describe('paymentStore growth workflow', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        resetStore();
    });

    it('normalises sponsored campaigns into the page contract', async () => {
        paymentsService.getSponsoredCampaigns.mockResolvedValue({
            data: [
                {
                    id: 'campaign_1',
                    job_title: 'Frontend Lead',
                    amount_spent: '310.50',
                    applications: 22,
                    impressions: '8100',
                    clicks: '510',
                    status: 'ACTIVE',
                },
            ],
        });

        await usePaymentStore.getState().fetchCampaigns();

        expect(usePaymentStore.getState().campaigns).toEqual([
            expect.objectContaining({
                id: 'campaign_1',
                job_title: 'Frontend Lead',
                name: 'Frontend Lead',
                spend: 310.5,
                applications: 22,
                apps: 22,
                impressions: 8100,
                clicks: 510,
                status: 'active',
            }),
        ]);
    });

    it('normalises pipeline stages from backend labels', async () => {
        paymentsService.getPipelines.mockResolvedValue({
            data: [
                {
                    id: 'pipeline_1',
                    name: 'Design Hiring',
                    stages: [
                        { id: 'sourced', label: 'Sourced', color: '#94A3B8' },
                        { id: 'screening', label: 'Screening', color: '#60A5FA' },
                    ],
                },
            ],
        });

        await usePaymentStore.getState().fetchPipelines();

        expect(usePaymentStore.getState().pipelines).toEqual([
            expect.objectContaining({
                id: 'pipeline_1',
                name: 'Design Hiring',
                stages: [
                    expect.objectContaining({
                        id: 'sourced',
                        label: 'Sourced',
                        name: 'Sourced',
                    }),
                    expect.objectContaining({
                        id: 'screening',
                        label: 'Screening',
                        name: 'Screening',
                    }),
                ],
            }),
        ]);
    });

    it('normalises CRM candidates from display-name payloads', async () => {
        paymentsService.getCandidates.mockResolvedValue({
            data: [
                {
                    id: 'candidate_1',
                    display_name: 'Alex Rivera',
                    stage_id: 'sourced',
                    rating: 4,
                    source: 'import',
                },
            ],
        });

        await usePaymentStore.getState().fetchCandidates('pipeline_1');

        expect(usePaymentStore.getState().candidates).toEqual([
            expect.objectContaining({
                id: 'candidate_1',
                name: 'Alex Rivera',
                stage_id: 'sourced',
                score_display: '4/5',
                source_label: 'Import',
            }),
        ]);
    });

    it('rethrows campaign loading failures so page error states can render', async () => {
        const error = new Error('Campaign API offline');
        paymentsService.getSponsoredCampaigns.mockRejectedValue(error);

        await expect(usePaymentStore.getState().fetchCampaigns()).rejects.toThrow('Campaign API offline');
        expect(usePaymentStore.getState().campaignsLoading).toBe(false);
    });
});
