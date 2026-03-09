import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const {
    fetchPlans,
    createCheckoutSession,
    addToast,
    usePaymentStoreMock,
    useAuthStoreMock,
    useToastMock,
} = vi.hoisted(() => ({
    fetchPlans: vi.fn(),
    createCheckoutSession: vi.fn(),
    addToast: vi.fn(),
    usePaymentStoreMock: vi.fn(),
    useAuthStoreMock: vi.fn(),
    useToastMock: vi.fn(),
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
vi.mock('../store/paymentStore', () => ({
    usePaymentStore: usePaymentStoreMock,
}));
vi.mock('../store/authStore', () => ({
    useAuthStore: useAuthStoreMock,
}));
vi.mock('../contexts/ToastContext', () => ({
    useToast: useToastMock,
}));
vi.mock('../services/api', () => ({
    getApiErrorMessage: vi.fn((error, fallback) => error?.message || fallback),
    paymentsService: {
        createCheckoutSession,
    },
}));

import SubscriptionPlans from './SubscriptionPlans';

describe('SubscriptionPlans', () => {
    const originalLocation = window.location;

    beforeEach(() => {
        vi.clearAllMocks();
        fetchPlans.mockResolvedValue(undefined);
        createCheckoutSession.mockResolvedValue({
            data: { url: 'https://checkout.stripe.com/test-session' },
        });
        usePaymentStoreMock.mockReturnValue({
            plans: [
                {
                    id: 'COMPANY:Professional',
                    name: 'Professional',
                    monthly_price: 299,
                    annual_price: 199,
                    monthly_plan_id: 'plan_monthly',
                    annual_plan_id: 'plan_yearly',
                    is_current: false,
                    features: [],
                },
            ],
            plansLoading: false,
            fetchPlans,
        });
        useAuthStoreMock.mockImplementation((selector) => selector({
            user: { role: 'COMPANY' },
        }));
        useToastMock.mockReturnValue({ addToast });
        Object.defineProperty(window, 'location', {
            configurable: true,
            value: { assign: vi.fn() },
        });
    });

    afterEach(() => {
        Object.defineProperty(window, 'location', {
            configurable: true,
            value: originalLocation,
        });
    });

    it('starts checkout for the selected interval-specific plan id', async () => {
        render(<SubscriptionPlans />);

        await waitFor(() => {
            expect(fetchPlans).toHaveBeenCalledWith('COMPANY');
        });

        fireEvent.click(screen.getByLabelText(/select/i));
        fireEvent.click(screen.getByRole('button', { name: 'Select Plan' }));

        await waitFor(() => {
            expect(createCheckoutSession).toHaveBeenCalledWith(undefined, 'plan_yearly', undefined);
        });

        expect(addToast).toHaveBeenCalledWith('Redirecting to secure checkout.', 'info');
        expect(window.location.assign).toHaveBeenCalledWith('https://checkout.stripe.com/test-session');
    });
});
