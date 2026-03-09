import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const {
    getAttempt,
    submitAnswer,
    finalSubmit,
    reportProctorEvent,
} = vi.hoisted(() => ({
    getAttempt: vi.fn(),
    submitAnswer: vi.fn(),
    finalSubmit: vi.fn(),
    reportProctorEvent: vi.fn(),
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
        getAttempt,
        submitAnswer,
        finalSubmit,
        reportProctorEvent,
    },
}));

import AssessmentPlayer from './AssessmentPlayer';
import { useAssessmentStore } from '../store/assessmentStore';

const resetAssessmentStore = () => {
    useAssessmentStore.setState({
        activeAssessment: null,
        attempt: null,
        currentQuestionIndex: 0,
        answers: {},
        flagged: {},
        timeRemaining: 0,
        activeResult: null,
        myResults: [],
        badges: [],
        invitations: [],
    });
};

describe('AssessmentPlayer', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        resetAssessmentStore();
        getAttempt.mockResolvedValue({
            data: {
                id: 'attempt-123',
                status: 'submitted',
                time_remaining_seconds: 900,
                questions: [
                    {
                        id: 11,
                        section_index: 0,
                        question_type: 'mcq',
                        question_text: 'What is Python?',
                        options: [
                            { id: 1, text: 'A programming language' },
                            { id: 2, text: 'A database' },
                        ],
                    },
                ],
                answers: {},
                flagged_question_ids: [],
            },
        });
        submitAnswer.mockResolvedValue({ data: { ok: true } });
        finalSubmit.mockResolvedValue({ data: { attempt_id: 'attempt-123' } });
        reportProctorEvent.mockResolvedValue({ data: { ok: true } });
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        vi.spyOn(window, 'alert').mockImplementation(() => {});
    });

    it('loads and submits answers using the attempt id route contract', async () => {
        render(
            <MemoryRouter initialEntries={['/assessments/assessment-55/attempt/attempt-123']}>
                <Routes>
                    <Route path="/assessments/:assessmentId/attempt/:attemptId" element={<AssessmentPlayer />} />
                </Routes>
            </MemoryRouter>,
        );

        await waitFor(() => {
            expect(getAttempt).toHaveBeenCalledWith('attempt-123');
        });

        fireEvent.click(screen.getByText('A programming language'));

        await waitFor(() => {
            expect(submitAnswer).toHaveBeenCalledWith(
                'attempt-123',
                expect.objectContaining({
                    question_id: 11,
                    selected_option_ids: [1],
                    is_bookmarked: false,
                }),
            );
        });
    });
});
