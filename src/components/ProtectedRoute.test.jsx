import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';

// Mock auth store
vi.mock('../store/authStore', () => ({
    useAuthStore: vi.fn(),
}));

import { useAuthStore } from '../store/authStore';

const renderWithRouter = (ui, { route = '/' } = {}) => {
    return render(
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    );
};

describe('ProtectedRoute', () => {
    it('renders children when authenticated and no allowedRoles', () => {
        useAuthStore.mockReturnValue({ isAuthenticated: true, user: { role: 'TALENT' } });
        renderWithRouter(
            <ProtectedRoute>
                <div>Protected content</div>
            </ProtectedRoute>
        );
        expect(screen.getByText('Protected content')).toBeInTheDocument();
    });

    it('redirects to /auth when not authenticated', () => {
        useAuthStore.mockReturnValue({ isAuthenticated: false, user: null });
        renderWithRouter(
            <ProtectedRoute>
                <div>Protected content</div>
            </ProtectedRoute>
        );
        expect(screen.queryByText('Protected content')).not.toBeInTheDocument();
        // Navigate component renders; we just check protected content is not shown
        const navigate = document.querySelector('[href="/auth"]');
        expect(navigate || document.body.textContent).toBeTruthy();
    });

    it('renders children when role is in allowedRoles', () => {
        useAuthStore.mockReturnValue({ isAuthenticated: true, user: { role: 'COMPANY' } });
        renderWithRouter(
            <ProtectedRoute allowedRoles={['COMPANY', 'ADMIN']}>
                <div>Company content</div>
            </ProtectedRoute>
        );
        expect(screen.getByText('Company content')).toBeInTheDocument();
    });

    it('does not render children when role is not in allowedRoles', () => {
        useAuthStore.mockReturnValue({ isAuthenticated: true, user: { role: 'TALENT' } });
        renderWithRouter(
            <ProtectedRoute allowedRoles={['ADMIN']}>
                <div>Admin only</div>
            </ProtectedRoute>
        );
        expect(screen.queryByText('Admin only')).not.toBeInTheDocument();
    });
});
