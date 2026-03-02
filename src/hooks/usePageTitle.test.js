import { describe, it, expect, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import usePageTitle from './usePageTitle';

describe('usePageTitle', () => {
    afterEach(() => {
        document.title = '';
        document.querySelectorAll('meta[name="description"], meta[property^="og:"]')
            .forEach(el => el.remove());
    });

    it('sets document title with TalentOrbit suffix', () => {
        renderHook(() => usePageTitle('Job Board'));
        expect(document.title).toBe('Job Board — TalentOrbit');
    });

    it('falls back to just TalentOrbit when no title provided', () => {
        renderHook(() => usePageTitle(''));
        expect(document.title).toBe('TalentOrbit');
    });

    it('sets meta description when provided', () => {
        renderHook(() => usePageTitle('Jobs', 'Browse open positions'));
        const meta = document.querySelector('meta[name="description"]');
        expect(meta).not.toBeNull();
        expect(meta.getAttribute('content')).toBe('Browse open positions');
    });

    it('sets Open Graph tags when description is provided', () => {
        renderHook(() => usePageTitle('Jobs', 'Browse open positions'));
        expect(document.querySelector('meta[property="og:title"]')?.getAttribute('content'))
            .toBe('Jobs — TalentOrbit');
        expect(document.querySelector('meta[property="og:description"]')?.getAttribute('content'))
            .toBe('Browse open positions');
        expect(document.querySelector('meta[property="og:type"]')?.getAttribute('content'))
            .toBe('website');
        expect(document.querySelector('meta[property="og:site_name"]')?.getAttribute('content'))
            .toBe('TalentOrbit');
    });

    it('cleans up title on unmount', () => {
        document.title = 'Original';
        const { unmount } = renderHook(() => usePageTitle('Test'));
        expect(document.title).toBe('Test — TalentOrbit');
        unmount();
        // After unmount, title should be restored
        expect(document.title).toBe('Original');
    });
});
