import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

const { listEnrollments, myCertificates } = vi.hoisted(() => ({
    listEnrollments: vi.fn(),
    myCertificates: vi.fn(),
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
vi.mock('../services/courseService', () => ({
    default: {
        listEnrollments,
        myCertificates,
    },
}));
vi.mock('../services/api', () => ({
    getApiErrorMessage: vi.fn((error, fallback) => error?.message || fallback),
}));

import MyLearning from './MyLearning';
import { useCourseStore } from '../store/courseStore';

const resetCourseStore = () => {
    useCourseStore.setState({
        activeCourse: null,
        activeLesson: null,
        courseProgress: null,
        enrollments: [],
        certificates: [],
        lessonProgress: {},
        reviews: [],
    });
};

const LocationDisplay = () => {
    const location = useLocation();
    return <div data-testid="location">{location.pathname}{location.search}</div>;
};

describe('MyLearning', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        resetCourseStore();
        listEnrollments.mockResolvedValue({ data: [] });
        myCertificates.mockResolvedValue({ data: [] });
    });

    it('honours the certificates tab from the query string on first load', async () => {
        myCertificates.mockResolvedValue({
            data: [
                {
                    id: 'cert-1',
                    course_title: 'Python Path',
                    issued_at: '2026-03-09T00:00:00Z',
                    certificate_id: 'CERT-001',
                },
            ],
        });

        render(
            <MemoryRouter initialEntries={['/my-learning?tab=certificates']}>
                <Routes>
                    <Route path="/my-learning" element={<><MyLearning /><LocationDisplay /></>} />
                    <Route path="/certificates/:certId" element={<LocationDisplay />} />
                </Routes>
            </MemoryRouter>,
        );

        expect(await screen.findByText('Python Path')).toBeTruthy();
        expect(screen.getByTestId('location').textContent).toBe('/my-learning?tab=certificates');
    });

    it('continues an active enrollment from the last lesson slug instead of the course overview', async () => {
        listEnrollments.mockResolvedValue({
            data: [
                {
                    id: 1,
                    status: 'active',
                    course_title: 'Python Path',
                    course_slug: 'python-path',
                    progress_percentage: 35,
                    last_lesson_slug: 'control-flow',
                    course_thumbnail: 'https://example.com/thumb.png',
                },
            ],
        });

        render(
            <MemoryRouter initialEntries={['/my-learning']}>
                <Routes>
                    <Route path="/my-learning" element={<><MyLearning /><LocationDisplay /></>} />
                    <Route path="/courses/:courseId/lessons/:lessonId" element={<LocationDisplay />} />
                    <Route path="/courses/:courseId/progress" element={<LocationDisplay />} />
                </Routes>
            </MemoryRouter>,
        );

        expect(await screen.findByText('Python Path')).toBeTruthy();

        fireEvent.click(screen.getByText('Python Path'));

        await waitFor(() => {
            expect(screen.getByTestId('location').textContent).toBe('/courses/python-path/lessons/control-flow');
        });
    });
});
