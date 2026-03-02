import { describe, it, expect } from 'vitest';
import { useAuthStore } from './authStore';

describe('authStore', () => {
    // Reset store state before each test
    const initialState = useAuthStore.getState();
    afterEach(() => {
        useAuthStore.setState(initialState, true);
    });

    it('starts with unauthenticated state', () => {
        const { isAuthenticated, user, accessToken, refreshToken } = useAuthStore.getState();
        expect(isAuthenticated).toBe(false);
        expect(user).toBeNull();
        expect(accessToken).toBeNull();
        expect(refreshToken).toBeNull();
    });

    it('setAuth sets user, tokens, and isAuthenticated', () => {
        const mockUser = { id: 1, email: 'test@example.com', role: 'TALENT' };
        useAuthStore.getState().setAuth(mockUser, 'access123', 'refresh456');

        const state = useAuthStore.getState();
        expect(state.isAuthenticated).toBe(true);
        expect(state.user).toEqual(mockUser);
        expect(state.accessToken).toBe('access123');
        expect(state.refreshToken).toBe('refresh456');
    });

    it('setTokens updates only tokens', () => {
        const mockUser = { id: 1, email: 'test@example.com', role: 'TALENT' };
        useAuthStore.getState().setAuth(mockUser, 'old_access', 'old_refresh');
        useAuthStore.getState().setTokens('new_access', 'new_refresh');

        const state = useAuthStore.getState();
        expect(state.accessToken).toBe('new_access');
        expect(state.refreshToken).toBe('new_refresh');
        expect(state.user).toEqual(mockUser);  // user unchanged
    });

    it('logout clears everything', () => {
        useAuthStore.getState().setAuth({ id: 1 }, 'a', 'r');
        useAuthStore.getState().logout();

        const state = useAuthStore.getState();
        expect(state.isAuthenticated).toBe(false);
        expect(state.user).toBeNull();
        expect(state.accessToken).toBeNull();
        expect(state.refreshToken).toBeNull();
    });

    it('setUser updates only the user object', () => {
        const user1 = { id: 1, full_name: 'Alice' };
        const user2 = { id: 1, full_name: 'Alice Updated' };
        useAuthStore.getState().setAuth(user1, 'a', 'r');
        useAuthStore.getState().setUser(user2);

        expect(useAuthStore.getState().user.full_name).toBe('Alice Updated');
        expect(useAuthStore.getState().accessToken).toBe('a'); // unchanged
    });

    it('role helpers return correct booleans', () => {
        useAuthStore.getState().setAuth({ role: 'COMPANY' }, 'a', 'r');
        expect(useAuthStore.getState().isCompany()).toBe(true);
        expect(useAuthStore.getState().isTalent()).toBe(false);
        expect(useAuthStore.getState().isAdmin()).toBe(false);

        useAuthStore.getState().setAuth({ role: 'ADMIN' }, 'a', 'r');
        expect(useAuthStore.getState().isAdmin()).toBe(true);
    });
});
