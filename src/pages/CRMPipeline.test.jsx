import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const {
    paymentsService,
    useToastMock,
} = vi.hoisted(() => ({
    paymentsService: {
        getPipelines: vi.fn(),
        getCandidates: vi.fn(),
        moveCandidate: vi.fn(),
    },
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
    default: () => <div>loading</div>,
}));
vi.mock('../contexts/ToastContext', () => ({
    useToast: useToastMock,
}));
vi.mock('../services/api', () => ({
    paymentsService,
    getApiErrorMessage: vi.fn((error, fallback) => error?.message || fallback),
}));

import CRMPipeline from './CRMPipeline';
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

describe('CRMPipeline', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        resetStore();
        useToastMock.mockReturnValue({ addToast: vi.fn() });
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
        paymentsService.moveCandidate.mockResolvedValue({ data: {} });
    });

    it('renders backend stage labels and candidate display names correctly', async () => {
        render(<CRMPipeline />);

        expect(await screen.findByText('Sourced')).toBeTruthy();
        expect(await screen.findByText('Alex Rivera')).toBeTruthy();
        expect(screen.getByText('4/5')).toBeTruthy();
    });
});

