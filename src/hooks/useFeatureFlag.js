/**
 * src/hooks/useFeatureFlag.js
 * React hook for evaluating PostHog feature flags via the intelligence API.
 *
 * Usage:
 *   const isEnabled = useFeatureFlag('new-recommendation-ui');
 *   const variant   = useFeatureFlag('onboarding-flow'); // 'control' | 'variant-a' | …
 */
import { useState, useEffect } from 'react';
import { intelligenceService } from '../services/api';
import { useAuthStore } from '../store/authStore';

export const flagsCache = { data: null, ts: 0 };
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export function useFeatureFlag(key) {
    const [value, setValue] = useState(false);
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    useEffect(() => {
        if (!isAuthenticated) return;

        const now = Date.now();
        if (flagsCache.data && now - flagsCache.ts < CACHE_TTL) {
            setValue(flagsCache.data[key] ?? false);
            return;
        }

        let cancelled = false;
        intelligenceService.getFeatureFlags()
            .then(({ data }) => {
                if (cancelled) return;
                flagsCache.data = data.flags || {};
                flagsCache.ts = Date.now();
                setValue(flagsCache.data[key] ?? false);
            })
            .catch(() => {
                if (!cancelled) setValue(false);
            });

        return () => { cancelled = true; };
    }, [key, isAuthenticated]);

    return value;
}

export default useFeatureFlag;
