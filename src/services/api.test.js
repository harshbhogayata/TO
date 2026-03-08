import { describe, it, expect } from 'vitest';
import { getApiErrorMessage, normaliseParsedResume } from './api';

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

describe('normaliseParsedResume', () => {
    it('maps legacy parser keys into the canonical response contract', () => {
        const normalised = normaliseParsedResume({
            skills: [{ canonical_name: 'react' }],
            experience: [{ title: 'Engineer' }],
            education: [{ degree: 'BSc' }],
            bio: 'Frontend engineer',
            contact: { email: 'redacted@example.com' },
            confidence_score: 0.84,
            parser_version: 'spacy_v1',
            cached: true,
        });

        expect(normalised.parsed_skills).toEqual([{ canonical_name: 'react' }]);
        expect(normalised.parsed_experience).toEqual([{ title: 'Engineer' }]);
        expect(normalised.parsed_education).toEqual([{ degree: 'BSc' }]);
        expect(normalised.generated_bio).toBe('Frontend engineer');
        expect(normalised.contact_info).toEqual({ email: 'redacted@example.com' });
        expect(normalised.ai_enhanced).toBe(false);
        expect(normalised.cached).toBe(true);
    });

    it('preserves canonical keys and infers AI metadata from parser version', () => {
        const normalised = normaliseParsedResume({
            parsed_skills: ['python'],
            parsed_experience: [],
            parsed_education: [],
            generated_bio: 'ML engineer',
            contact_info: { name: 'Candidate' },
            parser_version: 'ai_enhanced_v1',
        });

        expect(normalised.parsed_skills).toEqual(['python']);
        expect(normalised.generated_bio).toBe('ML engineer');
        expect(normalised.ai_enhanced).toBe(true);
        expect(normalised.feature_flag_used).toBe('USE_AI_ENHANCED_RESUME_PARSING');
        expect(normalised.cached).toBe(false);
    });
});
