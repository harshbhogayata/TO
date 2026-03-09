import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const { getResult } = vi.hoisted(() => ({
    getResult: vi.fn(),
}));

vi.mock('../layouts/DashboardLayout', () => ({
    default: ({ children }) => <div>{children}</div>,
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
        getResult,
    },
}));

import AssessmentResults from './AssessmentResults';
import { useAssessmentStore } from '../store/assessmentStore';

const resetAssessmentStore = () => {
    useAssessmentStore.setState({
        activeResult: null,
        myResults: [],
        badges: [],
        invitations: [],
    });
};

describe('AssessmentResults', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        resetAssessmentStore();
    });

    it('renders the repaired assessment result contract using the attempt result endpoint', async () => {
        getResult.mockResolvedValue({
            data: {
                id: 'result-1',
                percentage_score: 84.4,
                passed: true,
                questions_correct: 4,
                questions_incorrect: 1,
                questions_partial: 0,
                questions_skipped: 0,
                total_time_seconds: 620,
                percentile_rank: 91.2,
                passing_score: 70,
                skill_scores: {
                    Python: 92,
                },
                answers: [
                    {
                        question_id: 11,
                        question_text: 'What is Python?',
                        is_correct: true,
                        user_answer: 'A programming language',
                    },
                ],
                badge: {
                    id: 'badge-1',
                    name: 'Python Verified',
                },
            },
        });

        render(
            <MemoryRouter initialEntries={['/assessments/55/results/attempt-123']}>
                <Routes>
                    <Route path="/assessments/:assessmentId/results/:resultId" element={<AssessmentResults />} />
                </Routes>
            </MemoryRouter>,
        );

        await waitFor(() => {
            expect(getResult).toHaveBeenCalledWith('attempt-123');
        });

        expect(await screen.findByText('84%')).toBeTruthy();
        expect(screen.getByText('4 / 5')).toBeTruthy();
        expect(screen.getByText('Python')).toBeTruthy();
        expect(screen.getByText('What is Python?')).toBeTruthy();
        expect(screen.getByText('Badge Earned')).toBeTruthy();
    });

    it('shows a grading-pending state when the result is not available yet', async () => {
        getResult.mockRejectedValue({
            response: { status: 404 },
            message: 'Result not found',
        });

        render(
            <MemoryRouter initialEntries={['/assessments/55/results/attempt-123']}>
                <Routes>
                    <Route path="/assessments/:assessmentId/results/:resultId" element={<AssessmentResults />} />
                </Routes>
            </MemoryRouter>,
        );

        expect(await screen.findByText('Results Pending')).toBeTruthy();
        expect(screen.getByText(/still being graded/i)).toBeTruthy();
    });
});
