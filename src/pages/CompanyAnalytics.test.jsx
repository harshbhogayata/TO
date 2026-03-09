import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const {
    intelligenceService,
    useAuthStoreMock,
    useToastMock,
} = vi.hoisted(() => ({
    intelligenceService: {
        getAnalyticsOverview: vi.fn(),
        getAnalyticsFunnel: vi.fn(),
        getJobPerformance: vi.fn(),
        getBenchmarks: vi.fn(),
    },
    useAuthStoreMock: vi.fn(),
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
vi.mock('../components/VerticalLabel', () => ({
    default: ({ text }) => <div>{text}</div>,
}));
vi.mock('../components/Skeleton', () => ({
    default: Object.assign(
        () => <div>loading</div>,
        {
            Stat: () => <div>loading stat</div>,
            List: () => <div>loading list</div>,
        },
    ),
}));
vi.mock('../store/authStore', () => ({
    useAuthStore: useAuthStoreMock,
}));
vi.mock('../contexts/ToastContext', () => ({
    useToast: useToastMock,
}));
vi.mock('../hooks/usePageTitle', () => ({
    default: vi.fn(),
}));
vi.mock('../services/api', () => ({
    intelligenceService,
    getApiErrorMessage: vi.fn((error, fallback) => error?.message || fallback),
}));

import CompanyAnalytics from './CompanyAnalytics';

describe('CompanyAnalytics', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useAuthStoreMock.mockReturnValue({
            user: {
                company_name: 'Orbit Labs',
                email: 'ops@orbitlabs.test',
            },
        });
        useToastMock.mockReturnValue({ addToast: vi.fn() });
        intelligenceService.getAnalyticsOverview.mockResolvedValue({
            data: {
                total_views: 8100,
                total_applications: 22,
                application_change: 12.4,
                active_jobs: 3,
                total_jobs: 5,
            },
        });
        intelligenceService.getAnalyticsFunnel.mockResolvedValue({
            data: {
                stages: [
                    { name: 'Applied', count: 22, conversion_rate: 100 },
                    { name: 'Interview', count: 5, conversion_rate: 22.7 },
                ],
            },
        });
        intelligenceService.getJobPerformance.mockResolvedValue({
            data: {
                results: [
                    {
                        id: 1,
                        title: 'Frontend Lead',
                        views: 8100,
                        applications: 22,
                        shortlisted: 5,
                        health: 'healthy',
                    },
                ],
            },
        });
        intelligenceService.getBenchmarks.mockResolvedValue({
            data: {
                results: [
                    {
                        name: 'Apply Rate',
                        your_value: 2.4,
                        platform_avg: 1.8,
                        industry_avg: 2.0,
                        sample_size: 150,
                    },
                ],
            },
        });
    });

    it('renders company analytics data when benchmark rows arrive in a results envelope', async () => {
        render(<CompanyAnalytics />);

        expect(await screen.findByText('Frontend Lead')).toBeTruthy();
        expect(screen.getByText('Applied: 22 (100%)')).toBeTruthy();
        expect(screen.getByText('Apply Rate')).toBeTruthy();
    });
});

