import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';

vi.mock('../store/authStore', () => ({
    useAuthStore: vi.fn(),
}));

import { useAuthStore } from '../store/authStore';

const renderProtectedRoute = ({
    authState,
    allowedRoles,
    route = '/protected',
    content = 'Protected content',
}) => {
    useAuthStore.mockReturnValue(authState);

    return render(
        <MemoryRouter initialEntries={[route]}>
            <Routes>
                <Route path="/auth" element={<div>Auth page</div>} />
                <Route path="/user" element={<div>User dashboard</div>} />
                <Route path="/company" element={<div>Company dashboard</div>} />
                <Route path="/admin" element={<div>Admin dashboard</div>} />
                <Route
                    path="*"
                    element={(
                        <ProtectedRoute allowedRoles={allowedRoles}>
                            <div>{content}</div>
                        </ProtectedRoute>
                    )}
                />
            </Routes>
        </MemoryRouter>
    );
};

describe('ProtectedRoute', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders children when authenticated and no allowedRoles', () => {
        renderProtectedRoute({
            authState: { isAuthenticated: true, isLoading: false, user: { role: 'TALENT' } },
        });

        expect(screen.getByText('Protected content')).toBeTruthy();
    });

    it('redirects to /auth when not authenticated', () => {
        renderProtectedRoute({
            authState: { isAuthenticated: false, isLoading: false, user: null },
        });

        expect(screen.queryByText('Protected content')).toBeNull();
        expect(screen.getByText('Auth page')).toBeTruthy();
    });

    it('renders children when role is in allowedRoles', () => {
        renderProtectedRoute({
            authState: { isAuthenticated: true, isLoading: false, user: { role: 'COMPANY' } },
            allowedRoles: ['COMPANY', 'ADMIN'],
            content: 'Company content',
        });

        expect(screen.getByText('Company content')).toBeTruthy();
    });

    it('redirects authenticated users with the wrong role to their dashboard', () => {
        renderProtectedRoute({
            authState: { isAuthenticated: true, isLoading: false, user: { role: 'TALENT' } },
            allowedRoles: ['ADMIN'],
            content: 'Admin only',
        });

        expect(screen.queryByText('Admin only')).toBeNull();
        expect(screen.getByText('User dashboard')).toBeTruthy();
    });
});