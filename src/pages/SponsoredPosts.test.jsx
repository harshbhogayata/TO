import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const {
    paymentsService,
    addToast,
    useToastMock,
} = vi.hoisted(() => ({
    paymentsService: {
        getSponsoredCampaigns: vi.fn(),
        createSponsoredCampaign: vi.fn(),
    },
    addToast: vi.fn(),
    useToastMock: vi.fn(),
}));

vi.mock('../layouts/DashboardLayout', () => ({
    default: ({ children, headerRightContent }) => (
        <div>
            <div>{headerRightContent}</div>
            {children}
        </div>
    ),
}));
vi.mock('../hooks/usePageTitle', () => ({
    default: vi.fn(),
}));
vi.mock('../components/Skeleton', () => ({
    default: Object.assign(
        () => <div>loading</div>,
        {
            List: () => <div>loading list</div>,
            Card: () => <div>loading card</div>,
            Text: () => <div>loading text</div>,
        },
    ),
}));
vi.mock('../contexts/ToastContext', () => ({
    useToast: useToastMock,
}));
vi.mock('../services/api', () => ({
    paymentsService,
    getApiErrorMessage: vi.fn((error, fallback) => error?.message || fallback),
}));

import SponsoredPosts from './SponsoredPosts';
import { usePaymentStore } from '../store/paymentStore';

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

describe('SponsoredPosts', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        resetStore();
        useToastMock.mockReturnValue({ addToast });
        paymentsService.createSponsoredCampaign.mockResolvedValue({ data: {} });
        paymentsService.getSponsoredCampaigns.mockResolvedValue({
            data: [
                {
                    id: 'campaign_1',
                    job_title: 'Frontend Lead',
                    amount_spent: '310.50',
                    applications: 22,
                    impressions: 8100,
                    clicks: 510,
                    status: 'active',
                },
            ],
        });
    });

    it('renders campaign spend totals from backend amount_spent values', async () => {
        render(<SponsoredPosts />);

        expect(await screen.findByText('Frontend Lead')).toBeTruthy();
        expect(screen.getByText('$310.50 MTD')).toBeTruthy();
        expect(screen.getAllByText('$310.50')).toHaveLength(1);
    });

    it('shows the page-level error state when campaign loading fails', async () => {
        paymentsService.getSponsoredCampaigns.mockRejectedValue(new Error('Campaign API offline'));

        render(<SponsoredPosts />);

        expect(await screen.findByText('Unable to load campaign data')).toBeTruthy();
        expect(screen.getByText('Campaign API offline')).toBeTruthy();
        await waitFor(() => {
            expect(addToast).toHaveBeenCalledWith('Campaign API offline', 'error');
        });
    });
});

