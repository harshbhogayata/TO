/**
 * src/hooks/useExperiment.js
 * React hook for running A/B experiments with automatic event tracking.
 *
 * Usage:
 *   const { variant, track } = useExperiment('rec-algorithm');
 *   // variant = 'control' | 'variant-a' | …
 *   // track('clicked_recommendation', { job_id: 42 })
 */
import { useState, useEffect, useCallback } from 'react';
import { intelligenceService } from '../services/api';
import { useAuthStore } from '../store/authStore';
import { flagsCache } from './useFeatureFlag';

const CACHE_TTL = 5 * 60 * 1000;

export function useExperiment(experimentKey) {
    const [variant, setVariant] = useState('control');
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    useEffect(() => {
        if (!isAuthenticated) return;

        const now = Date.now();
        if (flagsCache.data && now - flagsCache.ts < CACHE_TTL) {
            const v = flagsCache.data[experimentKey];
            setVariant(typeof v === 'string' ? v : v ? 'treatment' : 'control');
            return;
        }

        let cancelled = false;
        intelligenceService.getFeatureFlags()
            .then(({ data }) => {
                if (cancelled) return;
                flagsCache.data = data.flags || {};
                flagsCache.ts = Date.now();
                const v = flagsCache.data[experimentKey];
                setVariant(typeof v === 'string' ? v : v ? 'treatment' : 'control');
            })
            .catch(() => {
                if (!cancelled) setVariant('control');
            });

        return () => { cancelled = true; };
    }, [experimentKey, isAuthenticated]);

    const track = useCallback(
        (event, properties = {}) => {
            intelligenceService.trackExperimentEvent(
                event,
                properties,
                experimentKey,
                variant,
            ).catch(() => { /* fire-and-forget */ });
        },
        [experimentKey, variant],
    );

    return { variant, track };
}

export default useExperiment;
