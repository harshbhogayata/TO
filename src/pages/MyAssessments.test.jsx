import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const { myResults, myInvitations, myBadges } = vi.hoisted(() => ({
    myResults: vi.fn(),
    myInvitations: vi.fn(),
    myBadges: vi.fn(),
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
vi.mock('../services/api', () => ({
    getApiErrorMessage: vi.fn((error, fallback) => error?.message || fallback),
}));
vi.mock('../services/assessmentService', () => ({
    default: {
        myResults,
        myInvitations,
        myBadges,
    },
}));

import MyAssessments from './MyAssessments';
import { useAssessmentStore } from '../store/assessmentStore';

const resetAssessmentStore = () => {
    useAssessmentStore.setState({
        activeResult: null,
        myResults: [],
        badges: [],
        invitations: [],
    });
};

describe('MyAssessments', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        resetAssessmentStore();
        myResults.mockResolvedValue({
            data: {
                results: [
                    {
                        id: 'result-1',
                        attempt_id: 'attempt-123',
                        assessment: 17,
                        assessment_title: 'Backend Screen',
                        percentage_score: 84,
                        passed: true,
                        graded_at: '2026-03-08T12:00:00Z',
                    },
                ],
            },
        });
        myInvitations.mockResolvedValue({ data: [] });
        myBadges.mockResolvedValue({ data: [] });
    });

    it('links result cards to the attempt-based result route instead of the result id', async () => {
        render(
            <MemoryRouter initialEntries={['/my-assessments']}>
                <Routes>
                    <Route path="/my-assessments" element={<MyAssessments />} />
                </Routes>
            </MemoryRouter>,
        );

        expect(await screen.findByText('Backend Screen')).toBeTruthy();

        const detailLink = screen.getByRole('link', { name: /view details/i });
        expect(detailLink.getAttribute('href')).toBe('/assessments/17/results/attempt-123');
    });
});
