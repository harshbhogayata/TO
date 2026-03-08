/**
 * src/store/authStore.js
 * Zustand global auth state.
 * Handles token persistence to localStorage and a clean logout action.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useAuthStore = create(
    persist(
        (set, get) => ({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
            isLoading: false,

            setAuth: (user, accessToken, refreshToken) => set({
                user,
                accessToken,
                refreshToken,
                isAuthenticated: true,
                isLoading: false,
            }),

            setTokens: (accessToken, refreshToken) => set({
                accessToken,
                refreshToken,
                isAuthenticated: true,
            }),

            setUser: (user) => set({ user }),

            logout: () => set({
                user: null,
                accessToken: null,
                refreshToken: null,
                isAuthenticated: false,
                isLoading: false,
            }),

            setLoading: (isLoading) => set({ isLoading }),

            // Computed helpers
            isCompany: () => get().user?.role === 'COMPANY',
            isTalent: () => get().user?.role === 'TALENT',
            isAdmin: () => get().user?.role === 'ADMIN',
        }),
        {
            name: 'talentorbit-auth',
            // accessToken intentionally excluded; memory-only for XSS protection
            partialize: (state) => ({
                user: state.user,
                refreshToken: state.refreshToken,
                isAuthenticated: state.isAuthenticated,
            }),
        }
    )
);