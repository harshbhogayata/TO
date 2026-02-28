import { describe, it, expect } from 'vitest';
import { getApiErrorMessage } from './api';

describe('getApiErrorMessage', () => {
    it('returns detail string from response data', () => {
        const err = { response: { data: { detail: 'Invalid credentials.' } } };
        expect(getApiErrorMessage(err)).toBe('Invalid credentials.');
    });

    it('returns message from response data when no detail', () => {
        const err = { response: { data: { message: 'Something failed.' } } };
        expect(getApiErrorMessage(err)).toBe('Something failed.');
    });

    it('returns error key from response data', () => {
        const err = { response: { data: { error: 'Bad request' } } };
        expect(getApiErrorMessage(err)).toBe('Bad request');
    });

    it('returns first non-field error when present', () => {
        const err = { response: { data: { non_field_errors: ['Email already taken.'] } } };
        expect(getApiErrorMessage(err)).toBe('Email already taken.');
    });

    it('uses custom fallback when no known keys', () => {
        const err = { response: { data: {} } };
        expect(getApiErrorMessage(err, 'Custom fallback')).toBe('Custom fallback');
    });

    it('uses fallback when err has no response', () => {
        expect(getApiErrorMessage(new Error('Network error'), 'Try again')).toBe('Try again');
    });

    it('uses default fallback when no response', () => {
        expect(getApiErrorMessage(new Error('Network error'))).toBe('Something went wrong. Please try again.');
    });
});
